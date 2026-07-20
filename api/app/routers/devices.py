from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_scope
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate
from app.schemas.pagination import Page

router = APIRouter(prefix="/devices", tags=["devices"])

# Writes require devices:write; reads stay open until human auth (Phase 6).


@router.get("", response_model=Page[DeviceResponse])
def list_devices(
    site: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Device)
    if site:
        query = query.filter(Device.site == site)
    total = query.count()
    items = query.order_by(Device.site, Device.hostname).offset(offset).limit(limit).all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    _key: ApiKey = Depends(require_scope("devices:write")),
):
    existing = db.query(Device).filter(Device.ip_address == str(payload.ip_address)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with IP {payload.ip_address} already exists",
        )
    device = Device(**payload.model_dump(mode="json"))
    db.add(device)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent create with the same IP can slip past the check (FM-A2).
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with IP {payload.ip_address} already exists",
        ) from None
    db.refresh(device)
    return device


@router.patch("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    _key: ApiKey = Depends(require_scope("devices:write")),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    if device.nautobot_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device is managed by the source of truth; make changes in Nautobot",
        )
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(device, field, value)
    db.commit()
    db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    _key: ApiKey = Depends(require_scope("devices:write")),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    # Active SoT rows are Nautobot's to remove; deactivated ones may be
    # cleaned up locally after they leave the SoT.
    if device.nautobot_id is not None and device.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device is managed by the source of truth; remove it in Nautobot",
        )
    db.delete(device)
    db.commit()
