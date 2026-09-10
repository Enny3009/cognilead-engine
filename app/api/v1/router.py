from fastapi import APIRouter
from app.api.v1 import ai, auth, campaigns, knowledge, lead_sources, leads, webhooks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(lead_sources.router)
api_router.include_router(campaigns.router)
api_router.include_router(leads.router)
api_router.include_router(knowledge.router)
api_router.include_router(ai.router)
api_router.include_router(webhooks.router)