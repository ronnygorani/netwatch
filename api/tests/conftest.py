import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app


@pytest.fixture
def client():
    """Fresh app + fresh in-memory database per test.

    Function-scoped on purpose: no state leaks between tests, so every test
    is self-contained and the suite can be run in any order, in parallel, or
    as a single test. (The previous session-scoped fixture shared one DB
    across the whole run, which made tests order-dependent.)

    StaticPool forces all operations through a single persistent connection —
    required for in-memory SQLite, where each new connection would otherwise
    get its own empty database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite ignores foreign keys unless told otherwise; enable them so
    # FK behavior (e.g. ON DELETE CASCADE) matches PostgreSQL in tests.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    # No context manager around TestClient — avoids running the lifespan.
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    engine.dispose()


@pytest.fixture
def create_device(client):
    """Factory fixture: POST a device and return the created resource."""

    def _create(hostname="SW-01", ip_address="10.0.0.1", site="HQ", **extra):
        payload = {"hostname": hostname, "ip_address": ip_address, "site": site, **extra}
        resp = client.post("/devices", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _create
