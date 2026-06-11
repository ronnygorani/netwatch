import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import Base, engine
from app.models import Device, Metric  # noqa: F401 — imported to register with Base
from app.routers import devices, health, metrics

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Application factory. Returns a configured FastAPI instance.

    Using a factory instead of a module-level instance keeps tests
    isolated — each test gets a fresh app with no shared state.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "NetWatch API starting | env=%s | version=%s",
            settings.environment,
            app.version,
        )
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified")
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
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(devices.router)
    app.include_router(metrics.router)

    return app


app = create_app()
