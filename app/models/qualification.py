from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LeadQualification(Base):
    __tablename__ = "lead_qualifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    qualification_score: Mapped[int] = mapped_column(Integer, nullable=False)
    is_qualified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    intent_category: Mapped[str] = mapped_column(String(64), nullable=False)
    budget_fit: Mapped[str] = mapped_column(String(32), nullable=False)
    timeline_urgency: Mapped[str] = mapped_column(String(32), nullable=False)
    ai_summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_routing: Mapped[str] = mapped_column(String(64), nullable=False)
    cited_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="qualification")  # type: ignore[name-defined] # noqa: F821


class AIClassification(Base):
    __tablename__ = "ai_classifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    classification: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )