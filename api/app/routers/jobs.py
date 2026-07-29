from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import require_scope
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.job import Job
from app.queue import enqueue_job
from app.schemas.job import JobCreate, JobResponse
from app.schemas.pagination import Page

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    key: ApiKey = Depends(require_scope("jobs:run")),
):
    # Persist first, enqueue second: the row is the source of truth, the queue
    # is just a nudge. A worker that never runs still leaves an audit trail.
    job = Job(type=payload.type, params=payload.params, requested_by=key.name)
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_job(job.id)
    return job


@router.get("", response_model=Page[JobResponse])
def list_jobs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Job).order_by(Job.id.desc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
