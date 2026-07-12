"""API-key authentication for service identities (X-API-Key header).

Keys are stored as SHA-256 hashes only. Human auth (JWT) lands in Phase 6.
"""

import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.api_key import ApiKey
from app.rate_limit import limiter

# auto_error=False so a missing header returns our 401, not FastAPI's generic 403.
_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

KEY_PREFIX = "nwk_"


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def require_scope(scope: str):
    """Dependency factory: 401 for unknown/revoked keys, 403 for missing scope."""

    def _check(
        raw_key: str | None = Security(_header_scheme),
        db: Session = Depends(get_db),
    ) -> ApiKey:
        if not raw_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-API-Key header",
            )
        record = (
            db.query(ApiKey)
            .filter(ApiKey.key_hash == hash_key(raw_key), ApiKey.is_active.is_(True))
            .first()
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key",
            )
        if scope not in record.scopes.split():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key '{record.name}' lacks required scope '{scope}'",
            )
        # Keyed by hash, not name: unique per credential.
        if not limiter.allow(record.key_hash, settings.rate_limit_per_minute):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for API key '{record.name}'",
            )
        # Persisted by the route's commit — tracks successful use only.
        record.last_used_at = datetime.now(UTC)
        return record

    return _check
