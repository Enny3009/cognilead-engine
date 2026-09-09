from datetime import datetime, timezone
import structlog
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


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
) -> dict:
    """
    Asynchronous Celery consumer for q.leads.ingest:
    Consumes verified webhook events, logs tracing metadata, and prepares
    payload for Tier 1-4 deduplication and scoring.
    """
    logger.info(
        "lead.ingest.task_received",
        organization_id=organization_id,
        source_id=source_id,
        task_id=self.request.id,
        received_at=received_at,
    )
    
    # Next phase wires this directly into DeduplicationService and ScoringService
    return {
        "status": "ACCEPTED",
        "task_id": self.request.id,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }