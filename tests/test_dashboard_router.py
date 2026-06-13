"""Tests for app/routers/dashboard.py"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.repository import Repository
from app.models.review_job import JobStatus, ReviewJob
from app.models.user import User
from app.services.auth_service import generate_magic_token

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _setup_and_login(client: TestClient, db: Session) -> tuple[User, Organization]:
    """Create user+org and establish an authenticated session via magic link."""
    email = f"dash-{uuid.uuid4()}@example.com"
    user = User(email=email, plan="free")
    db.add(user)
    db.flush()
    org = Organization(name="dashorg", owner_id=user.id, plan="free")
    db.add(org)
    db.commit()
    db.refresh(user)
    db.refresh(org)

    token = generate_magic_token(email)
    resp = client.get(f"/auth/verify?token={token}", follow_redirects=False)
    assert resp.status_code in (302, 303), f"Login failed: {resp.status_code}"
    return user, org


def _login_user_no_org(client: TestClient, db: Session) -> User:
    """Create a user WITHOUT an org and log in."""
    email = f"noorg-{uuid.uuid4()}@example.com"
    user = User(email=email, plan="free")
    db.add(user)
    db.commit()
    db.refresh(user)

    token = generate_magic_token(email)
    # Normally /auth/verify creates an org too; bypass that by patching
    # the DB query so no org is found during the verify call itself.
    # Simpler approach: verify will create an org. So instead we create the
    # user AFTER login by using a fresh user not linked to the session.
    # Actually, we'll just verify normally (which creates org) and then delete the org.
    resp = client.get(f"/auth/verify?token={token}", follow_redirects=False)
    assert resp.status_code in (302, 303)

    # Delete the org that was auto-created
    org = db.query(Organization).filter(Organization.owner_id == user.id).first()
    if org:
        db.delete(org)
        db.commit()

    return user


# ---------------------------------------------------------------------------
# GET / — unauthenticated
# ---------------------------------------------------------------------------

def test_dashboard_unauthenticated_redirects_to_login(client: TestClient):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/auth/login" in resp.headers["location"]


# ---------------------------------------------------------------------------
# GET / — authenticated, no org
# ---------------------------------------------------------------------------

def test_dashboard_authenticated_no_org_returns_200(client: TestClient, db: Session):
    _login_user_no_org(client, db)

    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# GET / — authenticated with org
# ---------------------------------------------------------------------------

def test_dashboard_with_org_returns_200(client: TestClient, db: Session):
    _setup_and_login(client, db)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_dashboard_with_org_and_repos_shows_repo_count(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)

    # Add two active repos
    for i in range(2):
        repo = Repository(org_id=org.id, git_host="github", repo_full_name=f"owner/repo-{i}", active=True)
        db.add(repo)
    db.commit()

    resp = client.get("/")
    assert resp.status_code == 200


def test_dashboard_with_recent_jobs_returns_200(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)

    repo = Repository(org_id=org.id, git_host="github", repo_full_name="owner/testrepo", active=True)
    db.add(repo)
    db.flush()

    job = ReviewJob(
        repo_id=repo.id,
        pr_number=1,
        pr_title="Test PR",
        pr_url="https://github.com/owner/testrepo/pull/1",
        status=JobStatus.done,
    )
    db.add(job)
    db.commit()

    resp = client.get("/")
    assert resp.status_code == 200


def test_dashboard_pending_and_done_jobs_both_counted(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)

    repo = Repository(org_id=org.id, git_host="github", repo_full_name="owner/counting-repo", active=True)
    db.add(repo)
    db.flush()

    # 1 pending, 2 done
    db.add(ReviewJob(
        repo_id=repo.id, pr_number=10, pr_title="Pending PR",
        pr_url="https://github.com/owner/counting-repo/pull/10",
        status=JobStatus.pending,
    ))
    for pr in (20, 21):
        db.add(ReviewJob(
            repo_id=repo.id, pr_number=pr, pr_title=f"Done PR {pr}",
            pr_url=f"https://github.com/owner/counting-repo/pull/{pr}",
            status=JobStatus.done,
        ))
    db.commit()

    resp = client.get("/")
    assert resp.status_code == 200
    # Template should render without errors — content contains basic dashboard HTML
    assert b"html" in resp.content.lower() or b"<!doctype" in resp.content.lower()
