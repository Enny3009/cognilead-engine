from fastapi import APIRouter
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary")
async def get_dashboard_summary():
    return {"status": "Not Implemented"}