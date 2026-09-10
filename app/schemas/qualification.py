from datetime import datetime
from enum import Enum
import uuid
from pydantic import BaseModel, ConfigDict, Field


class IntentCategoryEnum(str, Enum):
    ENTERPRISE_INQUIRY = "ENTERPRISE_INQUIRY"
    GENERAL_PRICING = "GENERAL_PRICING"
    JOB_SEEKER = "JOB_SEEKER"
    SPAM = "SPAM"


class BudgetFitEnum(str, Enum):
    HIGH_FIT = "HIGH_FIT"
    MODERATE_FIT = "MODERATE_FIT"
    LOW_FIT = "LOW_FIT"
    UNKNOWN = "UNKNOWN"


class TimelineUrgencyEnum(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    ONE_TO_THREE_MONTHS = "1_TO_3_MONTHS"
    EXPLORATORY = "EXPLORATORY"


class LeadQualificationOutput(BaseModel):
    """Strict schema contract enforced onto OpenAI structured outputs."""
    qualification_score: int = Field(ge=0, le=100, description="Overall qualified score 0-100 combining budget, intent, and seniority.")
    is_qualified: bool = Field(description="True if lead satisfies enterprise commercial thresholds.")
    intent_category: IntentCategoryEnum
    budget_fit: BudgetFitEnum
    timeline_urgency: TimelineUrgencyEnum
    ai_summary: str = Field(description="Maximum 3-sentence executive summary synthesizing lead intent and context.")
    recommended_routing: str = Field(description="Strictly 'ENTERPRISE_SALES', 'SME_SALES', or 'NURTURE'.")
    cited_chunk_ids: list[str] = Field(default_factory=list, description="IDs of knowledge chunks referenced in the evaluation.")


class LeadQualificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    qualification_score: int
    is_qualified: bool
    intent_category: str
    budget_fit: str
    timeline_urgency: str
    ai_summary: str
    recommended_routing: str
    cited_chunk_ids: list[uuid.UUID]
    evaluated_at: datetime