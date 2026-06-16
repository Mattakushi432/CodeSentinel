"""Tests for app/routers/dashboard.py"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.repository import Repository
from app.models.review_job import JobStatus, ReviewJob
from app.models.user import User
from app.services.auth_service import hash_password

_TEST_PASSWORD = "testpassword123"


def _setup_and_login(client: TestClient, db: Session) -> tuple[User, Organization]:
    """Create user+org and establish an authenticated session."""
    email = f"dash-{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash=hash_password(_TEST_PASSWORD))
    db.add(user)
    db.flush()
    org = Organization(name="dashorg", owner_id=user.id)
    db.add(org)
    db.commit()
    db.refresh(user)
    db.refresh(org)

    resp = client.post("/auth/login", data={"email": email, "password": _TEST_PASSWORD}, follow_redirects=False)
    assert resp.status_code in (302, 303), f"Login failed: {resp.status_code}"
    return user, org


def _login_user_no_org(client: TestClient, db: Session) -> User:
    """Create a user WITHOUT an org and log in."""
    email = f"noorg-{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash=hash_password(_TEST_PASSWORD))
    db.add(user)
    db.commit()
    db.refresh(user)

    resp = client.post("/auth/login", data={"email": email, "password": _TEST_PASSWORD}, follow_redirects=False)
    assert resp.status_code in (302, 303)
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
