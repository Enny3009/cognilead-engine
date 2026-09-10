from datetime import datetime
from enum import Enum
import uuid
from pydantic import BaseModel, ConfigDict, Field


class DocumentCategoryEnum(str, Enum):
    PRICING_GUIDE = "PRICING_GUIDE"
    SERVICE_CATALOG = "SERVICE_CATALOG"
    IDEAL_CUSTOMER_PROFILE = "IDEAL_CUSTOMER_PROFILE"
    CASE_STUDY = "CASE_STUDY"


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, examples=["2026 Enterprise Pricing & SLA Matrix"])
    category: DocumentCategoryEnum = Field(..., examples=[DocumentCategoryEnum.PRICING_GUIDE])
    raw_content: str = Field(..., min_length=20, description="Full markdown or text SOP to be chunked and embedded.")


class KnowledgeChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    content: str
    token_count: int
    chunk_index: int


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    category: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0


class SemanticSearchQuery(BaseModel):
    query: str = Field(..., min_length=3, examples=["How much does enterprise deployment cost?"])
    limit: int = Field(default=4, ge=1, le=10)


class SemanticSearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    content: str
    similarity: float