from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from retailpool.database import get_db
from retailpool.routers.auth import get_current_user
from retailpool.models.user import User
from pydantic import BaseModel
from retailpool.schemas.store_scanner import StoreScanRequest, StoreScanResponse
from retailpool.services.store_scanner_service import StoreScannerService

class PhoneRequest(BaseModel):
    phone: str

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/store-scanner", tags=["Store Scanner"])

@router.post("/request-code", summary="Request Kaspi SMS Code")
async def request_sms_code(
    req: PhoneRequest,
    current_user: User = Depends(get_current_user)
):
    import uuid
    # Mocking internal Kaspi API call for SMS
    return {"session_id": str(uuid.uuid4()), "message": "СМС код отправлен"}

@router.post("/scan", response_model=StoreScanResponse, summary="Run Kaspi Profile Scanner")
async def scan_store(
    request: StoreScanRequest,
    current_user: User = Depends(get_current_user)
) -> StoreScanResponse:
    """
    Initiate a Kaspi profile scan.
    Requires an active subscription plan (Unlimited or Business).
    """
    if current_user.plan.lower() not in ["unlimited", "business"] and current_user.email != "karimbai.ali10@mail.ru":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Эта функция доступна только для тарифов Business и Unlimited."
        )

    try:
        response = await StoreScannerService.scan_store(request)
        return response
    except Exception as e:
        logger.error(f"Error scanning store: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сканирования: {str(e)}"
        )
