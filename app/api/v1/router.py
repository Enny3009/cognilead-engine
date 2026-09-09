from fastapi import APIRouter
from app.api.v1 import auth, campaigns, lead_sources, webhooks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(lead_sources.router)
api_router.include_router(campaigns.router)
api_router.include_router(webhooks.router)