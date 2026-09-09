from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead, LeadActivity, LeadScore
from app.services.deduplication_service import PUBLIC_EMAIL_DOMAINS


@dataclass
class ScoringResult:
    lead_id: uuid.UUID
    total_score: int
    previous_score: int | None
    breakdown: dict[str, int]
    scoring_method: str = "RULE_BASED"


class ScoringService:
    """
    Deterministic Lead Scoring Engine (0-100).
    Evaluates title seniority, company size, email legitimacy, and commercial intent.
    """

    EXECUTIVE_TITLES = {"vp", "vice president", "director", "head of", "c-level", "chief", "founder", "co-founder", "partner"}
    MANAGEMENT_TITLES = {"manager", "lead", "principal", "supervisor"}
    INTENT_KEYWORDS = {"demo", "pricing", "procure", "enterprise", "quote", "pilot", "trial", "contract", "rfp"}

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def is_business_email(self, email: str) -> bool:
        parts = email.strip().lower().split("@")
        if len(parts) == 2:
            domain = parts[1]
            return domain not in PUBLIC_EMAIL_DOMAINS
        return False

    def evaluate_job_title(self, job_title: str | None) -> tuple[int, str | None]:
        if not job_title:
            return 0, None
        title_lower = job_title.lower()

        for term in self.EXECUTIVE_TITLES:
            if re.search(rf"\b{re.escape(term)}\b", title_lower):
                return 25, "senior_executive"

        for term in self.MANAGEMENT_TITLES:
            if re.search(rf"\b{re.escape(term)}\b", title_lower):
                return 15, "management"

        return 5, "individual_contributor"

    def evaluate_company_size(self, size: str | None) -> tuple[int, str | None]:
        if not size:
            return 0, None
        size_clean = size.strip()
        if size_clean in {"500+", "1000+", "1000-5000", "5000+"}:
            return 20, "enterprise"
        elif size_clean in {"50-249", "250-499", "100-499"}:
            return 10, "mid_market"
        elif size_clean in {"1-10", "11-50", "small"}:
            return 5, "sme"
        return 0, None

    def evaluate_intent(self, message: str | None) -> tuple[int, list[str]]:
        if not message:
            return 0, []
        msg_lower = message.lower()
        matched: list[str] = []

        for keyword in self.INTENT_KEYWORDS:
            if re.search(rf"\b{re.escape(keyword)}\b", msg_lower):
                matched.append(keyword)

        if "demo" in matched or "procure" in matched or "rfp" in matched:
            return 25, matched
        elif len(matched) > 0:
            return 15, matched
        return 0, []

    async def calculate_and_persist_score(self, lead_id: uuid.UUID) -> ScoringResult:
        stmt = select(Lead).where(Lead.id == lead_id)
        result = await self.db.execute(stmt)
        lead = result.scalar_one_or_none()

        if not lead:
            raise ValueError(f"Lead with id {lead_id} does not exist.")

        breakdown: dict[str, int] = {}

        # 1. Title Seniority (up to 25 pts)
        title_score, title_cat = self.evaluate_job_title(lead.job_title)
        if title_score > 0:
            breakdown["job_title_seniority"] = title_score

        # 2. Company Size / ICP fit (up to 20 pts)
        size_score, _ = self.evaluate_company_size(lead.company_size)
        if size_score > 0:
            breakdown["company_size_fit"] = size_score

        # 3. Domain Legitimacy (up to 15 pts)
        if self.is_business_email(lead.email):
            breakdown["corporate_business_email"] = 15

        # 4. Intent Keywords (up to 25 pts)
        intent_score, _ = self.evaluate_intent(lead.message)
        if intent_score > 0:
            breakdown["high_intent_message"] = intent_score

        # 5. Completeness Baseline (up to 15 pts)
        completeness = 0
        if lead.phone:
            completeness += 5
        if lead.country:
            completeness += 5
        if lead.company_name:
            completeness += 5
        if completeness > 0:
            breakdown["profile_completeness"] = completeness

        total_score = min(sum(breakdown.values()), 100)
        previous_score = lead.score

        # Update lead entity
        lead.score = total_score
        self.db.add(lead)

        # Upsert LeadScore record
        stmt_score = select(LeadScore).where(LeadScore.lead_id == lead.id)
        res_score = await self.db.execute(stmt_score)
        score_record = res_score.scalar_one_or_none()

        if score_record:
            score_record.previous_score = previous_score
            score_record.score = total_score
            score_record.score_breakdown = breakdown
            score_record.calculated_at = datetime.now(timezone.utc)
            self.db.add(score_record)
        else:
            score_record = LeadScore(
                lead_id=lead.id,
                score=total_score,
                previous_score=None,
                scoring_method="RULE_BASED",
                score_breakdown=breakdown,
            )
            self.db.add(score_record)

        # Record Score Activity Audit
        activity = LeadActivity(
            lead_id=lead.id,
            activity_type="SCORE_CALCULATED",
            description=f"Deterministic score calculated: {total_score}/100.",
            metadata_={
                "score": total_score,
                "previous_score": previous_score,
                "breakdown": breakdown,
            },
        )
        self.db.add(activity)
        await self.db.flush()

        return ScoringResult(
            lead_id=lead.id,
            total_score=total_score,
            previous_score=previous_score,
            breakdown=breakdown,
        )