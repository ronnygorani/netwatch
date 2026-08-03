"""Human authentication: password hashing and JWT issue/verify.

Services use API keys (app/auth.py); people log in and carry a short-lived
signed token. Both end up as an identity the audit log can name.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

# Ordered: a role satisfies any requirement at or below its level.
ROLE_LEVELS = {"viewer": 0, "operator": 1, "approver": 2, "admin": 3}

_PBKDF2_ROUNDS = 600_000  # OWASP guidance for PBKDF2-HMAC-SHA256

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), expected)


def create_access_token(user: User) -> str:
    payload = {
        "sub": user.username,
        "role": user.role,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise unauthorized
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise unauthorized from None

    user = db.query(User).filter(User.username == payload.get("sub")).first()
    # Deactivation takes effect immediately, even on an unexpired token.
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_role(minimum: str):
    """Dependency factory: `Depends(require_role("approver"))`."""

    def _check(user: User = Depends(current_user)) -> User:
        if ROLE_LEVELS[user.role] < ROLE_LEVELS[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{minimum}' or higher; you are '{user.role}'",
            )
        return user

    return _check
