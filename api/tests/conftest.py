from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import generate_key, hash_key
from app.database import Base, get_db
from app.main import create_app
from app.models.api_key import ApiKey


@pytest.fixture
def test_db():
    """Fresh in-memory database per test — no shared state, any run order.

    StaticPool is required for in-memory SQLite: every new connection would
    otherwise get its own empty database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite defaults FKs off; enable so CASCADE behavior matches Postgres.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    yield SimpleNamespace(engine=engine, session_factory=session_factory)
    engine.dispose()


@pytest.fixture
def client(test_db):
    """App wired to the per-test database. No lifespan (tables exist already)."""

    def override_get_db():
        db = test_db.session_factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def make_api_key(test_db):
    """Factory: mint an API key in the test DB, return the raw key."""

    def _make(name="test-service", scopes="devices:write metrics:write", is_active=True):
        raw_key = generate_key()
        with test_db.session_factory() as db:
            db.add(
                ApiKey(name=name, key_hash=hash_key(raw_key), scopes=scopes, is_active=is_active)
            )
            db.commit()
        return raw_key

    return _make


@pytest.fixture
def auth_headers(make_api_key):
    """Headers for a fully-scoped service identity — used by all write tests."""
    return {"X-API-Key": make_api_key()}


@pytest.fixture
def create_device(client, auth_headers):
    """Factory fixture: POST a device and return the created resource."""

    def _create(hostname="SW-01", ip_address="10.0.0.1", site="HQ", **extra):
        payload = {"hostname": hostname, "ip_address": ip_address, "site": site, **extra}
        resp = client.post("/devices", json=payload, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _create
