"""Tests for app/services/git_hosts/ (GitHub, GitLab, Gitea) and the factory."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.git_hosts import (
    GiteaProvider,
    GitHubProvider,
    GitLabProvider,
    get_git_host_client,
)
from app.services.git_hosts.base import DiffResult, PRInfo

# ---------------------------------------------------------------------------
# Helpers to build mock httpx responses
# ---------------------------------------------------------------------------

def _mock_response(json_data=None, text_data=None, status_code=200):
    """Return a mock that looks like an httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if json_data is not None:
        resp.json = MagicMock(return_value=json_data)
    if text_data is not None:
        resp.text = text_data
    return resp


def _async_client_ctx(response: MagicMock):
    """Construct a mock async context manager that yields a client whose methods return *response*."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client.post = AsyncMock(return_value=response)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, mock_client


# ---------------------------------------------------------------------------
# GitHubProvider
# ---------------------------------------------------------------------------

_GITHUB_PR_PAYLOAD = {
    "number": 42,
    "title": "Fix the auth bug",
    "html_url": "https://github.com/owner/repo/pull/42",
    "user": {"login": "dev"},
    "base": {"ref": "main"},
    "head": {"ref": "feature/auth"},
    "body": "Fixes the login issue",
}

_GITHUB_DIFF = """\
diff --git a/app/auth.py b/app/auth.py
--- a/app/auth.py
+++ b/app/auth.py
@@ -1,3 +1,4 @@
+import jwt
 import os
-# old line
+# new line
"""


@pytest.mark.asyncio
async def test_github_get_pr_info():
    resp = _mock_response(json_data=_GITHUB_PR_PAYLOAD)
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GitHubProvider(access_token="tok123")
        info = await provider.get_pr_info("owner/repo", 42)

    assert isinstance(info, PRInfo)
    assert info.number == 42
    assert info.title == "Fix the auth bug"
    assert info.author == "dev"
    assert info.base_branch == "main"
    assert info.head_branch == "feature/auth"
    assert info.body == "Fixes the login issue"


@pytest.mark.asyncio
async def test_github_get_pr_info_no_body():
    payload = {**_GITHUB_PR_PAYLOAD, "body": None}
    resp = _mock_response(json_data=payload)
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GitHubProvider(access_token=None)
        info = await provider.get_pr_info("owner/repo", 1)

    assert info.body == ""


@pytest.mark.asyncio
async def test_github_get_pr_diff():
    resp = _mock_response(text_data=_GITHUB_DIFF)
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GitHubProvider(access_token="tok")
        result = await provider.get_pr_diff("owner/repo", 42)

    assert isinstance(result, DiffResult)
    assert "app/auth.py" in result.files_changed
    assert result.lines_added == 2
    assert result.lines_removed == 1


@pytest.mark.asyncio
async def test_github_post_review_comment():
    resp = _mock_response(json_data={"id": 999})
    ctx, mock_client = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GitHubProvider(access_token="tok")
        comment_id = await provider.post_review_comment("owner/repo", 42, "LGTM!")

    assert comment_id == "999"
    mock_client.post.assert_awaited_once()
    call_kwargs = mock_client.post.call_args[1]
    assert call_kwargs["json"]["body"] == "LGTM!"


# ---------------------------------------------------------------------------
# GitLabProvider
# ---------------------------------------------------------------------------

_GITLAB_MR_PAYLOAD = {
    "iid": 7,
    "title": "Add feature Y",
    "web_url": "https://gitlab.com/owner/repo/-/merge_requests/7",
    "author": {"username": "gitlabdev"},
    "target_branch": "main",
    "source_branch": "feat/y",
    "description": "Adds feature Y",
}

_GITLAB_DIFFS = [
    {
        "new_path": "src/feature.py",
        "diff": "+# new comment\n-# old comment\n",
    }
]


@pytest.mark.asyncio
async def test_gitlab_get_pr_info():
    resp = _mock_response(json_data=_GITLAB_MR_PAYLOAD)
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GitLabProvider(base_url="https://gitlab.com", access_token="glpat-abc")
        info = await provider.get_pr_info("owner/repo", 7)

    assert isinstance(info, PRInfo)
    assert info.number == 7
    assert info.title == "Add feature Y"
    assert info.author == "gitlabdev"
    assert info.base_branch == "main"
    assert info.head_branch == "feat/y"


@pytest.mark.asyncio
async def test_gitlab_get_pr_diff():
    resp = _mock_response(json_data=_GITLAB_DIFFS)
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GitLabProvider(base_url="https://gitlab.com", access_token=None)
        result = await provider.get_pr_diff("owner/repo", 7)

    assert isinstance(result, DiffResult)
    assert "src/feature.py" in result.files_changed
    assert result.lines_added == 1
    assert result.lines_removed == 1


@pytest.mark.asyncio
async def test_gitlab_post_review_comment():
    resp = _mock_response(json_data={"id": 55})
    ctx, mock_client = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GitLabProvider(base_url="https://gitlab.com", access_token="token")
        cid = await provider.post_review_comment("owner/repo", 7, "Nice work!")

    assert cid == "55"
    mock_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_gitlab_encodes_repo_name_with_slash():
    """Repo name containing slash must be percent-encoded in GitLab API calls."""
    resp = _mock_response(json_data=_GITLAB_MR_PAYLOAD)
    ctx, mock_client = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GitLabProvider(base_url="https://gitlab.example.com", access_token=None)
        await provider.get_pr_info("group/subgroup/repo", 1)

    url_called = mock_client.get.call_args[0][0]
    assert "%2F" in url_called


# ---------------------------------------------------------------------------
# GiteaProvider
# ---------------------------------------------------------------------------

_GITEA_PR_PAYLOAD = {
    "number": 3,
    "title": "Hotfix login",
    "html_url": "https://gitea.example.com/owner/repo/pulls/3",
    "user": {"login": "giteadev"},
    "base": {"label": "main"},
    "head": {"label": "hotfix/login"},
    "body": "",
}

_GITEA_DIFF = """\
diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1 +1,2 @@
+print("hello")
 print("world")
"""


@pytest.mark.asyncio
async def test_gitea_get_pr_info():
    resp = _mock_response(json_data=_GITEA_PR_PAYLOAD)
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GiteaProvider(base_url="https://gitea.example.com", access_token="giteatok")
        info = await provider.get_pr_info("owner/repo", 3)

    assert isinstance(info, PRInfo)
    assert info.number == 3
    assert info.title == "Hotfix login"
    assert info.author == "giteadev"
    assert info.base_branch == "main"
    assert info.head_branch == "hotfix/login"


@pytest.mark.asyncio
async def test_gitea_get_pr_diff():
    resp = _mock_response(text_data=_GITEA_DIFF)
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GiteaProvider(base_url="https://gitea.example.com", access_token=None)
        result = await provider.get_pr_diff("owner/repo", 3)

    assert isinstance(result, DiffResult)
    assert "main.py" in result.files_changed
    assert result.lines_added == 1
    assert result.lines_removed == 0


@pytest.mark.asyncio
async def test_gitea_post_review_comment():
    resp = _mock_response(json_data={"id": 77})
    ctx, mock_client = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GiteaProvider(base_url="https://gitea.example.com", access_token="tok")
        cid = await provider.post_review_comment("owner/repo", 3, "Looks good!")

    assert cid == "77"
    mock_client.post.assert_awaited_once()


# ---------------------------------------------------------------------------
# Factory: get_git_host_client
# ---------------------------------------------------------------------------

def test_factory_returns_github_provider():
    client = get_git_host_client("github", None, "tok")
    assert isinstance(client, GitHubProvider)


def test_factory_returns_gitlab_provider_default_base_url():
    client = get_git_host_client("gitlab", None, "tok")
    assert isinstance(client, GitLabProvider)
    assert client._base == "https://gitlab.com"


def test_factory_returns_gitlab_provider_custom_base_url():
    client = get_git_host_client("gitlab", "https://mygitlab.example.com", "tok")
    assert isinstance(client, GitLabProvider)
    assert "mygitlab.example.com" in client._base


def test_factory_returns_gitea_provider():
    client = get_git_host_client("gitea", "https://gitea.example.com", "tok")
    assert isinstance(client, GiteaProvider)


def test_factory_unknown_host_raises_value_error():
    with pytest.raises(ValueError, match="Unknown git host"):
        get_git_host_client("bitbucket", None, None)
