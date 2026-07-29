from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_scope
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.device import Device
from app.models.metric import Metric
from app.schemas.metric import MetricCreate, MetricResponse
from app.schemas.pagination import Page

router = APIRouter(tags=["metrics"])


@router.post("/metrics", response_model=MetricResponse, status_code=status.HTTP_201_CREATED)
def ingest_metric(
    payload: MetricCreate,
    db: Session = Depends(get_db),
    _key: ApiKey = Depends(require_scope("metrics:write")),
):
    device = db.query(Device).filter(Device.id == payload.device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    metric = Metric(**payload.model_dump())
    db.add(metric)
    try:
        db.commit()
    except IntegrityError:
        # Device can be deleted between the check and the commit (FM-A3).
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        ) from None
    db.refresh(metric)
    return metric


@router.get("/devices/{device_id}/metrics", response_model=Page[MetricResponse])
def get_device_metrics(
    device_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    query = db.query(Metric).filter(Metric.device_id == device_id)
    total = query.count()
    items = query.order_by(Metric.collected_at.desc()).offset(offset).limit(limit).all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/metrics/latest", response_model=Page[MetricResponse])
def get_latest_metrics(db: Session = Depends(get_db)):
    # Rank per device and take rank 1. The id tiebreak matters: two metrics can
    # share a collected_at timestamp, and a max() join would return both (FM-E6).
    ranked = select(
        Metric.id,
        func.row_number()
        .over(
            partition_by=Metric.device_id,
            order_by=[Metric.collected_at.desc(), Metric.id.desc()],
        )
        .label("rank"),
    ).subquery()
    items = db.query(Metric).join(ranked, (Metric.id == ranked.c.id) & (ranked.c.rank == 1)).all()
    # Bounded by device count; envelope kept for consistency, not paged.
    return Page(items=items, total=len(items), limit=len(items) or 1, offset=0)
