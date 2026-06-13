"""Extended webhook tests: GitLab, Gitea, rate limiting, dedup."""
import hashlib
import hmac
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.repository import Repository
from app.models.review_job import JobStatus, ReviewJob
from app.models.user import User


def _make_github_sig(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


@pytest.fixture
def github_repo(db: Session):
    user = User(email=f"gh-{uuid.uuid4()}@example.com")
    db.add(user)
    db.flush()
    org = Organization(name="ghorg", owner_id=user.id)
    db.add(org)
    db.flush()
    repo = Repository(org_id=org.id, git_host="github", repo_full_name="owner/repo", webhook_secret="gh-secret")
    db.add(repo)
    db.commit()
    return repo


@pytest.fixture
def gitlab_repo(db: Session):
    user = User(email=f"gl-{uuid.uuid4()}@example.com")
    db.add(user)
    db.flush()
    org = Organization(name="glorg", owner_id=user.id)
    db.add(org)
    db.flush()
    repo = Repository(org_id=org.id, git_host="gitlab", repo_full_name="gl/repo", webhook_secret="gl-secret")
    db.add(repo)
    db.commit()
    return repo


@pytest.fixture
def gitea_repo(db: Session):
    user = User(email=f"gt-{uuid.uuid4()}@example.com")
    db.add(user)
    db.flush()
    org = Organization(name="gtorg", owner_id=user.id)
    db.add(org)
    db.flush()
    repo = Repository(org_id=org.id, git_host="gitea", repo_full_name="gt/repo", webhook_secret="gt-secret")
    db.add(repo)
    db.commit()
    return repo


class TestGitLabWebhook:
    def test_valid_merge_request_open(self, client: TestClient, gitlab_repo: Repository):
        payload = json.dumps({
            "object_attributes": {"action": "open", "iid": 7},
        }).encode()
        resp = client.post(
            f"/webhooks/{gitlab_repo.id}",
            content=payload,
            headers={
                "X-Gitlab-Event": "Merge Request Hook",
                "X-Gitlab-Token": "gl-secret",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"

    def test_invalid_token(self, client: TestClient, gitlab_repo: Repository):
        payload = json.dumps({"object_attributes": {"action": "open", "iid": 1}}).encode()
        resp = client.post(
            f"/webhooks/{gitlab_repo.id}",
            content=payload,
            headers={"X-Gitlab-Event": "Merge Request Hook", "X-Gitlab-Token": "WRONG"},
        )
        assert resp.status_code == 401

    def test_non_mr_event_ignored(self, client: TestClient, gitlab_repo: Repository):
        payload = json.dumps({}).encode()
        resp = client.post(
            f"/webhooks/{gitlab_repo.id}",
            content=payload,
            headers={"X-Gitlab-Event": "Push Hook", "X-Gitlab-Token": "gl-secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_closed_action_ignored(self, client: TestClient, gitlab_repo: Repository):
        payload = json.dumps({"object_attributes": {"action": "close", "iid": 1}}).encode()
        resp = client.post(
            f"/webhooks/{gitlab_repo.id}",
            content=payload,
            headers={"X-Gitlab-Event": "Merge Request Hook", "X-Gitlab-Token": "gl-secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


class TestGiteaWebhook:
    def test_valid_pr_opened(self, client: TestClient, gitea_repo: Repository):
        payload = json.dumps({
            "action": "opened",
            "pull_request": {"number": 3},
        }).encode()
        sig = hmac.new(b"gt-secret", payload, hashlib.sha256).hexdigest()
        resp = client.post(
            f"/webhooks/{gitea_repo.id}",
            content=payload,
            headers={
                "X-Gitea-Signature": sig,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"

    def test_invalid_signature(self, client: TestClient, gitea_repo: Repository):
        payload = json.dumps({"action": "opened", "pull_request": {"number": 1}}).encode()
        resp = client.post(
            f"/webhooks/{gitea_repo.id}",
            content=payload,
            headers={"X-Gitea-Signature": "badsig"},
        )
        assert resp.status_code == 401

    def test_closed_action_ignored(self, client: TestClient, gitea_repo: Repository):
        payload = json.dumps({"action": "closed", "pull_request": {"number": 1}}).encode()
        sig = hmac.new(b"gt-secret", payload, hashlib.sha256).hexdigest()
        resp = client.post(
            f"/webhooks/{gitea_repo.id}",
            content=payload,
            headers={"X-Gitea-Signature": sig},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


class TestWebhookDedup:
    def test_duplicate_pr_returns_already_queued(self, client: TestClient, db: Session, github_repo: Repository):
        # Pre-create a pending job for PR #100
        job = ReviewJob(repo_id=github_repo.id, pr_number=100, status=JobStatus.pending)
        db.add(job)
        db.commit()

        payload = json.dumps({"action": "opened", "pull_request": {"number": 100, "title": "T"}}).encode()
        sig = _make_github_sig(payload, github_repo.webhook_secret)
        resp = client.post(
            f"/webhooks/{github_repo.id}",
            content=payload,
            headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "already_queued"


class TestWebhookRateLimit:
    def test_rate_limit_triggers_after_max_requests(self, client: TestClient, github_repo: Repository):
        from app.routers.webhooks import _rate_buckets
        _rate_buckets.clear()

        for i in range(10):
            payload = json.dumps({"action": "opened", "pull_request": {"number": 200 + i, "title": "T"}}).encode()
            sig = _make_github_sig(payload, github_repo.webhook_secret)
            resp = client.post(
                f"/webhooks/{github_repo.id}",
                content=payload,
                headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": sig, "Content-Type": "application/json"},
            )
            assert resp.status_code in (200, 200)

        # 11th request should be rate limited
        payload = json.dumps({"action": "opened", "pull_request": {"number": 300, "title": "T"}}).encode()
        sig = _make_github_sig(payload, github_repo.webhook_secret)
        resp = client.post(
            f"/webhooks/{github_repo.id}",
            content=payload,
            headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert resp.status_code == 429

        _rate_buckets.clear()
