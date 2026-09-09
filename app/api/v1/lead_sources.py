import secrets
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext
from app.core.encryption import encryptor
from app.models.campaign import LeadSource
from app.schemas.lead_source import (
    LeadSourceCreate,
    LeadSourceCreateResponse,
    LeadSourceRead,
    LeadSourceUpdate,
)

router = APIRouter(prefix="/lead-sources", tags=["Lead Sources"])


@router.post(
    "/",
    response_model=LeadSourceCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New Inbound Lead Source",
)
async def create_lead_source(
    payload: LeadSourceCreate,
    request: Request,
    tenant: TenantContext = Depends(),
) -> LeadSourceCreateResponse:
    # Generate unique URL-safe webhook slug
    slug = f"src_{secrets.token_hex(8)}"
    plaintext_secret = payload.custom_secret or secrets.token_urlsafe(32)

    # Encrypt the webhook secret at rest using AES-256-GCM
    encrypted_secret = encryptor.encrypt(plaintext_secret)

    lead_source = LeadSource(
        organization_id=tenant.organization_id,
        name=payload.name.strip(),
        source_type=payload.source_type.value,
        webhook_slug=slug,
        webhook_secret_hash=encrypted_secret.hex(),  # Stored as encrypted hex
        is_active=payload.is_active,
    )
    tenant.db.add(lead_source)
    await tenant.db.flush()

    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/webhooks/{slug}"

    return LeadSourceCreateResponse(
        id=lead_source.id,
        organization_id=lead_source.organization_id,
        name=lead_source.name,
        source_type=lead_source.source_type,  # type: ignore[arg-type]
        webhook_slug=lead_source.webhook_slug,
        is_active=lead_source.is_active,
        created_at=lead_source.created_at,
        updated_at=lead_source.updated_at,
        plaintext_webhook_secret=plaintext_secret,
        webhook_url=webhook_url,
    )


@router.get("/", response_model=list[LeadSourceRead], summary="List Tenant Lead Sources")
async def list_lead_sources(
    tenant: TenantContext = Depends(),
) -> list[LeadSource]:
    stmt = (
        select(LeadSource)
        .where(LeadSource.organization_id == tenant.organization_id)
        .order_by(LeadSource.created_at.desc())
    )
    result = await tenant.db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{id}", response_model=LeadSourceRead, summary="Get Lead Source Details")
async def get_lead_source(
    id: uuid.UUID,
    tenant: TenantContext = Depends(),
) -> LeadSource:
    stmt = select(LeadSource).where(
        LeadSource.id == id,
        LeadSource.organization_id == tenant.organization_id,
    )
    result = await tenant.db.execute(stmt)
    lead_source = result.scalar_one_or_none()
    if not lead_source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead source not found")
    return lead_source


@router.patch("/{id}", response_model=LeadSourceRead, summary="Update Lead Source")
async def update_lead_source(
    id: uuid.UUID,
    payload: LeadSourceUpdate,
    tenant: TenantContext = Depends(),
) -> LeadSource:
    stmt = select(LeadSource).where(
        LeadSource.id == id,
        LeadSource.organization_id == tenant.organization_id,
    )
    result = await tenant.db.execute(stmt)
    lead_source = result.scalar_one_or_none()
    if not lead_source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead source not found")

    if payload.name is not None:
        lead_source.name = payload.name.strip()
    if payload.is_active is not None:
        lead_source.is_active = payload.is_active

    tenant.db.add(lead_source)
    await tenant.db.flush()
    return lead_source