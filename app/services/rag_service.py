import hashlib
import math
import random
import uuid
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.schemas.knowledge import SemanticSearchResult


class RAGService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.is_mock = (
            not settings.OPENAI_API_KEY
            or settings.OPENAI_API_KEY.startswith("sk-proj-your")
            or settings.OPENAI_API_KEY == "mock"
        )
        if not self.is_mock:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    @staticmethod
    def chunk_text(content: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
        content = content.strip()
        if len(content) <= max_chars:
            return [content]

        chunks = []
        start = 0
        while start < len(content):
            end = start + max_chars
            chunk = content[start:end]
            chunks.append(chunk)
            start += max_chars - overlap
        return chunks

    def _generate_mock_embedding(self, input_text: str) -> list[float]:
        # Generates deterministic normalized 1536-dim vector seeded on text hash
        seed = int(hashlib.sha256(input_text.encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed)
        raw = [rng.uniform(-1.0, 1.0) for _ in range(1536)]
        magnitude = math.sqrt(sum(x * x for x in raw))
        return [x / magnitude for x in raw]

    async def generate_embedding(self, input_text: str) -> list[float]:
        if self.is_mock:
            return self._generate_mock_embedding(input_text)

        clean_text = input_text.replace("\n", " ")
        response = await self.client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=clean_text,
        )
        return response.data[0].embedding

    async def ingest_document(
        self,
        organization_id: uuid.UUID,
        title: str,
        category: str,
        raw_content: str,
    ) -> KnowledgeDocument:
        doc = KnowledgeDocument(
            organization_id=organization_id,
            title=title.strip(),
            category=category,
            is_active=True,
        )
        self.db.add(doc)
        await self.db.flush()

        chunks_text = self.chunk_text(raw_content)

        for index, chunk_str in enumerate(chunks_text):
            embedding = await self.generate_embedding(chunk_str)
            approx_tokens = math.ceil(len(chunk_str) / 4)

            chunk = KnowledgeChunk(
                document_id=doc.id,
                content=chunk_str,
                token_count=approx_tokens,
                chunk_index=index,
                embedding=embedding,
            )
            self.db.add(chunk)

        await self.db.flush()
        return doc

    async def similarity_search(
        self,
        organization_id: uuid.UUID,
        query: str,
        limit: int = 4,
    ) -> list[SemanticSearchResult]:
        query_vector = await self.generate_embedding(query)
        vector_str = f"[{','.join(str(x) for x in query_vector)}]"

        sql = text("""
            SELECT 
                kc.id AS chunk_id,
                kc.document_id,
                kd.title AS document_title,
                kc.content,
                1 - (kc.embedding <=> CAST(:query_vector AS vector)) AS similarity
            FROM knowledge_chunks kc
            JOIN knowledge_documents kd ON kc.document_id = kd.id
            WHERE kd.organization_id = :org_id AND kd.is_active = TRUE
            ORDER BY kc.embedding <=> CAST(:query_vector AS vector)
            LIMIT :limit;
        """)

        result = await self.db.execute(
            sql,
            {"query_vector": vector_str, "org_id": organization_id, "limit": limit},
        )
        rows = result.fetchall()

        return [
            SemanticSearchResult(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                document_title=row.document_title,
                content=row.content,
                similarity=float(row.similarity),
            )
            for row in rows
        ]