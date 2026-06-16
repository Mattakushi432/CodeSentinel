"""Tests for app/routers/repositories.py"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.repository import Repository
from app.models.user import User
from app.services.auth_service import hash_password

_TEST_PASSWORD = "testpassword123"


def _setup_and_login(client: TestClient, db: Session) -> tuple[User, Organization]:
    email = f"repos-{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash=hash_password(_TEST_PASSWORD))
    db.add(user)
    db.flush()
    org = Organization(name="myorg", owner_id=user.id)
    db.add(org)
    db.commit()
    db.refresh(user)
    db.refresh(org)

    resp = client.post("/auth/login", data={"email": email, "password": _TEST_PASSWORD}, follow_redirects=False)
    assert resp.status_code in (302, 303), f"Login failed: {resp.status_code}"
    return user, org


# ---------------------------------------------------------------------------
# GET /repos — unauthenticated
# ---------------------------------------------------------------------------

def test_list_repos_unauthenticated_redirects(client: TestClient):
    resp = client.get("/repos", follow_redirects=False)
    # require_user raises 302 HTTP exception
    assert resp.status_code in (302, 303)


# ---------------------------------------------------------------------------
# GET /repos — authenticated
# ---------------------------------------------------------------------------

def test_list_repos_no_org_returns_404(client: TestClient, db: Session):
    email = f"noorg-{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash=hash_password(_TEST_PASSWORD))
    db.add(user)
    db.commit()
    client.post("/auth/login", data={"email": email, "password": _TEST_PASSWORD}, follow_redirects=False)

    resp = client.get("/repos", follow_redirects=False)
    assert resp.status_code == 404


def test_list_repos_authenticated_returns_200(client: TestClient, db: Session):
    _setup_and_login(client, db)
    resp = client.get("/repos")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_list_repos_shows_existing_repos(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)
    repo = Repository(org_id=org.id, git_host="github", repo_full_name="owner/myrepo")
    db.add(repo)
    db.commit()

    resp = client.get("/repos")
    assert resp.status_code == 200
    assert b"myrepo" in resp.content


# ---------------------------------------------------------------------------
# POST /repos — create repo
# ---------------------------------------------------------------------------

def test_add_repo_creates_and_redirects(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)

    resp = client.post(
        "/repos",
        data={
            "git_host": "github",
            "repo_full_name": "owner/new-repo",
            "base_url": "",
            "access_token": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/repos"

    repo = db.query(Repository).filter(
        Repository.org_id == org.id,
        Repository.repo_full_name == "owner/new-repo",
    ).first()
    assert repo is not None
    assert repo.git_host == "github"
    assert repo.active is True


def test_add_repo_strips_whitespace(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)

    client.post(
        "/repos",
        data={
            "git_host": "github",
            "repo_full_name": "  owner/spaced-repo  ",
            "base_url": "",
            "access_token": "",
        },
        follow_redirects=False,
    )

    repo = db.query(Repository).filter(
        Repository.org_id == org.id,
        Repository.repo_full_name == "owner/spaced-repo",
    ).first()
    assert repo is not None


# ---------------------------------------------------------------------------
# POST /repos/{id}/delete
# ---------------------------------------------------------------------------

def test_delete_repo_soft_deletes_and_redirects(client: TestClient, db: Session):
    user, org = _setup_and_login(client, db)
    repo = Repository(org_id=org.id, git_host="github", repo_full_name="owner/to-delete", active=True)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    resp = client.post(f"/repos/{repo.id}/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/repos"

    db.refresh(repo)
    assert repo.active is False


def test_delete_repo_nonexistent_still_redirects(client: TestClient, db: Session):
    _setup_and_login(client, db)
    resp = client.post("/repos/99999/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/repos"


def test_delete_repo_from_other_org_ignored(client: TestClient, db: Session):
    """Users cannot delete repos belonging to other organisations."""
    user, org = _setup_and_login(client, db)

    # Create a second user+org+repo
    other_email = f"other-{uuid.uuid4()}@example.com"
    other_user = User(email=other_email, password_hash=hash_password(_TEST_PASSWORD))
    db.add(other_user)
    db.flush()
    other_org = Organization(name="otherorg", owner_id=other_user.id)
    db.add(other_org)
    db.flush()
    other_repo = Repository(org_id=other_org.id, git_host="github", repo_full_name="other/repo", active=True)
    db.add(other_repo)
    db.commit()
    db.refresh(other_repo)

    resp = client.post(f"/repos/{other_repo.id}/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)

    # Repo should still be active (was not deleted)
    db.refresh(other_repo)
    assert other_repo.active is True
