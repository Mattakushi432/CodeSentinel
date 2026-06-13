import hashlib
import hmac
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.repository import Repository
from app.models.user import User


def _make_github_sig(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


@pytest.fixture
def repo_with_secret(db: Session):
    user = User(email=f"test-{uuid.uuid4()}@example.com")
    db.add(user)
    db.flush()

    org = Organization(name="testorg", owner_id=user.id)
    db.add(org)
    db.flush()

    repo = Repository(org_id=org.id, git_host="github", repo_full_name="test/repo", webhook_secret="supersecret")
    db.add(repo)
    db.commit()
    return repo


def test_webhook_valid_github_pr_opened(client: TestClient, repo_with_secret: Repository):
    payload = json.dumps({
        "action": "opened",
        "pull_request": {"number": 42, "title": "Fix bug"},
    }).encode()
    sig = _make_github_sig(payload, repo_with_secret.webhook_secret)

    resp = client.post(
        f"/webhooks/{repo_with_secret.id}",
        content=payload,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert "job_id" in data


def test_webhook_invalid_signature(client: TestClient, repo_with_secret: Repository):
    payload = b'{"action": "opened"}'
    resp = client.post(
        f"/webhooks/{repo_with_secret.id}",
        content=payload,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=bad", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_webhook_ignored_event(client: TestClient, repo_with_secret: Repository):
    payload = json.dumps({"action": "closed"}).encode()
    sig = _make_github_sig(payload, repo_with_secret.webhook_secret)
    resp = client.post(
        f"/webhooks/{repo_with_secret.id}",
        content=payload,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_unknown_repo(client: TestClient):
    resp = client.post("/webhooks/99999", content=b"{}", headers={"X-GitHub-Event": "pull_request"})
    assert resp.status_code == 404
