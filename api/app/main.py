import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import settings
from app.models import Device, Metric, PollerHeartbeat  # noqa: F401 — registers with Base
from app.routers import devices, health, metrics, poller

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
            "- Device inventory → /devices\n"
            "- Health metrics ingestion and queries → /metrics\n"
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

    app.include_router(health.router)
    app.include_router(devices.router)
    app.include_router(metrics.router)
    app.include_router(poller.router)

    return app


app = create_app()
