import logging

from fastapi import FastAPI

from app.config import settings
from app.routers import health

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
    app = FastAPI(
        title="NetWatch API",
        description=(
            "Unified REST API for the NetWatch Network Observability Platform.\n\n"
            "All modules communicate exclusively through this API:\n"
            "- Phase 2: C++ probe engine → POST /metrics\n"
            "- Phase 3: C++ packet analyzer → POST /packets\n"
            "- Phase 4: Python automator → GET/POST /devices\n"
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.include_router(health.router)

    @app.on_event("startup")
    async def on_startup():
        logger.info(
            "NetWatch API starting | env=%s | version=%s",
            settings.environment,
            app.version,
        )

    @app.on_event("shutdown")
    async def on_shutdown():
        logger.info("NetWatch API shutting down gracefully")

    return app


app = create_app()
