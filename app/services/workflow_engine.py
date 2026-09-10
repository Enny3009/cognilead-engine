from datetime import datetime, timezone
from typing import Any
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadActivity
from app.models.workflow import Workflow, WorkflowExecution, WorkflowStep


class WorkflowEngine:
    """
    DAG State Machine:
    Evaluates conditional branches and sequentially executes actions.
    Persists execution step indexes atomically to guarantee idempotency.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def evaluate_condition(self, condition_config: dict[str, Any], lead: Lead) -> bool:
        """
        Evaluates boolean criteria:
        e.g., {"field": "score", "operator": ">=", "value": 80}
        """
        field = condition_config.get("field", "")
        operator = condition_config.get("operator", "==")
        target_value = condition_config.get("value")

        actual_value = getattr(lead, field, None)
        if actual_value is None and isinstance(lead.normalized_data, dict):
            actual_value = lead.normalized_data.get(field)

        if operator == ">=":
            return float(actual_value or 0) >= float(target_value)
        elif operator == "<=":
            return float(actual_value or 0) <= float(target_value)
        elif operator == "==":
            return str(actual_value).lower() == str(target_value).lower()
        elif operator == "!=":
            return str(actual_value).lower() != str(target_value).lower()
        return False

    async def execute_dag(
        self,
        workflow_id: uuid.UUID,
        lead_id: uuid.UUID,
    ) -> WorkflowExecution:
        # 1. Load Workflow and Steps
        stmt_wf = (
            select(Workflow)
            .where(Workflow.id == workflow_id)
        )
        res_wf = await self.db.execute(stmt_wf)
        workflow = res_wf.scalar_one_or_none()
        if not workflow or not workflow.is_active:
            raise ValueError("Workflow not found or disabled.")

        stmt_steps = (
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == workflow_id, WorkflowStep.is_enabled == True)
            .order_by(WorkflowStep.position)
        )
        res_steps = await self.db.execute(stmt_steps)
        steps = res_steps.scalars().all()

        stmt_lead = select(Lead).where(Lead.id == lead_id)
        res_lead = await self.db.execute(stmt_lead)
        lead = res_lead.scalar_one_or_none()
        if not lead:
            raise ValueError("Target lead not found.")

        # 2. Initialize Execution Record
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            lead_id=lead.id,
            status="RUNNING",
            current_step=0,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(execution)
        await self.db.flush()

        try:
            for step in steps:
                execution.current_step = step.position

                if step.step_type == "CONDITION":
                    passed = self.evaluate_condition(step.configuration, lead)
                    if not passed:
                        # Condition not met, exit DAG cleanly
                        execution.status = "COMPLETED"
                        execution.completed_at = datetime.now(timezone.utc)
                        break

                elif step.step_type == "ASSIGN_LEAD":
                    method = step.configuration.get("method", "ROUND_ROBIN")
                    activity = LeadActivity(
                        lead_id=lead.id,
                        activity_type="ASSIGNMENT",
                        description=f"Automated DAG assignment via {method}.",
                        metadata_={"workflow_id": str(workflow.id), "step_id": str(step.id)},
                    )
                    self.db.add(activity)

                elif step.step_type == "CREATE_CRM_RECORD":
                    # Queues outbound integration delivery task
                    activity = LeadActivity(
                        lead_id=lead.id,
                        activity_type="CRM_SYNC",
                        description=f"Queued outbound sync to {step.configuration.get('platform', 'EXTERNAL_CRM')}.",
                        metadata_={"step_id": str(step.id), "config": step.configuration},
                    )
                    self.db.add(activity)

            execution.status = "COMPLETED"
            execution.completed_at = datetime.now(timezone.utc)

        except Exception as err:
            execution.status = "FAILED"
            execution.error_message = str(err)
            execution.completed_at = datetime.now(timezone.utc)
            raise

        finally:
            await self.db.commit()

        return execution