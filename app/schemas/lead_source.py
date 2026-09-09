from datetime import datetime
from enum import Enum
import uuid
from pydantic import BaseModel, ConfigDict, Field


class SourceTypeEnum(str, Enum):
    META_ADS = "META_ADS"
    GOOGLE_ADS = "GOOGLE_ADS"
    TIKTOK_ADS = "TIKTOK_ADS"
    WEBSITE_FORM = "WEBSITE_FORM"
    LANDING_PAGE = "LANDING_PAGE"
    API = "API"
    REFERRAL = "REFERRAL"


class LeadSourceBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Meta Q3 Growth Ads"])
    source_type: SourceTypeEnum = Field(..., examples=[SourceTypeEnum.META_ADS])
    is_active: bool = Field(default=True)


class LeadSourceCreate(LeadSourceBase):
    custom_secret: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
        description="Optional pre-shared secret. If omitted, a cryptographically secure 32-byte secret is generated.",
    )


class LeadSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    is_active: bool | None = None


class LeadSourceRead(LeadSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    webhook_slug: str
    created_at: datetime
    updated_at: datetime


class LeadSourceCreateResponse(LeadSourceRead):
    plaintext_webhook_secret: str = Field(
        ...,
        description="Returned ONCE upon creation. Must be configured in the advertising platform or webhook provider.",
    )
    webhook_url: str