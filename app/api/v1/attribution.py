import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import TenantContext
from app.models.attribution import AttributionTouchpoint
from app.models.lead import Lead
from app.schemas.attribution import (
    AttributionSummaryResponse,
    CampaignPerformanceRead,
    TouchpointCreate,
    TouchpointRead,
)
from app.services.attribution_service import AttributionService

router = APIRouter(prefix="/attribution", tags=["Attribution Engine"])


@router.post("/leads/{lead_id}/touchpoints", response_model=TouchpointRead, status_code=status.HTTP_201_CREATED, summary="Record Attribution Touchpoint")
async def record_touchpoint(
    lead_id: uuid.UUID,
    payload: TouchpointCreate,
    tenant: TenantContext = Depends(),
) -> AttributionTouchpoint:
    stmt = select(Lead.id).where(Lead.id == lead_id, Lead.organization_id == tenant.organization_id)
    res = await tenant.db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    service = AttributionService(tenant.db)
    tp = await service.record_touchpoint(
        lead_id=lead_id,
        channel=payload.channel.value,
        touchpoint_type=payload.touchpoint_type,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
    )
    await tenant.db.commit()
    return tp


@router.get("/summary", response_model=AttributionSummaryResponse, summary="Multi-Touch Channel Attribution Summary")
async def get_attribution_summary(
    tenant: TenantContext = Depends(),
) -> AttributionSummaryResponse:
    service = AttributionService(tenant.db)
    return await service.calculate_summary(tenant.organization_id)


@router.get("/campaign-performance", response_model=list[CampaignPerformanceRead], summary="Campaign ROI & Attributed Pipeline")
async def get_campaign_performance(
    tenant: TenantContext = Depends(),
) -> list[CampaignPerformanceRead]:
    service = AttributionService(tenant.db)
    return await service.calculate_campaign_performance(tenant.organization_id)