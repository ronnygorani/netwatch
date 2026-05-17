from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.metric import Metric
from app.schemas.metric import MetricCreate, MetricResponse

router = APIRouter(tags=["metrics"])


@router.post("/metrics", response_model=MetricResponse, status_code=status.HTTP_201_CREATED)
def ingest_metric(payload: MetricCreate, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == payload.device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    metric = Metric(**payload.model_dump())
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


@router.get("/devices/{device_id}/metrics", response_model=list[MetricResponse])
def get_device_metrics(
    device_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return (
        db.query(Metric)
        .filter(Metric.device_id == device_id)
        .order_by(Metric.collected_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/metrics/latest", response_model=list[MetricResponse])
def get_latest_metrics(db: Session = Depends(get_db)):
    subquery = (
        db.query(
            Metric.device_id,
            func.max(Metric.collected_at).label("max_collected_at"),
        )
        .group_by(Metric.device_id)
        .subquery()
    )
    return (
        db.query(Metric)
        .join(
            subquery,
            (Metric.device_id == subquery.c.device_id)
            & (Metric.collected_at == subquery.c.max_collected_at),
        )
        .all()
    )
