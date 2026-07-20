import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers.sot import run_sync_or_raise

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/nautobot")
async def nautobot_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive change events from the SoT and resync immediately.

    Authenticated by HMAC signature over the body (X-Hook-Signature), not an
    API key: proves the message came from Nautobot and was not altered.
    Idempotent because the sync is; duplicate deliveries are harmless.
    """
    if not settings.nautobot_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )

    body = await request.body()
    expected = hmac.new(settings.nautobot_webhook_secret.encode(), body, hashlib.sha512).hexdigest()
    provided = request.headers.get("X-Hook-Signature", "")
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature"
        )

    try:
        event = json.loads(body)
        logger.info("Nautobot webhook: %s %s", event.get("event"), event.get("model"))
    except (ValueError, AttributeError):
        pass  # payload is informational; the sync reconciles everything anyway

    return run_sync_or_raise(db)
