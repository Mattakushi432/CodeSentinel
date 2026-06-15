import atexit
import os
import tempfile

# Must be set before any app module is imported so get_settings() picks it up
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)  # release OS fd; SQLAlchemy manages its own connections
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests")
atexit.register(lambda: os.unlink(_DB_PATH) if os.path.exists(_DB_PATH) else None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


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
