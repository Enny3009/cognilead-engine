import asyncio
from datetime import datetime, timezone
import uuid
import structlog

from app.core.database import AsyncSessionLocal
from app.services.qualification_service import QualificationService
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


async def _run_qualification(lead_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        service = QualificationService(db)
        qual = await service.qualify_lead(uuid.UUID(lead_id))
        await db.commit()

        return {
            "lead_id": str(qual.lead_id),
            "is_qualified": qual.is_qualified,
            "intent_category": qual.intent_category,
            "budget_fit": qual.budget_fit,
            "routing": qual.recommended_routing,
        }


@celery_app.task(
    name="app.workers.ai_tasks.qualify_lead_rag_task",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def qualify_lead_rag_task(self, lead_id: str) -> dict:
    logger.info("lead.ai_qualification.started", task_id=self.request.id, lead_id=lead_id)

    outcome = asyncio.run(_run_qualification(lead_id))

    logger.info("lead.ai_qualification.completed", task_id=self.request.id, outcome=outcome)

    return {
        "status": "QUALIFIED",
        "task_id": self.request.id,
        "outcome": outcome,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }