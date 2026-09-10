from datetime import datetime, timezone
import uuid
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class KnowledgeDocument(Base, TenantMixin, TimestampMixin):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)  # PRICING_GUIDE, SERVICE_CATALOG, ICP, CASE_STUDY
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="document", cascade="all, delete-orphan", order_by="KnowledgeChunk.chunk_index"
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    document: Mapped["KnowledgeDocument"] = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        Index(
            "idx_knowledge_chunks_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )