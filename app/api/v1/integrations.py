import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import TenantContext
from app.models.integration import IntegrationDelivery, IntegrationEndpoint
from app.schemas.integration import (
    DeliveryRead,
    DispatchSyncRequest,
    EndpointCreate,
    EndpointRead,
)
from app.workers.dispatch_tasks import sync_lead_to_crm_task

router = APIRouter(prefix="/integrations", tags=["Integrations & Circuit Breaker"])


@router.post("/endpoints", response_model=EndpointRead, status_code=status.HTTP_201_CREATED, summary="Register Downstream CRM Endpoint")
async def create_endpoint(
    payload: EndpointCreate,
    tenant: TenantContext = Depends(),
) -> IntegrationEndpoint:
    endpoint = IntegrationEndpoint(
        organization_id=tenant.organization_id,
        platform=payload.platform.upper(),
        base_url=payload.base_url.strip(),
        rate_limit_per_minute=payload.rate_limit_per_minute,
        circuit_state="CLOSED",
    )
    tenant.db.add(endpoint)
    await tenant.db.commit()
    await tenant.db.refresh(endpoint)
    return endpoint


@router.get("/endpoints", response_model=list[EndpointRead], summary="List Integration Endpoints")
async def list_endpoints(
    tenant: TenantContext = Depends(),
) -> list[IntegrationEndpoint]:
    stmt = select(IntegrationEndpoint).where(IntegrationEndpoint.organization_id == tenant.organization_id)
    res = await tenant.db.execute(stmt)
    return list(res.scalars().all())


@router.post("/endpoints/{endpoint_id}/sync/{lead_id}", summary="Dispatch CRM Sync Task (Rate-Limited & Circuit Guarded)")
async def dispatch_sync(
    endpoint_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: DispatchSyncRequest,
    tenant: TenantContext = Depends(),
) -> dict[str, str]:
    stmt = select(IntegrationEndpoint.id).where(
        IntegrationEndpoint.id == endpoint_id,
        IntegrationEndpoint.organization_id == tenant.organization_id,
    )
    res = await tenant.db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration endpoint not found")

    task = sync_lead_to_crm_task.apply_async(
        args=[str(lead_id), str(endpoint_id), payload.simulate_failure],
        queue="q.integrations.dispatch",
    )
    return {"status": "QUEUED", "task_id": task.id}


@router.get("/deliveries", response_model=list[DeliveryRead], summary="List Integration Delivery Logs")
async def list_deliveries(
    tenant: TenantContext = Depends(),
) -> list[IntegrationDelivery]:
    stmt = (
        select(IntegrationDelivery)
        .join(IntegrationEndpoint, IntegrationEndpoint.id == IntegrationDelivery.endpoint_id)
        .where(IntegrationEndpoint.organization_id == tenant.organization_id)
        .order_by(IntegrationDelivery.created_at.desc())
    )
    res = await tenant.db.execute(stmt)
    return list(res.scalars().all())