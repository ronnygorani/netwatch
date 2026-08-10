from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.database import get_db
from app.models.config_template import ConfigTemplate, ConfigVariable
from app.models.device import Device
from app.models.user import User
from app.schemas.pagination import Page
from app.schemas.templating import (
    RenderResponse,
    TemplateCreate,
    TemplateResponse,
    VariableResponse,
    VariableSet,
)
from app.security import require_role
from app.templating import render_for_device, resolve_variables

router = APIRouter(tags=["templating"])


@router.get("/templates", response_model=Page[TemplateResponse])
def list_templates(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(ConfigTemplate).order_by(ConfigTemplate.name)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.put("/templates/{name}", response_model=TemplateResponse)
def upsert_template(
    name: str,
    payload: TemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator")),
):
    if name != payload.name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Path name and body name must match",
        )
    template = db.query(ConfigTemplate).filter(ConfigTemplate.name == name).first()
    if template is None:
        template = ConfigTemplate(name=name)
        db.add(template)
    template.description = payload.description
    template.body = payload.body
    audit.record(
        db,
        actor=user.username,
        actor_type="human",
        action="template.upsert",
        resource=f"templates/{name}",
        request=request,
    )
    db.commit()
    db.refresh(template)
    return template


@router.delete("/templates/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    name: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator")),
):
    template = db.query(ConfigTemplate).filter(ConfigTemplate.name == name).first()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    db.delete(template)
    audit.record(
        db,
        actor=user.username,
        actor_type="human",
        action="template.delete",
        resource=f"templates/{name}",
        request=request,
    )
    db.commit()


@router.get("/variables", response_model=Page[VariableResponse])
def list_variables(db: Session = Depends(get_db)):
    items = db.query(ConfigVariable).order_by(ConfigVariable.scope, ConfigVariable.scope_ref).all()
    return Page(items=items, total=len(items), limit=len(items) or 1, offset=0)


@router.put("/variables", response_model=VariableResponse)
def set_variables(
    payload: VariableSet,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("operator")),
):
    """Replace the variable set at one scope. Ansible group_vars, as an endpoint."""
    if payload.scope == "device" and db.get(Device, int(payload.scope_ref or 0)) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown device id"
        )

    row = (
        db.query(ConfigVariable)
        .filter(
            ConfigVariable.scope == payload.scope, ConfigVariable.scope_ref == payload.scope_ref
        )
        .first()
    )
    if row is None:
        row = ConfigVariable(scope=payload.scope, scope_ref=payload.scope_ref)
        db.add(row)
    row.data = payload.data
    row.updated_at = datetime.now(UTC)
    audit.record(
        db,
        actor=user.username,
        actor_type="human",
        action="variables.set",
        resource=f"variables/{payload.scope}/{payload.scope_ref or 'all'}",
        request=request,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Variable scope already exists"
        ) from None
    db.refresh(row)
    return row


@router.get("/devices/{device_id}/variables")
def get_resolved_variables(device_id: int, db: Session = Depends(get_db)):
    """The merged result for one device. Answers 'why does this device have this value?'"""
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return {
        "device_id": device.id,
        "hostname": device.hostname,
        "variables": resolve_variables(db, device),
    }


@router.post("/templates/{name}/render", response_model=list[RenderResponse])
def render_template(
    name: str,
    device_ids: list[int],
    db: Session = Depends(get_db),
):
    """Preview what a template produces per device, before proposing a change."""
    template = db.query(ConfigTemplate).filter(ConfigTemplate.name == name).first()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    devices = db.query(Device).filter(Device.id.in_(device_ids)).all()
    if len(devices) != len(set(device_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown device ids"
        )
    try:
        return [
            RenderResponse(
                device_id=d.id, hostname=d.hostname, rendered=render_for_device(db, template, d)
            )
            for d in devices
        ]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None
