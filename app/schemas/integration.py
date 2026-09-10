from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, Field


class EndpointCreate(BaseModel):
    platform: str = Field(..., examples=["SALESFORCE", "HUBSPOT"])
    base_url: str = Field(..., examples=["https://api.salesforce.mock/v1/leads"])
    rate_limit_per_minute: int = Field(default=100, ge=1)


class EndpointRead(EndpointCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    circuit_state: str
    failure_count: int
    created_at: datetime


class DispatchSyncRequest(BaseModel):
    simulate_failure: bool = Field(default=False, description="Set True to test circuit breaker trip on HTTP 500.")


class DeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    lead_id: uuid.UUID
    endpoint_id: uuid.UUID
    delivery_status: str
    http_status_code: int | None
    attempt_count: int
    created_at: datetime