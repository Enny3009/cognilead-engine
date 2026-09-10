from datetime import datetime, timezone
from typing import Any
import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class Integration(Base, TenantMixin, TimestampMixin):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_type: Mapped[str] = mapped_column(String(32), nullable=False)  # SALESFORCE, HUBSPOT, ZOHO, MOCK_CRM
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    credentials: Mapped["IntegrationCredential | None"] = relationship(
        "IntegrationCredential", back_populates="integration", cascade="all, delete-orphan", uselist=False
    )


class IntegrationCredential(Base):
    __tablename__ = "integration_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    credential_type: Mapped[str] = mapped_column(String(32), nullable=False)  # API_KEY, BEARER_TOKEN, OAUTH2_TOKENS
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    integration: Mapped["Integration"] = relationship("Integration", back_populates="credentials")


class IntegrationEndpoint(Base, TenantMixin, TimestampMixin):
    __tablename__ = "integration_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    circuit_state: Mapped[str] = mapped_column(String(16), default="CLOSED", nullable=False)  # CLOSED, OPEN, HALF_OPEN
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deliveries: Mapped[list["IntegrationDelivery"]] = relationship("IntegrationDelivery", back_populates="endpoint")


class IntegrationDelivery(Base):
    __tablename__ = "integration_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integration_endpoints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delivery_status: Mapped[str] = mapped_column(String(32), default="QUEUED", nullable=False)  # QUEUED, DELIVERED, FAILED, DEAD_LETTER
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    endpoint: Mapped["IntegrationEndpoint"] = relationship("IntegrationEndpoint", back_populates="deliveries")


class ExternalCRMRecord(Base, TenantMixin, TimestampMixin):
    __tablename__ = "external_crm_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_record_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    record_type: Mapped[str] = mapped_column(String(32), default="CONTACT", nullable=False)
    sync_status: Mapped[str] = mapped_column(String(32), default="SYNCED", nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )