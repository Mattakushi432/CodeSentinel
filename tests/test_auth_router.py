"""Tests for app/routers/auth.py"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.services.auth_service import hash_password

_TEST_PASSWORD = "testpassword123"


def _create_user_and_login(client: TestClient, db: Session) -> User:
    """Create a user+org with a known password, then log in."""
    email = f"auth-{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash=hash_password(_TEST_PASSWORD))
    db.add(user)
    db.flush()
    org = Organization(name="testorg", owner_id=user.id)
    db.add(org)
    db.commit()
    db.refresh(user)

    resp = client.post("/auth/login", data={"email": email, "password": _TEST_PASSWORD}, follow_redirects=False)
    assert resp.status_code in (302, 303), f"Login failed: {resp.status_code}"
    return user


# ---------------------------------------------------------------------------
# GET /auth/login
# ---------------------------------------------------------------------------

def test_login_page_returns_200(client: TestClient):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# GET /auth/register
# ---------------------------------------------------------------------------

def test_register_page_returns_200(client: TestClient):
    resp = client.get("/auth/register")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

def test_register_creates_user_and_redirects(client: TestClient, db: Session):
    email = f"newuser-{uuid.uuid4()}@example.com"
    resp = client.post(
        "/auth/register",
        data={"email": email, "password": "strongpass1", "password_confirm": "strongpass1"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/"

    user = db.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.password_hash is not None

    org = db.query(Organization).filter(Organization.owner_id == user.id).first()
    assert org is not None


def test_register_duplicate_email_shows_error(client: TestClient, db: Session):
    email = f"dup-{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash=hash_password("pass1234"))
    db.add(user)
    db.commit()

    resp = client.post(
        "/auth/register",
        data={"email": email, "password": "pass1234", "password_confirm": "pass1234"},
    )
    assert resp.status_code == 200
    assert b"already exists" in resp.content.lower()


def test_register_password_mismatch_shows_error(client: TestClient):
    resp = client.post(
        "/auth/register",
        data={"email": "mismatch@example.com", "password": "pass1234", "password_confirm": "different"},
    )
    assert resp.status_code == 200
    assert b"do not match" in resp.content.lower()


def test_register_password_too_short_shows_error(client: TestClient):
    resp = client.post(
        "/auth/register",
        data={"email": "short@example.com", "password": "abc", "password_confirm": "abc"},
    )
    assert resp.status_code == 200
    assert b"at least" in resp.content.lower()


def test_register_invalid_email_shows_error(client: TestClient):
    resp = client.post(
        "/auth/register",
        data={"email": "not-an-email", "password": "pass1234", "password_confirm": "pass1234"},
    )
    assert resp.status_code == 200
    assert b"valid email" in resp.content.lower()


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

def test_login_valid_credentials_redirects(client: TestClient, db: Session):
    email = f"login-{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash=hash_password("correctpass"))
    db.add(user)
    db.commit()

    resp = client.post("/auth/login", data={"email": email, "password": "correctpass"}, follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/"


def test_login_wrong_password_shows_error(client: TestClient, db: Session):
    email = f"wrongpass-{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash=hash_password("correctpass"))
    db.add(user)
    db.commit()

    resp = client.post("/auth/login", data={"email": email, "password": "wrongpass"})
    assert resp.status_code == 200
    assert b"invalid" in resp.content.lower()


def test_login_nonexistent_email_shows_error(client: TestClient):
    resp = client.post("/auth/login", data={"email": "nobody@example.com", "password": "somepass"})
    assert resp.status_code == 200
    assert b"invalid" in resp.content.lower()


def test_login_invalid_email_format_shows_error(client: TestClient):
    resp = client.post("/auth/login", data={"email": "not-an-email", "password": "somepass"})
    assert resp.status_code == 200
    assert b"valid email" in resp.content.lower()


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

def test_logout_clears_session_and_redirects(client: TestClient, db: Session):
    _create_user_and_login(client, db)

    resp = client.post("/auth/logout", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/auth/login" in resp.headers["location"]


def test_logout_without_login_redirects_to_login(client: TestClient):
    resp = client.post("/auth/logout", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/auth/login" in resp.headers["location"]


# ---------------------------------------------------------------------------
# dev-login route must not exist
# ---------------------------------------------------------------------------

def test_dev_login_route_does_not_exist(client: TestClient):
    resp = client.get("/auth/dev-login", follow_redirects=False)
    assert resp.status_code == 404
