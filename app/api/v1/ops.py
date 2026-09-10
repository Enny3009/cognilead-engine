import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import get_current_active_admin
from app.core.database import AsyncSessionLocal
from app.models.integration import IntegrationDelivery
from app.models.user import User
from app.schemas.integration import DeliveryRead
from app.workers.dispatch_tasks import sync_lead_to_crm_task

router = APIRouter(prefix="/ops", tags=["Operations & DLQ"])


@router.get("/dlq", response_model=list[DeliveryRead], summary="Inspect Dead-Letter Queue (Admin Only)")
async def get_dlq_jobs(
    current_admin: User = Depends(get_current_active_admin),
) -> list[IntegrationDelivery]:
    async with AsyncSessionLocal() as db:
        stmt = (
            select(IntegrationDelivery)
            .where(IntegrationDelivery.delivery_status.in_(["FAILED", "DEAD_LETTER"]))
            .order_by(IntegrationDelivery.created_at.desc())
            .limit(50)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())


@router.post("/dlq/{id}/replay", summary="Replay Failed Outbound Sync Task")
async def replay_dlq_job(
    id: uuid.UUID,
    current_admin: User = Depends(get_current_active_admin),
) -> dict[str, str]:
    async with AsyncSessionLocal() as db:
        stmt = select(IntegrationDelivery).where(IntegrationDelivery.id == id)
        res = await db.execute(stmt)
        delivery = res.scalar_one_or_none()
        if not delivery:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery record not found")

        task = sync_lead_to_crm_task.apply_async(
            args=[str(delivery.lead_id), str(delivery.endpoint_id), False],
            queue="q.integrations.dispatch",
        )
        return {"status": "REQUEUED", "task_id": task.id}