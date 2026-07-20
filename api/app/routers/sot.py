from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_scope
from app.config import settings
from app.database import get_db
from app.models.api_key import ApiKey
from app.nautobot import full_sync, last_sync

router = APIRouter(prefix="/sot", tags=["source-of-truth"])


def run_sync_or_raise(db: Session) -> dict:
    if not settings.nautobot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Source of truth not configured (NAUTOBOT_TOKEN is empty)",
        )
    try:
        return full_sync(db)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Nautobot unreachable: {exc}",
        ) from None


@router.post("/sync")
def sync_from_nautobot(
    db: Session = Depends(get_db),
    _key: ApiKey = Depends(require_scope("sot:sync")),
):
    return run_sync_or_raise(db)


@router.get("/status")
def sot_status():
    return {"configured": bool(settings.nautobot_token), **last_sync}
