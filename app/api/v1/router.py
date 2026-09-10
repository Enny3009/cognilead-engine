from fastapi import APIRouter
from app.api.v1 import (
    ai,
    auth,
    campaigns,
    integrations,
    knowledge,
    lead_sources,
    leads,
    ops,
    webhooks,
    workflows,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(lead_sources.router)
api_router.include_router(campaigns.router)
api_router.include_router(leads.router)
api_router.include_router(knowledge.router)
api_router.include_router(ai.router)
api_router.include_router(workflows.router)
api_router.include_router(integrations.router)
api_router.include_router(ops.router)
api_router.include_router(webhooks.router)