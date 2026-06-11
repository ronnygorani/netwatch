import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app

# StaticPool forces all DB operations through a single persistent connection,
# which is required for in-memory SQLite — otherwise each new connection gets
# its own empty database and the tables created above disappear.
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

Base.metadata.create_all(bind=_engine)


def override_get_db():
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    # No context manager — avoids triggering the lifespan's create_all
    # against the production DB. Tables are already created above.
    return TestClient(app)
