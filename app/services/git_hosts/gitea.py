import httpx
from urllib.parse import quote

from app.services.git_hosts.base import DiffResult, GitHostClient, PRInfo


def _encode_segments(repo_full_name: str) -> tuple[str, str]:
    owner, repo = repo_full_name.split("/", 1)
    return quote(owner, safe=""), quote(repo, safe="")


class GiteaProvider(GitHostClient):
    def __init__(self, base_url: str, access_token: str | None):
        self._base = base_url.rstrip("/")
        self._token = access_token

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"token {self._token}"
        return h

    def _api(self, path: str) -> str:
        return f"{self._base}/api/v1{path}"

    async def get_pr_info(self, repo_full_name: str, pr_number: int) -> PRInfo:
        owner, repo = _encode_segments(repo_full_name)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                self._api(f"/repos/{owner}/{repo}/pulls/{pr_number}"),
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        return PRInfo(
            number=data["number"],
            title=data["title"],
            url=data["html_url"],
            author=data["user"]["login"],
            base_branch=data["base"]["label"],
            head_branch=data["head"]["label"],
            body=data.get("body") or "",
        )

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> DiffResult:
        owner, repo = _encode_segments(repo_full_name)
        async with httpx.AsyncClient(timeout=30, headers={"Accept": "text/plain", **self._headers()}) as client:
            resp = await client.get(
                self._api(f"/repos/{owner}/{repo}/pulls/{pr_number}.diff"),
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
        owner, repo = _encode_segments(repo_full_name)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self._api(f"/repos/{owner}/{repo}/issues/{pr_number}/comments"),
                headers=self._headers(),
                json={"body": body},
            )
            resp.raise_for_status()
            return str(resp.json()["id"])
