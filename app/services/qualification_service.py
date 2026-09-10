import uuid
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.lead import Lead, LeadActivity
from app.models.qualification import LeadQualification
from app.schemas.qualification import (
    BudgetFitEnum,
    IntentCategoryEnum,
    LeadQualificationOutput,
    TimelineUrgencyEnum,
)
from app.services.rag_service import RAGService


class QualificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.rag = RAGService(db)
        self.is_mock = self.rag.is_mock
        if not self.is_mock:
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def qualify_lead(self, lead_id: uuid.UUID) -> LeadQualification:
        stmt = select(Lead).where(Lead.id == lead_id)
        result = await self.db.execute(stmt)
        lead = result.scalar_one_or_none()

        if not lead:
            raise ValueError(f"Lead {lead_id} not found.")

        search_query = f"{lead.company_name or ''} {lead.job_title or ''} {lead.message or ''}".strip()
        top_chunks = await self.rag.similarity_search(
            organization_id=lead.organization_id,
            query=search_query,
            limit=4,
        )

        cited_chunk_ids = [chunk.chunk_id for chunk in top_chunks]

        if self.is_mock:
            # Deterministic mock evaluation based on deterministic score
            is_qualified = lead.score >= 70
            parsed_output = LeadQualificationOutput(
                qualification_score=lead.score,
                is_qualified=is_qualified,
                intent_category=IntentCategoryEnum.ENTERPRISE_INQUIRY if is_qualified else IntentCategoryEnum.GENERAL_PRICING,
                budget_fit=BudgetFitEnum.HIGH_FIT if is_qualified else BudgetFitEnum.MODERATE_FIT,
                timeline_urgency=TimelineUrgencyEnum.IMMEDIATE if is_qualified else TimelineUrgencyEnum.EXPLORATORY,
                ai_summary=(
                    f"Lead {lead.first_name} {lead.last_name} from {lead.company_name} demonstrates high commercial intent "
                    f"with a deterministic score of {lead.score}/100. Evaluated against enterprise documentation."
                ),
                recommended_routing="ENTERPRISE_SALES" if is_qualified else "NURTURE",
                cited_chunk_ids=[str(cid) for cid in cited_chunk_ids],
            )
        else:
            sop_context = "\n---\n".join([
                f"[Chunk ID: {chunk.chunk_id} | Doc: {chunk.document_title}]:\n{chunk.content}"
                for chunk in top_chunks
            ])

            system_prompt = (
                "You are the Lead Qualification AI for an enterprise marketing operations engine. "
                "Analyze the lead using the provided company Standard Operating Procedures (SOPs), "
                "Pricing Models, and ICP documentation. Evaluate intent, budget fit, and urgency. "
                "Cite the Chunk IDs you used to reach your conclusion."
            )

            user_content = f"""
Lead Information:
- Full Name: {lead.first_name} {lead.last_name}
- Email: {lead.email}
- Job Title: {lead.job_title}
- Company: {lead.company_name} (Size: {lead.company_size})
- Inbound Message: {lead.message}
- Deterministic Rule Score: {lead.score}/100

Company Knowledge Base Documentation:
{sop_context if sop_context else "No company SOPs found. Qualify based on standard B2B enterprise heuristics."}
"""

            completion = await self.client.beta.chat.completions.parse(
                model=settings.OPENAI_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format=LeadQualificationOutput,
                temperature=0.1,
            )
            parsed_output = completion.choices[0].message.parsed

        valid_cited_ids = []
        for chunk_id_str in parsed_output.cited_chunk_ids:
            try:
                valid_cited_ids.append(uuid.UUID(chunk_id_str))
            except ValueError:
                continue

        stmt_qual = select(LeadQualification).where(LeadQualification.lead_id == lead.id)
        res_qual = await self.db.execute(stmt_qual)
        qual_record = res_qual.scalar_one_or_none()

        if qual_record:
            qual_record.qualification_score = parsed_output.qualification_score
            qual_record.is_qualified = parsed_output.is_qualified
            qual_record.intent_category = parsed_output.intent_category.value
            qual_record.budget_fit = parsed_output.budget_fit.value
            qual_record.timeline_urgency = parsed_output.timeline_urgency.value
            qual_record.ai_summary = parsed_output.ai_summary
            qual_record.recommended_routing = parsed_output.recommended_routing
            qual_record.cited_chunk_ids = valid_cited_ids
            self.db.add(qual_record)
        else:
            qual_record = LeadQualification(
                lead_id=lead.id,
                qualification_score=parsed_output.qualification_score,
                is_qualified=parsed_output.is_qualified,
                intent_category=parsed_output.intent_category.value,
                budget_fit=parsed_output.budget_fit.value,
                timeline_urgency=parsed_output.timeline_urgency.value,
                ai_summary=parsed_output.ai_summary,
                recommended_routing=parsed_output.recommended_routing,
                cited_chunk_ids=valid_cited_ids,
            )
            self.db.add(qual_record)

        lead.status = "QUALIFIED" if parsed_output.is_qualified else "UNQUALIFIED"
        self.db.add(lead)

        activity = LeadActivity(
            lead_id=lead.id,
            activity_type="AI_QUALIFIED",
            description=f"AI Qualification complete: {parsed_output.intent_category.value} ({parsed_output.budget_fit.value}).",
            metadata_={
                "qualification_score": parsed_output.qualification_score,
                "is_qualified": parsed_output.is_qualified,
                "recommended_routing": parsed_output.recommended_routing,
                "summary": parsed_output.ai_summary,
            },
        )
        self.db.add(activity)
        await self.db.flush()

        return qual_record