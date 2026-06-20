from urllib.parse import quote

import httpx

from app.services.git_hosts.base import DiffResult, GitHostClient, PRInfo

_API = "https://api.github.com"


def _encode_repo(repo_full_name: str) -> str:
    owner, repo = repo_full_name.split("/", 1)
    return f"{quote(owner, safe='')}/{quote(repo, safe='')}"


class GitHubProvider(GitHostClient):
    def __init__(self, access_token: str | None):
        self._token = access_token

    def _headers(self) -> dict:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def get_pr_info(self, repo_full_name: str, pr_number: int) -> PRInfo:
        encoded = _encode_repo(repo_full_name)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{_API}/repos/{encoded}/pulls/{pr_number}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        return PRInfo(
            number=data["number"],
            title=data["title"],
            url=data["html_url"],
            author=data["user"]["login"],
            base_branch=data["base"]["ref"],
            head_branch=data["head"]["ref"],
            body=data.get("body") or "",
        )

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> DiffResult:
        encoded = _encode_repo(repo_full_name)
        headers = {**self._headers(), "Accept": "application/vnd.github.v3.diff"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{_API}/repos/{encoded}/pulls/{pr_number}",
                headers=headers,
            )
            resp.raise_for_status()
            raw_diff = resp.text

        files: list[str] = []
        added = removed = 0
        for line in raw_diff.splitlines():
            if line.startswith("+++ b/"):
                files.append(line[6:])
            elif line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1

        return DiffResult(raw_diff=raw_diff, files_changed=files, lines_added=added, lines_removed=removed)

    async def post_review_comment(self, repo_full_name: str, pr_number: int, body: str) -> str:
        encoded = _encode_repo(repo_full_name)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_API}/repos/{encoded}/issues/{pr_number}/comments",
                headers=self._headers(),
                json={"body": body},
            )
            resp.raise_for_status()
            return str(resp.json()["id"])
