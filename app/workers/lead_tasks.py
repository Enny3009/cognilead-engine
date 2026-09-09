import asyncio
from datetime import datetime, timezone
import uuid
import structlog
from app.core.database import AsyncSessionLocal
from app.services.deduplication_service import DeduplicationService
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


async def _process_ingest(
    organization_id: str,
    source_id: str,
    raw_payload: dict,
    campaign_id: str | None = None,
) -> dict:
    async with AsyncSessionLocal() as db:
        dedup_service = DeduplicationService(db)
        result = await dedup_service.evaluate_and_deduplicate(
            organization_id=uuid.UUID(organization_id),
            source_id=uuid.UUID(source_id),
            raw_payload=raw_payload,
            campaign_id=uuid.UUID(campaign_id) if campaign_id else None,
        )
        await db.commit()

        return {
            "lead_id": str(result.lead.id),
            "action": result.action,
            "matched_existing": result.matched_existing,
            "review_flag": result.review_flag,
            "details": result.details,
        }


@celery_app.task(
    name="app.workers.lead_tasks.ingest_raw_lead_task",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def ingest_raw_lead_task(
    self,
    organization_id: str,
    source_id: str,
    raw_payload: dict,
    headers: dict,
    received_at: str,
    campaign_id: str | None = None,
) -> dict:
    logger.info("lead.ingest.processing_started", task_id=self.request.id, source_id=source_id)

    outcome = asyncio.run(
        _process_ingest(
            organization_id=organization_id,
            source_id=source_id,
            raw_payload=raw_payload,
            campaign_id=campaign_id,
        )
    )

    logger.info("lead.ingest.processed", task_id=self.request.id, outcome=outcome)

    return {
        "status": "PROCESSED",
        "task_id": self.request.id,
        "outcome": outcome,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }