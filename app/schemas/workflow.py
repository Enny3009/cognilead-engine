from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, Field


class WorkflowStepCreate(BaseModel):
    step_type: str = Field(..., examples=["CONDITION", "ASSIGN_LEAD", "CREATE_CRM_RECORD"])
    configuration: dict[str, Any] = Field(default_factory=dict)
    position: int = Field(..., ge=1)
    is_enabled: bool = True


class WorkflowStepRead(WorkflowStepCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workflow_id: uuid.UUID


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, examples=["Enterprise Qualification & Routing DAG"])
    trigger_type: str = Field(..., examples=["LEAD_CREATED", "SCORE_THRESHOLD"])
    is_active: bool = True
    steps: list[WorkflowStepCreate] = Field(default_factory=list)


class WorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    trigger_type: str
    is_active: bool
    created_at: datetime
    steps: list[WorkflowStepRead] = Field(default_factory=list)


class WorkflowExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workflow_id: uuid.UUID
    lead_id: uuid.UUID
    status: str
    current_step: int
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None