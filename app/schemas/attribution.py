from datetime import datetime
from decimal import Decimal
from enum import Enum
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ChannelEnum(str, Enum):
    PAID_SEARCH = "PAID_SEARCH"
    PAID_SOCIAL = "PAID_SOCIAL"
    ORGANIC_SEARCH = "ORGANIC_SEARCH"
    DIRECT = "DIRECT"
    EMAIL = "EMAIL"


class TouchpointCreate(BaseModel):
    channel: ChannelEnum = Field(..., examples=[ChannelEnum.PAID_SOCIAL])
    touchpoint_type: str = Field(default="INTERMEDIATE", examples=["FIRST_TOUCH", "INTERMEDIATE", "LAST_TOUCH"])
    utm_source: str | None = Field(default=None, examples=["meta"])
    utm_medium: str | None = Field(default=None, examples=["cpc"])
    utm_campaign: str | None = Field(default=None, examples=["enterprise_q3"])


class TouchpointRead(TouchpointCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    lead_id: uuid.UUID
    occurred_at: datetime


class ChannelAttributionShare(BaseModel):
    channel: str
    first_touch_percentage: float
    last_touch_percentage: float
    linear_percentage: float
    total_touchpoints: int


class AttributionSummaryResponse(BaseModel):
    organization_id: uuid.UUID
    total_touchpoints: int
    analyzed_leads_count: int
    channels: list[ChannelAttributionShare]


class CampaignPerformanceRead(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    campaign_code: str
    budget: Decimal
    first_touch_leads: float
    last_touch_leads: float
    linear_attributed_leads: float
    attributed_pipeline_value: Decimal