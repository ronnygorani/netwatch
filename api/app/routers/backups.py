from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.auth import require_scope
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.config_backup import ConfigBackup
from app.models.device import Device
from app.schemas.job import BackupSummary
from app.schemas.pagination import Page

router = APIRouter(tags=["backups"])


@router.get("/devices/{device_id}/backups", response_model=Page[BackupSummary])
def list_backups(
    device_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    if db.get(Device, device_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    query = (
        db.query(ConfigBackup)
        .filter(ConfigBackup.device_id == device_id)
        .order_by(ConfigBackup.taken_at.desc())
    )
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/backups/{backup_id}", response_class=PlainTextResponse)
def get_backup_content(
    backup_id: int,
    db: Session = Depends(get_db),
    # Config content holds secrets (password hashes); reading it is scoped.
    _key: ApiKey = Depends(require_scope("backups:read")),
):
    backup = db.get(ConfigBackup, backup_id)
    if backup is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found")
    return backup.content
