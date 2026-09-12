import asyncio
from datetime import datetime, timedelta, timezone
import structlog
from sqlalchemy import select
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.attribution import CampaignAttributionRollup
from app.models.campaign import Campaign
from app.models.integration import IntegrationEndpoint
from app.models.lead import Lead, LeadActivity
from app.services.attribution_service import AttributionService
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


async def _evaluate_circuit_breakers() -> int:
    """Finds OPEN circuit breakers in Redis and transitions eligible ones to HALF_OPEN."""
    redis_client = aioredis.from_url(str(settings.REDIS_URI), decode_responses=False)
    reset_count = 0
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(IntegrationEndpoint)
            res = await db.execute(stmt)
            endpoints = res.scalars().all()

            for ep in endpoints:
                state_key = f"cb:endpoint:{ep.id}:state"
                raw_state = await redis_client.get(state_key)
                state = raw_state.decode("utf-8") if raw_state else "CLOSED"

                # Check if TTL expired or key missing while endpoint is marked failed
                ttl = await redis_client.ttl(state_key)
                if state == "OPEN" and ttl <= 0:
                    await redis_client.set(state_key, "HALF_OPEN")
                    reset_count += 1
                    logger.info("circuit_breaker.transition", endpoint_id=str(ep.id), state="HALF_OPEN")
    finally:
        await redis_client.aclose()
    return reset_count


async def _refresh_attribution_rollups() -> int:
    """Calculates multi-touch attribution metrics for active campaigns."""
    updated = 0
    async with AsyncSessionLocal() as db:
        stmt = select(Campaign)
        res = await db.execute(stmt)
        campaigns = res.scalars().all()

        service = AttributionService(db)
        for camp in campaigns:
            perf = await service.calculate_campaign_performance(camp.organization_id)
            for p in perf:
                if p.campaign_id == camp.id:
                    rollup = CampaignAttributionRollup(
                        organization_id=camp.organization_id,
                        campaign_id=camp.id,
                        first_touch_credit=Decimal(str(p.first_touch_leads)),
                        last_touch_credit=Decimal(str(p.last_touch_leads)),
                        linear_credit=Decimal(str(p.linear_attributed_leads)),
                        attributed_revenue=p.attributed_pipeline_value,
                        metrics_snapshot={"budget": str(camp.budget)},
                    )
                    db.add(rollup)
                    updated += 1
        await db.commit()
    return updated


async def _flag_stale_leads() -> int:
    """Detects qualified leads uncontacted for > 48 hours and logs warning activities."""
    flagged = 0
    threshold = datetime.now(timezone.utc) - timedelta(hours=48)
    async with AsyncSessionLocal() as db:
        stmt = select(Lead).where(
            Lead.status == "QUALIFIED",
            Lead.last_contacted_at.is_(None),
            Lead.created_at <= threshold,
        )
        res = await db.execute(stmt)
        stale_leads = res.scalars().all()

        for lead in stale_leads:
            lead.status = "LOST"
            activity = LeadActivity(
                lead_id=lead.id,
                activity_type="STATUS_CHANGE",
                description="Lead marked LOST automatically due to SLA breach: uncontacted for > 48 hours.",
                metadata_={"sla_breached": True, "stale_since": lead.created_at.isoformat()},
            )
            db.add(activity)
            flagged += 1

        await db.commit()
    return flagged


@celery_app.task(name="app.workers.scheduled_tasks.evaluate_circuit_breakers_task")
def evaluate_circuit_breakers_task() -> dict:
    count = asyncio.run(_evaluate_circuit_breakers())
    logger.info("scheduled.circuit_breakers.evaluated", resets=count)
    return {"resets": count}


@celery_app.task(name="app.workers.scheduled_tasks.refresh_attribution_rollups_task")
def refresh_attribution_rollups_task() -> dict:
    count = asyncio.run(_refresh_attribution_rollups())
    logger.info("scheduled.attribution_rollups.refreshed", updated=count)
    return {"rollups_updated": count}


@celery_app.task(name="app.workers.scheduled_tasks.flag_stale_leads_task")
def flag_stale_leads_task() -> dict:
    count = asyncio.run(_flag_stale_leads())
    logger.info("scheduled.stale_leads.flagged", count=count)
    return {"flagged_leads": count}