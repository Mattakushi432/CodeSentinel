"""Tests for app/routers/reviews.py"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.repository import Repository
from app.models.review_job import JobStatus, ReviewJob
from app.models.user import User
from app.services.auth_service import hash_password

_TEST_PASSWORD = "testpassword123"


def _login_with_org(client: TestClient, db: Session) -> tuple[User, Organization]:
    email = f"reviews-{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash=hash_password(_TEST_PASSWORD))
    db.add(user)
    db.flush()
    org = Organization(name="testorg", owner_id=user.id)
    db.add(org)
    db.commit()
    db.refresh(user)
    db.refresh(org)
    client.post("/auth/login", data={"email": email, "password": _TEST_PASSWORD}, follow_redirects=False)
    return user, org


def test_list_reviews_returns_200(client: TestClient, db: Session):
    _login_with_org(client, db)
    resp = client.get("/reviews")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_list_reviews_no_org_returns_200_empty(client: TestClient, db: Session):
    email = f"noorg-{uuid.uuid4()}@example.com"
    user = User(email=email, password_hash=hash_password(_TEST_PASSWORD))
    db.add(user)
    db.commit()
    client.post("/auth/login", data={"email": email, "password": _TEST_PASSWORD}, follow_redirects=False)
    resp = client.get("/reviews")
    assert resp.status_code == 200


def test_list_reviews_repo_filter(client: TestClient, db: Session):
    user, org = _login_with_org(client, db)
    repo = Repository(org_id=org.id, git_host="github", repo_full_name="owner/repo")
    db.add(repo)
    db.commit()
    resp = client.get(f"/reviews?repo_id={repo.id}")
    assert resp.status_code == 200


def test_review_detail_returns_200(client: TestClient, db: Session):
    user, org = _login_with_org(client, db)
    repo = Repository(org_id=org.id, git_host="github", repo_full_name="owner/repo")
    db.add(repo)
    db.flush()
    job = ReviewJob(repo_id=repo.id, pr_number=1, status=JobStatus.done)
    db.add(job)
    db.commit()
    resp = client.get(f"/reviews/{job.id}")
    assert resp.status_code == 200


def test_review_detail_not_found_returns_404(client: TestClient, db: Session):
    _login_with_org(client, db)
    resp = client.get("/reviews/99999")
    assert resp.status_code == 404


def test_job_status_returns_200(client: TestClient, db: Session):
    user, org = _login_with_org(client, db)
    repo = Repository(org_id=org.id, git_host="github", repo_full_name="owner/repo")
    db.add(repo)
    db.flush()
    job = ReviewJob(repo_id=repo.id, pr_number=1, status=JobStatus.pending)
    db.add(job)
    db.commit()
    resp = client.get(f"/reviews/job/{job.id}/status")
    assert resp.status_code == 200
