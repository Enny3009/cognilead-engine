import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import TenantContext
from app.models.campaign import Campaign, LeadSource
from app.schemas.campaign import CampaignCreate, CampaignRead, CampaignUpdate

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("/", response_model=CampaignRead, status_code=status.HTTP_201_CREATED, summary="Create Campaign")
async def create_campaign(
    payload: CampaignCreate,
    tenant: TenantContext = Depends(),
) -> Campaign:
    # Verify campaign_code uniqueness within tenant
    code_check = await tenant.db.execute(
        select(Campaign).where(
            Campaign.organization_id == tenant.organization_id,
            Campaign.campaign_code == payload.campaign_code.strip(),
        )
    )
    if code_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A campaign with this code already exists in your organization",
        )

    # Validate lead_source_id if provided
    if payload.lead_source_id:
        src_check = await tenant.db.execute(
            select(LeadSource).where(
                LeadSource.id == payload.lead_source_id,
                LeadSource.organization_id == tenant.organization_id,
            )
        )
        if not src_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specified lead source not found")

    campaign = Campaign(
        organization_id=tenant.organization_id,
        campaign_code=payload.campaign_code.strip(),
        name=payload.name.strip(),
        lead_source_id=payload.lead_source_id,
        budget=payload.budget,
        currency=payload.currency.upper(),
        status=payload.status,
    )
    tenant.db.add(campaign)
    await tenant.db.flush()
    return campaign


@router.get("/", response_model=list[CampaignRead], summary="List Tenant Campaigns")
async def list_campaigns(
    tenant: TenantContext = Depends(),
) -> list[Campaign]:
    stmt = (
        select(Campaign)
        .where(Campaign.organization_id == tenant.organization_id)
        .order_by(Campaign.created_at.desc())
    )
    result = await tenant.db.execute(stmt)
    return list(result.scalars().all())