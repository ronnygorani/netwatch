from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceResponse])
def list_devices(site: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Device)
    if site:
        query = query.filter(Device.site == site)
    return query.order_by(Device.site, Device.hostname).all()


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)):
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
        # The check above is a race (FM-A2): two concurrent creates with the
        # same IP can both pass it. The DB unique constraint is the real
        # guard — translate its violation to the same 409 the contract promises.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with IP {payload.ip_address} already exists",
        ) from None
    db.refresh(device)
    return device


@router.patch("/{device_id}", response_model=DeviceResponse)
def update_device(device_id: int, payload: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(device, field, value)
    db.commit()
    db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    db.delete(device)
    db.commit()
