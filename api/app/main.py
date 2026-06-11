import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import engine
from app.models import Device, Metric  # noqa: F401 — imported to register with Base
from app.database import Base
from app.routers import health
from app.routers import devices, metrics

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
            "NetAuto API starting | env=%s | version=%s",
            settings.environment,
            app.version,
        )
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified")
        yield
        logger.info("NetAuto API shutting down gracefully")

    app = FastAPI(
        title="NetAuto API",
        description=(
            "Unified REST API for the NetAuto Network Automation Platform.\n\n"
            "All modules communicate exclusively through this API:\n"
            "- Phase 2: Device inventory + Netmiko poller → /devices, /metrics\n"
            "- Phase 3: Config manager → /configs\n"
            "- Phase 4: Change workflow → /changes\n"
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
