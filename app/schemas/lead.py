from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LeadScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int
    previous_score: int | None
    scoring_method: str
    score_breakdown: dict[str, Any]
    calculated_at: datetime


class LeadActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    activity_type: str
    description: str
    metadata_: dict[str, Any] = Field(
        ...,
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    source_id: uuid.UUID
    campaign_id: uuid.UUID | None
    first_name: str | None
    last_name: str | None
    email: EmailStr
    phone: str | None
    company_name: str | None
    job_title: str | None
    country: str | None
    city: str | None
    industry: str | None
    company_size: str | None
    message: str | None
    status: str
    score: int
    created_at: datetime
    updated_at: datetime
    score_record: LeadScoreRead | None = None