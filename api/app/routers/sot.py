from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_scope
from app.config import settings
from app.database import get_db
from app.models.api_key import ApiKey
from app.nautobot import fetch_nautobot_devices, map_nautobot_device, sync_devices

router = APIRouter(prefix="/sot", tags=["source-of-truth"])


@router.post("/sync")
def sync_from_nautobot(
    db: Session = Depends(get_db),
    _key: ApiKey = Depends(require_scope("sot:sync")),
):
    if not settings.nautobot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Source of truth not configured (NAUTOBOT_TOKEN is empty)",
        )
    try:
        nb_devices = fetch_nautobot_devices()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Nautobot unreachable: {exc}",
        ) from None

    mapped = [m for d in nb_devices if (m := map_nautobot_device(d))]
    counts = sync_devices(db, mapped)
    counts["skipped"] = len(nb_devices) - len(mapped)
    return counts
