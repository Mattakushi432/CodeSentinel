import os

# Must be set before any app module is imported so get_settings() picks it up
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, engine, get_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(setup_database):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset in-memory rate limit counters between tests to prevent bleed-through."""
    try:
        from app.limiter import limiter
        limiter._storage.reset()
    except (AttributeError, Exception):
        pass
    yield


@pytest.fixture
def client(db):
    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False, headers={"Referer": "http://localhost:8000/"}) as c:
        yield c
    app.dependency_overrides.clear()
