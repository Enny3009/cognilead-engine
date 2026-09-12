from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import uuid
from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class AttributionTouchpoint(Base, TimestampMixin):
    __tablename__ = "attribution_touchpoints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(64), nullable=False)  # PAID_SEARCH, PAID_SOCIAL, ORGANIC_SEARCH, DIRECT, EMAIL
    touchpoint_type: Mapped[str] = mapped_column(String(32), nullable=False)  # FIRST_TOUCH, INTERMEDIATE, LAST_TOUCH
    utm_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(100), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    lead: Mapped["Lead"] = relationship("Lead")  # type: ignore[name-defined] # noqa: F821


class CampaignAttributionRollup(Base, TenantMixin, TimestampMixin):
    __tablename__ = "campaign_attribution_rollups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    first_touch_credit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    last_touch_credit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    linear_credit: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    attributed_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)