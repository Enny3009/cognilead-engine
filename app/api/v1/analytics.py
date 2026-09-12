from decimal import Decimal
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import TenantContext
from app.models.crm import Deal
from app.models.lead import Lead

router = APIRouter(prefix="/analytics", tags=["Analytics & Dashboard"])


class DashboardSummary(BaseModel):
    total_leads: int
    qualified_leads: int
    qualification_rate_percentage: float
    total_pipeline_value: Decimal
    average_lead_score: float


@router.get("/summary", response_model=DashboardSummary, summary="Executive KPI Dashboard Summary")
async def get_dashboard_summary(
    tenant: TenantContext = Depends(),
) -> DashboardSummary:
    # Total Leads
    stmt_total = select(func.count(Lead.id)).where(Lead.organization_id == tenant.organization_id)
    res_total = await tenant.db.execute(stmt_total)
    total_leads = res_total.scalar() or 0

    # Qualified Leads
    stmt_qual = select(func.count(Lead.id)).where(
        Lead.organization_id == tenant.organization_id, Lead.status == "QUALIFIED"
    )
    res_qual = await tenant.db.execute(stmt_qual)
    qualified_leads = res_qual.scalar() or 0

    # Average Score
    stmt_avg = select(func.coalesce(func.avg(Lead.score), 0.0)).where(Lead.organization_id == tenant.organization_id)
    res_avg = await tenant.db.execute(stmt_avg)
    avg_score = round(float(res_avg.scalar() or 0.0), 1)

    # Pipeline Value
    stmt_deal = select(func.coalesce(func.sum(Deal.value), Decimal("0.00"))).where(
        Deal.organization_id == tenant.organization_id
    )
    res_deal = await tenant.db.execute(stmt_deal)
    total_pipeline = res_deal.scalar() or Decimal("0.00")

    rate = round((qualified_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

    return DashboardSummary(
        total_leads=total_leads,
        qualified_leads=qualified_leads,
        qualification_rate_percentage=rate,
        total_pipeline_value=Decimal(str(total_pipeline)),
        average_lead_score=avg_score,
    )

@router.get("/leads")
async def get_lead_analytics():
    return {"status": "Not Implemented"}