import asyncio
from datetime import datetime, timezone
import uuid
import structlog
from sqlalchemy import select
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.integrations.mock_crm_client import MockCRMClient
from app.models.integration import ExternalCRMRecord, IntegrationDelivery, IntegrationEndpoint
from app.models.lead import Lead, LeadActivity
from app.services.circuit_breaker import CircuitBreaker
from app.services.rate_limiter import TokenBucketRateLimiter
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


async def _dispatch_sync(
    lead_id: str,
    endpoint_id: str,
    simulate_failure: bool = False,
) -> dict:
    # Create an async Redis client scoped strictly to the lifecycle of this task's event loop
    redis_client = aioredis.from_url(str(settings.REDIS_URI), decode_responses=False)
    
    try:
        rate_limiter = TokenBucketRateLimiter(redis_client)
        circuit_breaker = CircuitBreaker(redis_client)

        # 1. Circuit Breaker Inspection
        allowed = await circuit_breaker.allow_request(endpoint_id)
        if not allowed:
            logger.warn("crm.dispatch.circuit_open", endpoint_id=endpoint_id)
            return {
                "status": "DEFERRED",
                "reason": "Circuit breaker is OPEN. Outbound traffic paused for cooldown.",
            }

        # 2. Token Bucket Rate Limiter Inspection
        token_acquired = await rate_limiter.acquire_token(endpoint_id, limit_per_minute=100)
        if not token_acquired:
            logger.warn("crm.dispatch.rate_limited", endpoint_id=endpoint_id)
            return {
                "status": "RATE_LIMITED",
                "reason": "Token bucket quota exhausted. Retrying with backoff.",
            }

        async with AsyncSessionLocal() as db:
            res_ep = await db.execute(select(IntegrationEndpoint).where(IntegrationEndpoint.id == uuid.UUID(endpoint_id)))
            endpoint = res_ep.scalar_one_or_none()

            res_lead = await db.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))
            lead = res_lead.scalar_one_or_none()

            if not endpoint or not lead:
                return {"status": "ERROR", "reason": "Endpoint or Lead entity missing."}

            crm_client = MockCRMClient()
            payload = {
                "lead_id": str(lead.id),
                "email": lead.email,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "company": lead.company_name,
                "score": lead.score,
            }

            # 3. Dispatch Outbound Sync
            res = await crm_client.sync_lead(
                endpoint_url=endpoint.base_url,
                lead_payload=payload,
                simulate_failure=simulate_failure,
            )

            delivery = IntegrationDelivery(
                lead_id=lead.id,
                endpoint_id=endpoint.id,
                delivery_status="DELIVERED" if res.success else "FAILED",
                http_status_code=res.status_code,
                request_payload=payload,
                response_body=res.response_body,
                attempt_count=1,
            )
            db.add(delivery)

            if res.success:
                await circuit_breaker.record_success(endpoint_id)
                act = LeadActivity(
                    lead_id=lead.id,
                    activity_type="CRM_SYNC",
                    description=f"Synced successfully to {endpoint.platform} (Record ID: {res.external_id}).",
                    metadata_={"external_id": res.external_id, "endpoint_id": str(endpoint.id)},
                )
                db.add(act)
            else:
                await circuit_breaker.record_failure(endpoint_id)
                act = LeadActivity(
                    lead_id=lead.id,
                    activity_type="CRM_SYNC",
                    description=f"Outbound sync to {endpoint.platform} failed: {res.error_message}.",
                    metadata_={"status_code": res.status_code},
                )
                db.add(act)

            await db.commit()

            return {
                "status": "DELIVERED" if res.success else "FAILED",
                "http_status_code": res.status_code,
                "external_id": res.external_id,
            }
    finally:
        # Await clean disconnect while the event loop created by asyncio.run is still open
        await redis_client.aclose()


@celery_app.task(
    name="app.workers.dispatch_tasks.sync_lead_to_crm_task",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
)
def sync_lead_to_crm_task(
    self,
    lead_id: str,
    endpoint_id: str,
    simulate_failure: bool = False,
) -> dict:
    logger.info("crm.dispatch.started", task_id=self.request.id, lead_id=lead_id, endpoint_id=endpoint_id)
    outcome = asyncio.run(_dispatch_sync(lead_id, endpoint_id, simulate_failure))
    logger.info("crm.dispatch.completed", task_id=self.request.id, outcome=outcome)
    return outcome