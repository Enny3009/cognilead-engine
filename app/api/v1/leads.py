from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.utils.pagination import PaginatedResponse

from app.api.deps import TenantContext
from app.models.lead import Lead, LeadActivity
from app.schemas.lead import LeadActivityRead, LeadRead, LeadScoreRead
from app.services.scoring_service import ScoringService

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.get("/", response_model=PaginatedResponse[LeadRead], summary="List Organization Leads")
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    tenant: TenantContext = Depends(),
) -> PaginatedResponse[LeadRead]:
    offset = (page - 1) * page_size
    
    count_stmt = select(func.count(Lead.id)).where(Lead.organization_id == tenant.organization_id)
    total = (await tenant.db.execute(count_stmt)).scalar_one()
    
    stmt = (
        select(Lead)
        .where(Lead.organization_id == tenant.organization_id)
        .options(selectinload(Lead.score_record))
        .order_by(Lead.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list((await tenant.db.execute(stmt)).scalars().all())
    
    return PaginatedResponse(
        items=items, page=page, page_size=page_size, 
        total=total, total_pages=(total + page_size - 1) // page_size
    )


@router.get("/{id}", response_model=LeadRead, summary="Get Lead Profile with Score Breakdown")
async def get_lead(
    id: uuid.UUID,
    tenant: TenantContext = Depends(),
) -> Lead:
    stmt = (
        select(Lead)
        .where(Lead.id == id, Lead.organization_id == tenant.organization_id)
        .options(selectinload(Lead.score_record))
    )
    result = await tenant.db.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.post("/{id}/score", response_model=LeadScoreRead, summary="Manually Recalculate Lead Score")
async def score_lead(
    id: uuid.UUID,
    tenant: TenantContext = Depends(),
) -> LeadScoreRead:
    stmt = select(Lead).where(Lead.id == id, Lead.organization_id == tenant.organization_id)
    result = await tenant.db.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    scoring_service = ScoringService(tenant.db)
    res = await scoring_service.calculate_and_persist_score(lead.id)

    return LeadScoreRead(
        score=res.total_score,
        previous_score=res.previous_score,
        scoring_method=res.scoring_method,
        score_breakdown=res.breakdown,
        calculated_at=datetime.now(timezone.utc),
    )


@router.get("/{id}/activities", response_model=list[LeadActivityRead], summary="Get Lead Audit Activities")
async def get_lead_activities(
    id: uuid.UUID,
    tenant: TenantContext = Depends(),
) -> list[LeadActivity]:
    # Verify lead belongs to tenant
    lead_check = await tenant.db.execute(
        select(Lead.id).where(Lead.id == id, Lead.organization_id == tenant.organization_id)
    )
    if not lead_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    stmt = (
        select(LeadActivity)
        .where(LeadActivity.lead_id == id)
        .order_by(LeadActivity.created_at.desc())
    )
    result = await tenant.db.execute(stmt)
    return list(result.scalars().all())