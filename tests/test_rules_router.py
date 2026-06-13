"""Tests for app/routers/rules.py"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.rule import Rule
from app.models.user import User
from app.services.auth_service import generate_magic_token

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _setup_and_login(client: TestClient, db: Session) -> tuple[User, Organization]:
    email = f"rules-{uuid.uuid4()}@example.com"
    user = User(email=email, plan="free")
    db.add(user)
    db.flush()
    org = Organization(name="myorg", owner_id=user.id, plan="free")
    db.add(org)
    db.commit()
    db.refresh(user)
    db.refresh(org)

    token = generate_magic_token(email)
    resp = client.get(f"/auth/verify?token={token}", follow_redirects=False)
    assert resp.status_code in (302, 303), f"Login failed: {resp.status_code}"
    return user, org


# ---------------------------------------------------------------------------
# GET /rules — unauthenticated
# ---------------------------------------------------------------------------

def test_list_rules_unauthenticated_redirects(client: TestClient):
    resp = client.get("/rules", follow_redirects=False)
    assert resp.status_code in (302, 303)


# ---------------------------------------------------------------------------
# GET /rules — authenticated
# ---------------------------------------------------------------------------

def test_list_rules_authenticated_returns_200(client: TestClient, db: Session):
    _setup_and_login(client, db)
    resp = client.get("/rules")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_list_rules_shows_existing_rules(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)
    rule = Rule(org_id=org.id, name="No SQL injection", description="Catch SQL injection", language="all")
    db.add(rule)
    db.commit()

    resp = client.get("/rules")
    assert resp.status_code == 200
    assert b"No SQL injection" in resp.content


# ---------------------------------------------------------------------------
# POST /rules — create
# ---------------------------------------------------------------------------

def test_add_rule_creates_and_redirects(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)

    resp = client.post(
        "/rules",
        data={
            "name": "Enforce type hints",
            "description": "All functions must have type annotations",
            "prompt_snippet": "Fail if type hints are missing",
            "language": "python",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/rules"

    rule = db.query(Rule).filter(Rule.org_id == org.id, Rule.name == "Enforce type hints").first()
    assert rule is not None
    assert rule.language == "python"
    assert rule.enabled is True


def test_add_rule_strips_whitespace_from_name(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)

    client.post(
        "/rules",
        data={"name": "  padded rule  ", "description": "", "prompt_snippet": "", "language": "all"},
        follow_redirects=False,
    )

    rule = db.query(Rule).filter(Rule.org_id == org.id, Rule.name == "padded rule").first()
    assert rule is not None


def test_add_rule_empty_optional_fields_stored_as_none(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)

    client.post(
        "/rules",
        data={"name": "minimal-rule", "description": "", "prompt_snippet": "", "language": "all"},
        follow_redirects=False,
    )

    rule = db.query(Rule).filter(Rule.org_id == org.id, Rule.name == "minimal-rule").first()
    assert rule is not None
    assert rule.description is None
    assert rule.prompt_snippet is None


# ---------------------------------------------------------------------------
# POST /rules/{id}/toggle
# ---------------------------------------------------------------------------

def test_toggle_rule_disables_enabled_rule(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)
    rule = Rule(org_id=org.id, name="toggle-me", enabled=True, language="all")
    db.add(rule)
    db.commit()
    db.refresh(rule)

    resp = client.post(f"/rules/{rule.id}/toggle", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/rules"

    db.refresh(rule)
    assert rule.enabled is False


def test_toggle_rule_enables_disabled_rule(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)
    rule = Rule(org_id=org.id, name="disabled-rule", enabled=False, language="all")
    db.add(rule)
    db.commit()
    db.refresh(rule)

    client.post(f"/rules/{rule.id}/toggle", follow_redirects=False)

    db.refresh(rule)
    assert rule.enabled is True


def test_toggle_nonexistent_rule_still_redirects(client: TestClient, db: Session):
    _setup_and_login(client, db)
    resp = client.post("/rules/99999/toggle", follow_redirects=False)
    assert resp.status_code in (302, 303)


# ---------------------------------------------------------------------------
# POST /rules/{id}/delete
# ---------------------------------------------------------------------------

def test_delete_rule_removes_from_db(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)
    rule = Rule(org_id=org.id, name="delete-me", language="all")
    db.add(rule)
    db.commit()
    db.refresh(rule)
    rule_id = rule.id

    resp = client.post(f"/rules/{rule_id}/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/rules"

    deleted = db.query(Rule).filter(Rule.id == rule_id).first()
    assert deleted is None


def test_delete_nonexistent_rule_still_redirects(client: TestClient, db: Session):
    _setup_and_login(client, db)
    resp = client.post("/rules/99999/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)


def test_delete_rule_from_other_org_ignored(client: TestClient, db: Session):
    """A user cannot delete rules belonging to a different organisation."""
    _setup_and_login(client, db)

    other_email = f"other-{uuid.uuid4()}@example.com"
    other_user = User(email=other_email, plan="free")
    db.add(other_user)
    db.flush()
    other_org = Organization(name="otherorg", owner_id=other_user.id, plan="free")
    db.add(other_org)
    db.flush()
    other_rule = Rule(org_id=other_org.id, name="other-rule", language="all")
    db.add(other_rule)
    db.commit()
    db.refresh(other_rule)
    rule_id = other_rule.id

    client.post(f"/rules/{rule_id}/delete", follow_redirects=False)

    still_there = db.query(Rule).filter(Rule.id == rule_id).first()
    assert still_there is not None
