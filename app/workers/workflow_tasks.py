import asyncio
import uuid
import structlog
from app.core.database import AsyncSessionLocal
from app.services.workflow_engine import WorkflowEngine
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


async def _run_workflow_dag(workflow_id: str, lead_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        engine = WorkflowEngine(db)
        execution = await engine.execute_dag(uuid.UUID(workflow_id), uuid.UUID(lead_id))
        return {
            "execution_id": str(execution.id),
            "status": execution.status,
            "current_step": execution.current_step,
            "error": execution.error_message,
        }


@celery_app.task(
    name="app.workers.workflow_tasks.execute_workflow_dag_task",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
)
def execute_workflow_dag_task(self, workflow_id: str, lead_id: str) -> dict:
    logger.info("workflow.dag.started", task_id=self.request.id, workflow_id=workflow_id, lead_id=lead_id)
    outcome = asyncio.run(_run_workflow_dag(workflow_id, lead_id))
    logger.info("workflow.dag.completed", task_id=self.request.id, outcome=outcome)
    return outcome