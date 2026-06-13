"""Tests for app/routers/auth.py"""
import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.services.auth_service import generate_magic_token

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _login(client: TestClient, db: Session) -> User:
    """Create a user+org, verify via magic link, return the user."""
    email = f"auth-{uuid.uuid4()}@example.com"
    user = User(email=email, plan="free")
    db.add(user)
    db.flush()
    org = Organization(name="testorg", owner_id=user.id, plan="free")
    db.add(org)
    db.commit()
    db.refresh(user)

    token = generate_magic_token(email)
    resp = client.get(f"/auth/verify?token={token}", follow_redirects=False)
    assert resp.status_code in (302, 303)
    return user


# ---------------------------------------------------------------------------
# GET /auth/login
# ---------------------------------------------------------------------------

def test_login_page_returns_200(client: TestClient):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

def test_login_submit_valid_email_returns_magic_link_sent(client: TestClient, db: Session):
    with patch("app.routers.auth.send_magic_link", new_callable=AsyncMock) as mock_send:
        resp = client.post("/auth/login", data={"email": "user@example.com"})
    mock_send.assert_awaited_once()
    assert resp.status_code == 200
    # The response should render the magic_link_sent template
    assert "text/html" in resp.headers["content-type"]


def test_login_submit_strips_and_lowercases_email(client: TestClient, db: Session):
    captured = {}

    async def capture(to_email, magic_url):
        captured["email"] = to_email

    with patch("app.routers.auth.send_magic_link", side_effect=capture):
        client.post("/auth/login", data={"email": "  User@EXAMPLE.COM  "})

    assert captured.get("email") == "user@example.com"


# ---------------------------------------------------------------------------
# GET /auth/verify
# ---------------------------------------------------------------------------

def test_verify_valid_token_creates_user_and_redirects(client: TestClient, db: Session):
    email = f"newuser-{uuid.uuid4()}@example.com"
    token = generate_magic_token(email)

    resp = client.get(f"/auth/verify?token={token}", follow_redirects=False)

    # Should redirect to /
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/"

    # User should have been created in DB
    user = db.query(User).filter(User.email == email).first()
    assert user is not None

    # Org should have been created too
    org = db.query(Organization).filter(Organization.owner_id == user.id).first()
    assert org is not None


def test_verify_valid_token_existing_user_no_duplicate(client: TestClient, db: Session):
    email = f"existing-{uuid.uuid4()}@example.com"
    user = User(email=email, plan="free")
    db.add(user)
    db.flush()
    org = Organization(name="myorg", owner_id=user.id, plan="free")
    db.add(org)
    db.commit()

    token = generate_magic_token(email)
    resp = client.get(f"/auth/verify?token={token}", follow_redirects=False)
    assert resp.status_code in (302, 303)

    # No duplicate user should exist
    count = db.query(User).filter(User.email == email).count()
    assert count == 1


def test_verify_invalid_token_shows_login_with_error(client: TestClient):
    resp = client.get("/auth/verify?token=totally-invalid-token")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    # Should render login page with error
    assert b"expired" in resp.content.lower() or b"invalid" in resp.content.lower()


def test_verify_expired_token_shows_error(client: TestClient):
    # We patch verify_magic_token to simulate expiry
    with patch("app.routers.auth.verify_magic_token", return_value=None):
        resp = client.get("/auth/verify?token=sometoken")
    assert resp.status_code == 200
    # Should show the login page (not a redirect)
    assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# GET /auth/logout
# ---------------------------------------------------------------------------

def test_logout_clears_session_and_redirects(client: TestClient, db: Session):
    # First log in
    _login(client, db)

    # Then log out
    resp = client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/auth/login" in resp.headers["location"]


def test_logout_without_login_redirects_to_login(client: TestClient):
    resp = client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/auth/login" in resp.headers["location"]
