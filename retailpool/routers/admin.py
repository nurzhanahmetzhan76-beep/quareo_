from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import get_db
from retailpool.models.user import User
from retailpool.services.auth_service import get_current_user

router = APIRouter(prefix="/api/admin", tags=["Admin"])

ADMIN_EMAIL = "disairon.agent@bk.ru"


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.email != ADMIN_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    plan: str
    created_at: str
    scans_used: int
    wb_scans_used: int
    waybills_used: int
    analytics_used: int

    class Config:
        from_attributes = True


class UpdatePlanRequest(BaseModel):
    plan: str


@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all users."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    # Format created_at to string to avoid datetime serialization issues
    formatted_users = []
    for u in users:
        formatted_users.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "plan": u.plan,
            "created_at": u.created_at.isoformat() if u.created_at else "",
            "scans_used": u.scans_used,
            "wb_scans_used": u.wb_scans_used,
            "waybills_used": u.waybills_used,
            "analytics_used": u.analytics_used,
        })
    return formatted_users


@router.post("/users/{user_id}/plan")
async def update_user_plan(
    user_id: UUID,
    req: UpdatePlanRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a user's subscription plan."""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    valid_plans = ["free", "waybills", "start", "business", "unlimited"]
    if req.plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Must be one of: {', '.join(valid_plans)}")
        
    target_user.plan = req.plan
    await db.commit()
    
    return {"status": "ok", "message": f"Updated {target_user.email} to plan {req.plan}"}
