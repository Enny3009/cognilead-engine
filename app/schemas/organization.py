from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, Field


class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, examples=["Acme Corp"])
    slug: str = Field(..., min_length=2, max_length=100, examples=["acme-corp"])
    timezone: str = Field(default="UTC", max_length=64)
    industry: str | None = Field(default=None, max_length=100)


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationRead(OrganizationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime