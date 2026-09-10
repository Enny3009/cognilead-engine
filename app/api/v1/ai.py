import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import TenantContext
from app.models.lead import Lead
from app.models.qualification import LeadQualification
from app.schemas.qualification import LeadQualificationRead
from app.services.qualification_service import QualificationService
from app.workers.ai_tasks import qualify_lead_rag_task

router = APIRouter(prefix="/ai", tags=["AI Qualification"])


@router.post("/leads/{lead_id}/classify", response_model=LeadQualificationRead, summary="Run Synchronous RAG Qualification")
async def classify_lead_sync(
    lead_id: uuid.UUID,
    tenant: TenantContext = Depends(),
) -> LeadQualification:
    stmt = select(Lead.id).where(Lead.id == lead_id, Lead.organization_id == tenant.organization_id)
    res = await tenant.db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    service = QualificationService(tenant.db)
    return await service.qualify_lead(lead_id)


@router.post("/leads/{lead_id}/async-classify", summary="Queue RAG Qualification to Celery (q.leads.ai)")
async def classify_lead_async(
    lead_id: uuid.UUID,
    tenant: TenantContext = Depends(),
) -> dict[str, str]:
    stmt = select(Lead.id).where(Lead.id == lead_id, Lead.organization_id == tenant.organization_id)
    res = await tenant.db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    task = qualify_lead_rag_task.apply_async(args=[str(lead_id)], queue="q.leads.ai")
    return {"status": "QUEUED", "task_id": task.id}


@router.get("/leads/{lead_id}/qualification", response_model=LeadQualificationRead, summary="Get AI Qualification Report")
async def get_lead_qualification(
    lead_id: uuid.UUID,
    tenant: TenantContext = Depends(),
) -> LeadQualification:
    stmt = (
        select(LeadQualification)
        .join(Lead, Lead.id == LeadQualification.lead_id)
        .where(Lead.id == lead_id, Lead.organization_id == tenant.organization_id)
    )
    res = await tenant.db.execute(stmt)
    qual = res.scalar_one_or_none()
    if not qual:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Qualification report not found for this lead")
    return qual