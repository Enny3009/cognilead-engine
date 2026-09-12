from fastapi import APIRouter
router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/")
async def list_notifications():
    return {"status": "Not Implemented"}