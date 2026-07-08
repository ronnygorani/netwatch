import platform
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import __version__
from app.config import settings
from app.database import check_db_connection

router = APIRouter(prefix="/health", tags=["health"])

_start_time = time.time()


class HealthResponse(BaseModel):
    status: str
    environment: str
    uptime_seconds: float
    database: str
    python_version: str
    version: str


@router.get("", response_model=HealthResponse)
def health_check():
    """Return the operational status of the API and its dependencies.

    Returns HTTP 200 when healthy, HTTP 503 when a dependency is down.
    The 503 is what Kubernetes readiness probes act on.
    """
    db_ok = check_db_connection()

    response_data = HealthResponse(
        status="healthy" if db_ok else "degraded",
        environment=settings.environment,
        uptime_seconds=round(time.time() - _start_time, 2),
        database="connected" if db_ok else "unreachable",
        python_version=platform.python_version(),
        version=__version__,
    )

    if not db_ok:
        return JSONResponse(status_code=503, content=response_data.model_dump())

    return response_data
