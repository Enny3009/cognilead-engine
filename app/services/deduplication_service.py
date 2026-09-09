from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
import re
from typing import Any
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import Company
from app.models.lead import Lead, LeadActivity

PUBLIC_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "mail.com",
    "protonmail.com",
}


@dataclass
class DeduplicationResult:
    action: str  # "MERGED_TIER_1", "LINKED_TIER_2", "LINKED_TIER_3", "FLAGGED_TIER_4", "CREATED_NEW"
    lead: Lead
    matched_existing: bool
    review_flag: bool = False
    details: str = ""


class DeduplicationService:
    """
    Progressive Deduplication Hierarchy:
    - Tier 1: Exact Normalized Email Match (re-engagement, updates activity)
    - Tier 2: E.164 Normalized Phone Match
    - Tier 3: Corporate Domain Match + Company Entity Mapping
    - Tier 4: Fuzzy Levenshtein Distance (> 0.85 similarity flags for manual review)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def normalize_phone(phone: str | None) -> str | None:
        if not phone:
            return None
        cleaned = re.sub(r"[^\d+]", "", phone.strip())
        if not cleaned.startswith("+") and len(cleaned) == 10:
            cleaned = "+1" + cleaned
        return cleaned

    @staticmethod
    def extract_corporate_domain(email: str) -> str | None:
        parts = email.strip().lower().split("@")
        if len(parts) == 2:
            domain = parts[1]
            if domain not in PUBLIC_EMAIL_DOMAINS:
                return domain
        return None

    @staticmethod
    def similarity_ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()

    async def evaluate_and_deduplicate(
        self,
        organization_id: uuid.UUID,
        source_id: uuid.UUID,
        raw_payload: dict[str, Any],
        campaign_id: uuid.UUID | None = None,
    ) -> DeduplicationResult:
        # Extract normalized attributes
        email = self.normalize_email(raw_payload.get("email", ""))
        phone = self.normalize_phone(raw_payload.get("phone"))
        first_name = raw_payload.get("first_name", "").strip() or None
        last_name = raw_payload.get("last_name", "").strip() or None
        company_name = raw_payload.get("company_name", "").strip() or None
        job_title = raw_payload.get("job_title", "").strip() or None
        country = raw_payload.get("country", "").strip().upper()[:2] or None
        city = raw_payload.get("city", "").strip() or None
        industry = raw_payload.get("industry", "").strip() or None
        company_size = raw_payload.get("company_size", "").strip() or None
        message = raw_payload.get("message", "").strip() or None

        normalized_data = {
            "email": email,
            "phone": phone,
            "first_name": first_name,
            "last_name": last_name,
            "company_name": company_name,
            "job_title": job_title,
            "country": country,
            "city": city,
            "industry": industry,
            "company_size": company_size,
            "message": message,
        }

        # --- Tier 1: Exact Email Match ---
        stmt_t1 = select(Lead).where(
            Lead.organization_id == organization_id,
            Lead.email == email,
        )
        res_t1 = await self.db.execute(stmt_t1)
        existing_lead = res_t1.scalar_one_or_none()

        if existing_lead:
            existing_lead.last_contacted_at = datetime.now(timezone.utc)
            existing_lead.normalized_data = {**existing_lead.normalized_data, **normalized_data}

            activity = LeadActivity(
                lead_id=existing_lead.id,
                activity_type="RE_ENGAGED",
                description="Lead re-submitted form or campaign conversion event.",
                metadata_={"source_id": str(source_id), "raw_payload": raw_payload},
            )
            self.db.add(activity)
            await self.db.flush()

            return DeduplicationResult(
                action="MERGED_TIER_1",
                lead=existing_lead,
                matched_existing=True,
                details=f"Exact match on email: {email}",
            )

        # --- Tier 2: E.164 Phone Match ---
        if phone:
            stmt_t2 = select(Lead).where(
                Lead.organization_id == organization_id,
                Lead.phone == phone,
            )
            res_t2 = await self.db.execute(stmt_t2)
            existing_lead_phone = res_t2.scalar_one_or_none()

            if existing_lead_phone:
                activity = LeadActivity(
                    lead_id=existing_lead_phone.id,
                    activity_type="PHONE_MATCH_LINKED",
                    description=f"Inbound submission matched existing contact by phone ({phone}).",
                    metadata_={"matched_email": email, "raw_payload": raw_payload},
                )
                self.db.add(activity)
                await self.db.flush()

                return DeduplicationResult(
                    action="LINKED_TIER_2",
                    lead=existing_lead_phone,
                    matched_existing=True,
                    details=f"E.164 phone match: {phone}",
                )

        # --- Tier 3: Domain & Company Match ---
        corp_domain = self.extract_corporate_domain(email)
        matched_company: Company | None = None

        if corp_domain:
            stmt_company = select(Company).where(
                Company.organization_id == organization_id,
                Company.domain == corp_domain,
            )
            res_comp = await self.db.execute(stmt_company)
            matched_company = res_comp.scalar_one_or_none()

            if not matched_company and company_name:
                matched_company = Company(
                    organization_id=organization_id,
                    name=company_name,
                    domain=corp_domain,
                    industry=industry,
                    company_size=company_size,
                )
                self.db.add(matched_company)
                await self.db.flush()

        # --- Tier 4: Fuzzy Levenshtein Distance Detection ---
        requires_manual_review = False
        full_name = f"{first_name or ''} {last_name or ''}".strip()

        if full_name and company_name:
            stmt_candidates = (
                select(Lead)
                .where(
                    Lead.organization_id == organization_id,
                    Lead.company_name.isnot(None),
                )
                .limit(50)
            )
            res_candidates = await self.db.execute(stmt_candidates)
            candidates = res_candidates.scalars().all()

            for cand in candidates:
                cand_name = f"{cand.first_name or ''} {cand.last_name or ''}".strip()
                cand_comp = cand.company_name or ""

                name_sim = self.similarity_ratio(full_name, cand_name)
                comp_sim = self.similarity_ratio(company_name, cand_comp)

                if (name_sim * 0.5 + comp_sim * 0.5) > 0.85:
                    requires_manual_review = True
                    break

        # Create New Lead Record
        lead_status = "VALIDATING" if requires_manual_review else "NEW"

        new_lead = Lead(
            organization_id=organization_id,
            source_id=source_id,
            campaign_id=campaign_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            company_name=company_name or (matched_company.name if matched_company else None),
            job_title=job_title,
            country=country,
            city=city,
            industry=industry,
            company_size=company_size,
            message=message,
            raw_data=raw_payload,
            normalized_data=normalized_data,
            status=lead_status,
            score=0,
        )
        self.db.add(new_lead)
        await self.db.flush()

        # Record Initial Ingestion Activity
        activity = LeadActivity(
            lead_id=new_lead.id,
            activity_type="CREATED",
            description="Lead ingested from webhook pipeline.",
            metadata_={
                "source_id": str(source_id),
                "review_flag": requires_manual_review,
                "matched_company_id": str(matched_company.id) if matched_company else None,
            },
        )
        self.db.add(activity)
        await self.db.flush()

        return DeduplicationResult(
            action="FLAGGED_TIER_4" if requires_manual_review else "CREATED_NEW",
            lead=new_lead,
            matched_existing=False,
            review_flag=requires_manual_review,
            details="New lead provisioned with activity ledger",
        )