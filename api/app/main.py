import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app import __version__
from app.config import settings
from app.models import Device, Metric, PollerHeartbeat  # noqa: F401 — registers with Base
from app.routers import devices, health, metrics, poller, sot, webhooks

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Application factory — keeps tests isolated from module-level state."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Schema is managed by Alembic as a deploy step, never at startup.
        logger.info(
            "NetWatch API starting | env=%s | version=%s",
            settings.environment,
            app.version,
        )
        yield
        logger.info("NetWatch API shutting down gracefully")

    app = FastAPI(
        title="NetWatch API",
        description=(
            "Unified REST API for the NetWatch network automation platform.\n\n"
            "Current modules:\n"
            "- Device inventory: /v1/devices\n"
            "- Health metrics ingestion and queries: /v1/metrics\n"
            "- Collector liveness: /v1/poller\n"
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Dashboard is served from a different origin than the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    # /health stays unversioned: it is infrastructure (probes), not API surface.
    app.include_router(health.router)
    app.include_router(devices.router, prefix="/v1")
    app.include_router(metrics.router, prefix="/v1")
    app.include_router(poller.router, prefix="/v1")
    app.include_router(sot.router, prefix="/v1")
    app.include_router(webhooks.router, prefix="/v1")

    # Legacy unversioned paths: 308 preserves method and body, unlike 301.
    # Remove after one phase (CONTRACTS section 1).
    legacy_prefixes = ("/devices", "/metrics", "/poller")

    @app.middleware("http")
    async def redirect_legacy_paths(request: Request, call_next):
        path = request.url.path
        if path.startswith(legacy_prefixes):
            url = request.url.replace(path=f"/v1{path}")
            return RedirectResponse(str(url), status_code=308)
        return await call_next(request)

    return app


app = create_app()
