from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserResponse
from app.security import (
    create_access_token,
    current_user,
    hash_password,
    require_role,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form.username).first()
    # One message for both cases: revealing which half was wrong helps attackers
    # enumerate usernames.
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in_minutes=settings.jwt_expire_minutes,
    )


@router.get("/me", response_model=UserResponse)
def read_me(user: User = Depends(current_user)):
    return user


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    audit.record(
        db,
        actor=admin.username,
        actor_type="human",
        action="user.create",
        resource=f"users/{payload.username}",
        detail={"role": payload.role},
        request=request,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
        ) from None
    db.refresh(user)
    return user
