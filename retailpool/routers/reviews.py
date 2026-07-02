"""
Reviews API endpoints.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])

@router.get("/")
async def get_reviews():
    """Get all reviews."""
    return []

@router.post("/{review_id}/reply")
async def reply_to_review(review_id: str, data: dict):
    """Reply to a specific review."""
    return {"success": True, "reply": data.get("reply")}
