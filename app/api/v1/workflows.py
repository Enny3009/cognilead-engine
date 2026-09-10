import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import TenantContext
from app.models.lead import Lead
from app.models.workflow import Workflow, WorkflowExecution, WorkflowStep
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowExecutionRead,
    WorkflowRead,
)
from app.services.workflow_engine import WorkflowEngine
from app.workers.workflow_tasks import execute_workflow_dag_task

router = APIRouter(prefix="/workflows", tags=["Workflows (DAG Engine)"])


@router.post("/", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED, summary="Create Workflow with DAG Steps")
async def create_workflow(
    payload: WorkflowCreate,
    tenant: TenantContext = Depends(),
) -> Workflow:
    workflow = Workflow(
        organization_id=tenant.organization_id,
        name=payload.name.strip(),
        trigger_type=payload.trigger_type,
        is_active=payload.is_active,
    )
    tenant.db.add(workflow)
    await tenant.db.flush()

    for step_in in payload.steps:
        step = WorkflowStep(
            workflow_id=workflow.id,
            step_type=step_in.step_type,
            configuration=step_in.configuration,
            position=step_in.position,
            is_enabled=step_in.is_enabled,
        )
        tenant.db.add(step)

    await tenant.db.commit()

    stmt = select(Workflow).where(Workflow.id == workflow.id).options(selectinload(Workflow.steps))
    res = await tenant.db.execute(stmt)
    return res.scalar_one()


@router.get("/", response_model=list[WorkflowRead], summary="List Tenant Workflows")
async def list_workflows(
    tenant: TenantContext = Depends(),
) -> list[Workflow]:
    stmt = (
        select(Workflow)
        .where(Workflow.organization_id == tenant.organization_id)
        .options(selectinload(Workflow.steps))
        .order_by(Workflow.created_at.desc())
    )
    result = await tenant.db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{id}/execute/{lead_id}", response_model=WorkflowExecutionRead, summary="Execute Workflow DAG Synchronously")
async def execute_dag_sync(
    id: uuid.UUID,
    lead_id: uuid.UUID,
    tenant: TenantContext = Depends(),
) -> WorkflowExecution:
    stmt = select(Workflow.id).where(Workflow.id == id, Workflow.organization_id == tenant.organization_id)
    res = await tenant.db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    engine = WorkflowEngine(tenant.db)
    return await engine.execute_dag(id, lead_id)


@router.post("/{id}/queue/{lead_id}", summary="Queue Workflow DAG to Celery (q.workflows.engine)")
async def queue_dag_async(
    id: uuid.UUID,
    lead_id: uuid.UUID,
    tenant: TenantContext = Depends(),
) -> dict[str, str]:
    stmt = select(Workflow.id).where(Workflow.id == id, Workflow.organization_id == tenant.organization_id)
    res = await tenant.db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    task = execute_workflow_dag_task.apply_async(args=[str(id), str(lead_id)], queue="q.workflows.engine")
    return {"status": "QUEUED", "task_id": task.id}