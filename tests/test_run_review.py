"""Integration tests for run_review with mocked LLM and git clients."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest  # noqa: F401
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.repository import Repository
from app.models.review import Review
from app.models.review_job import JobStatus, ReviewJob
from app.models.user import User
from app.services.git_hosts.base import DiffResult, PRInfo
from app.services.llm.base import LLMResponse
from app.services.review_pipeline import run_review

SAMPLE_DIFF = """\
diff --git a/auth.py b/auth.py
index 000..111 100644
--- a/auth.py
+++ b/auth.py
@@ -1,3 +1,6 @@
+import os
+
 def login(user, password):
-    query = f"SELECT * FROM users WHERE email = '{user}'"
+    query = f"SELECT * FROM users WHERE email = '{user}' AND pwd='{password}'"
+    return db.execute(query)
"""

SAMPLE_LLM_RESPONSE = '[{"file": "auth.py", "line": 5, "severity": "high", "message": "SQL injection via string formatting"}]'


@pytest.fixture
def repo_with_job(db: Session):
    user = User(email=f"review-{uuid.uuid4()}@test.com")
    db.add(user)
    db.flush()
    org = Organization(name="testorg", owner_id=user.id)
    db.add(org)
    db.flush()
    repo = Repository(
        org_id=org.id,
        git_host="github",
        repo_full_name="owner/testrepo",
        webhook_secret="sec",
        access_token="token123",
    )
    db.add(repo)
    db.flush()
    job = ReviewJob(repo_id=repo.id, pr_number=42, status=JobStatus.pending)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, repo, db


async def test_run_review_success(repo_with_job):
    job, repo, db = repo_with_job

    pr_info = PRInfo(
        number=42, title="Fix auth", url="https://github.com/owner/testrepo/pull/42",
        author="dev", base_branch="main", head_branch="fix/auth", body="Fixes SQL bug",
    )
    diff = DiffResult(raw_diff=SAMPLE_DIFF, files_changed=["auth.py"], lines_added=4, lines_removed=1)
    llm_resp = LLMResponse(text=SAMPLE_LLM_RESPONSE, model="qwen2.5-coder:7b", prompt_tokens=100, completion_tokens=50)

    mock_git = AsyncMock()
    mock_git.get_pr_info.return_value = pr_info
    mock_git.get_pr_diff.return_value = diff
    mock_git.post_review_comment.return_value = "comment-id-123"

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = llm_resp

    with patch("app.services.review_pipeline.get_git_host_client", return_value=mock_git), \
         patch("app.services.review_pipeline.get_llm_client", return_value=mock_llm):
        await run_review(job.id, db)

    db.refresh(job)
    assert job.status == JobStatus.done
    assert job.pr_title == "Fix auth"
    assert job.pr_author == "dev"
    assert job.model_used == "qwen2.5-coder:7b"

    review = db.query(Review).filter(Review.job_id == job.id).first()
    assert review is not None
    assert review.severity_high == 1
    assert review.severity_medium == 0
    assert review.posted_comment_id == "comment-id-123"
    assert len(review.issues_json) == 1


async def test_run_review_empty_diff(repo_with_job):
    job, repo, db = repo_with_job

    pr_info = PRInfo(
        number=42, title="Empty", url="https://github.com/owner/testrepo/pull/42",
        author="dev", base_branch="main", head_branch="empty", body="",
    )
    empty_diff = DiffResult(raw_diff="", files_changed=[], lines_added=0, lines_removed=0)

    mock_git = AsyncMock()
    mock_git.get_pr_info.return_value = pr_info
    mock_git.get_pr_diff.return_value = empty_diff

    mock_llm = AsyncMock()

    with patch("app.services.review_pipeline.get_git_host_client", return_value=mock_git), \
         patch("app.services.review_pipeline.get_llm_client", return_value=mock_llm):
        await run_review(job.id, db)

    db.refresh(job)
    assert job.status == JobStatus.skipped
    assert job.error_msg == "Empty diff"
    mock_llm.generate.assert_not_called()


async def test_run_review_llm_error(repo_with_job):
    job, repo, db = repo_with_job

    pr_info = PRInfo(
        number=42, title="Err", url="https://github.com/owner/testrepo/pull/42",
        author="dev", base_branch="main", head_branch="err", body="",
    )
    diff = DiffResult(raw_diff=SAMPLE_DIFF, files_changed=["auth.py"], lines_added=4, lines_removed=1)

    mock_git = AsyncMock()
    mock_git.get_pr_info.return_value = pr_info
    mock_git.get_pr_diff.return_value = diff

    mock_llm = AsyncMock()
    mock_llm.generate.side_effect = Exception("Ollama timeout")

    with patch("app.services.review_pipeline.get_git_host_client", return_value=mock_git), \
         patch("app.services.review_pipeline.get_llm_client", return_value=mock_llm):
        await run_review(job.id, db)

    db.refresh(job)
    assert job.status == JobStatus.error
    assert "Ollama timeout" in job.error_msg


async def test_run_review_skips_already_processing(repo_with_job):
    job, repo, db = repo_with_job
    job.status = JobStatus.processing
    db.commit()

    mock_git = AsyncMock()
    mock_llm = AsyncMock()

    with patch("app.services.review_pipeline.get_git_host_client", return_value=mock_git), \
         patch("app.services.review_pipeline.get_llm_client", return_value=mock_llm):
        await run_review(job.id, db)

    mock_git.get_pr_info.assert_not_called()


async def test_run_review_large_diff_chunked(repo_with_job):
    job, repo, db = repo_with_job

    pr_info = PRInfo(
        number=42, title="Big PR", url="https://github.com/owner/testrepo/pull/42",
        author="dev", base_branch="main", head_branch="big", body="",
    )
    # Create a diff larger than max_diff_lines (500)
    large_diff_lines = ["diff --git a/file.py b/file.py"] + [f"+line {i}" for i in range(600)]
    large_diff = "\n".join(large_diff_lines)
    diff = DiffResult(raw_diff=large_diff, files_changed=["file.py"], lines_added=600, lines_removed=0)

    llm_resp = LLMResponse(text="[]", model="qwen2.5-coder:7b", prompt_tokens=100, completion_tokens=5)

    mock_git = AsyncMock()
    mock_git.get_pr_info.return_value = pr_info
    mock_git.get_pr_diff.return_value = diff
    mock_git.post_review_comment.return_value = "cmt-id"

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = llm_resp

    with patch("app.services.review_pipeline.get_git_host_client", return_value=mock_git), \
         patch("app.services.review_pipeline.get_llm_client", return_value=mock_llm):
        await run_review(job.id, db)

    db.refresh(job)
    assert job.status == JobStatus.done
    # Should have been called at least once (chunked)
    assert mock_llm.generate.call_count >= 1
