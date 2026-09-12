from collections import defaultdict
from decimal import Decimal
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attribution import AttributionTouchpoint, CampaignAttributionRollup
from app.models.campaign import Campaign
from app.models.crm import Contact, Deal
from app.models.lead import Lead
from app.schemas.attribution import (
    AttributionSummaryResponse,
    CampaignPerformanceRead,
    ChannelAttributionShare,
)


class AttributionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_touchpoint(
        self,
        lead_id: uuid.UUID,
        channel: str,
        touchpoint_type: str = "INTERMEDIATE",
        utm_source: str | None = None,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
    ) -> AttributionTouchpoint:
        touchpoint = AttributionTouchpoint(
            lead_id=lead_id,
            channel=channel.upper(),
            touchpoint_type=touchpoint_type.upper(),
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
        )
        self.db.add(touchpoint)
        await self.db.flush()
        return touchpoint

    async def calculate_summary(self, organization_id: uuid.UUID) -> AttributionSummaryResponse:
        # Load all leads and touchpoints for tenant
        stmt = (
            select(AttributionTouchpoint)
            .join(Lead, Lead.id == AttributionTouchpoint.lead_id)
            .where(Lead.organization_id == organization_id)
            .order_by(AttributionTouchpoint.lead_id, AttributionTouchpoint.occurred_at.asc())
        )
        res = await self.db.execute(stmt)
        touchpoints = res.scalars().all()

        if not touchpoints:
            return AttributionSummaryResponse(
                organization_id=organization_id,
                total_touchpoints=0,
                analyzed_leads_count=0,
                channels=[],
            )

        # Group touchpoints by lead
        lead_journeys: dict[uuid.UUID, list[AttributionTouchpoint]] = defaultdict(list)
        channel_counts: dict[str, int] = defaultdict(int)

        for tp in touchpoints:
            lead_journeys[tp.lead_id].append(tp)
            channel_counts[tp.channel] += 1

        first_touch_shares: dict[str, float] = defaultdict(float)
        last_touch_shares: dict[str, float] = defaultdict(float)
        linear_shares: dict[str, float] = defaultdict(float)

        total_leads = len(lead_journeys)

        for _, journey in lead_journeys.items():
            first_channel = journey[0].channel
            last_channel = journey[-1].channel

            first_touch_shares[first_channel] += 1.0
            last_touch_shares[last_channel] += 1.0

            linear_increment = 1.0 / len(journey)
            for tp in journey:
                linear_shares[tp.channel] += linear_increment

        all_channels = sorted(list(channel_counts.keys()))
        shares: list[ChannelAttributionShare] = []

        for ch in all_channels:
            ft_pct = round((first_touch_shares[ch] / total_leads) * 100, 2)
            lt_pct = round((last_touch_shares[ch] / total_leads) * 100, 2)
            lin_pct = round((linear_shares[ch] / total_leads) * 100, 2)

            shares.append(
                ChannelAttributionShare(
                    channel=ch,
                    first_touch_percentage=ft_pct,
                    last_touch_percentage=lt_pct,
                    linear_percentage=lin_pct,
                    total_touchpoints=channel_counts[ch],
                )
            )

        return AttributionSummaryResponse(
            organization_id=organization_id,
            total_touchpoints=len(touchpoints),
            analyzed_leads_count=total_leads,
            channels=shares,
        )

    async def calculate_campaign_performance(self, organization_id: uuid.UUID) -> list[CampaignPerformanceRead]:
        stmt_camps = select(Campaign).where(Campaign.organization_id == organization_id)
        res_camps = await self.db.execute(stmt_camps)
        campaigns = res_camps.scalars().all()

        metrics: list[CampaignPerformanceRead] = []

        for camp in campaigns:
            # Query attributed pipeline deal value from leads linked to this campaign
            stmt_val = (
                select(func.coalesce(func.sum(Deal.value), 0))
                .join(Contact, Contact.id == Deal.contact_id)
                .join(Lead, Lead.id == Contact.lead_id)
                .where(Lead.campaign_id == camp.id)
            )
            res_val = await self.db.execute(stmt_val)
            pipeline_val = res_val.scalar() or Decimal("0.00")

            # Query leads count
            stmt_leads = select(func.count(Lead.id)).where(Lead.campaign_id == camp.id)
            res_leads = await self.db.execute(stmt_leads)
            leads_count = float(res_leads.scalar() or 0)

            metrics.append(
                CampaignPerformanceRead(
                    campaign_id=camp.id,
                    campaign_name=camp.name,
                    campaign_code=camp.campaign_code,
                    budget=camp.budget,
                    first_touch_leads=leads_count,
                    last_touch_leads=leads_count,
                    linear_attributed_leads=leads_count,
                    attributed_pipeline_value=Decimal(str(pipeline_val)),
                )
            )

        return metrics