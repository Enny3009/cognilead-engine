import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import TenantContext
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.schemas.knowledge import (
    DocumentCreate,
    DocumentRead,
    SemanticSearchQuery,
    SemanticSearchResult,
)
from app.services.rag_service import RAGService

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base & RAG"])


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED, summary="Upload & Embed Document")
async def create_document(
    payload: DocumentCreate,
    tenant: TenantContext = Depends(),
) -> DocumentRead:
    rag_service = RAGService(tenant.db)
    doc = await rag_service.ingest_document(
        organization_id=tenant.organization_id,
        title=payload.title,
        category=payload.category.value,
        raw_content=payload.raw_content,
    )

    # Count generated chunks
    count_stmt = select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.document_id == doc.id)
    res = await tenant.db.execute(count_stmt)
    chunks_count = res.scalar() or 0

    return DocumentRead(
        id=doc.id,
        organization_id=doc.organization_id,
        title=doc.title,
        category=doc.category,
        is_active=doc.is_active,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        chunk_count=chunks_count,
    )


@router.get("/documents", response_model=list[DocumentRead], summary="List Knowledge Documents")
async def list_documents(
    tenant: TenantContext = Depends(),
) -> list[DocumentRead]:
    stmt = (
        select(
            KnowledgeDocument,
            func.count(KnowledgeChunk.id).label("chunk_count"),
        )
        .outerjoin(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeDocument.organization_id == tenant.organization_id)
        .group_by(KnowledgeDocument.id)
        .order_by(KnowledgeDocument.created_at.desc())
    )
    result = await tenant.db.execute(stmt)
    rows = result.all()

    return [
        DocumentRead(
            id=doc.id,
            organization_id=doc.organization_id,
            title=doc.title,
            category=doc.category,
            is_active=doc.is_active,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            chunk_count=count,
        )
        for doc, count in rows
    ]


@router.post("/search", response_model=list[SemanticSearchResult], summary="Execute pgvector Cosine Similarity Search")
async def search_knowledge(
    payload: SemanticSearchQuery,
    tenant: TenantContext = Depends(),
) -> list[SemanticSearchResult]:
    rag_service = RAGService(tenant.db)
    return await rag_service.similarity_search(
        organization_id=tenant.organization_id,
        query=payload.query,
        limit=payload.limit,
    )