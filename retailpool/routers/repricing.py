"""
Kaspi-bot repricing API endpoints.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/repricing", tags=["Repricing Bot"])

@router.get("/status")
async def get_bot_status():
    """Get the current status of the repricing bot."""
    return {"status": "active", "last_run": "2 seconds ago"}

@router.post("/rules")
async def update_rules(data: dict):
    """Update repricing rules."""
    return {"success": True, "rules": data}

@router.get("/log")
async def get_repricing_log():
    """Get the history of price changes."""
    return []
