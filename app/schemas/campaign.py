from datetime import datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel, ConfigDict, Field


class CampaignBase(BaseModel):
    campaign_code: str = Field(..., min_length=2, max_length=64, examples=["CAMP-2026-Q3-META"])
    name: str = Field(..., min_length=2, max_length=255, examples=["US Enterprise Procurement Campaign"])
    lead_source_id: uuid.UUID | None = None
    budget: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    currency: str = Field(default="USD", min_length=3, max_length=3)
    status: str = Field(default="ACTIVE")


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    budget: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: str | None = None
    lead_source_id: uuid.UUID | None = None


class CampaignRead(CampaignBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime