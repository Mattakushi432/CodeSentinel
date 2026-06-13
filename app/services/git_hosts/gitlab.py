import httpx

from app.services.git_hosts.base import DiffResult, GitHostClient, PRInfo


class GitLabProvider(GitHostClient):
    def __init__(self, base_url: str, access_token: str | None):
        self._base = base_url.rstrip("/")
        self._token = access_token

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._token:
            h["PRIVATE-TOKEN"] = self._token
        return h

    def _api(self, path: str) -> str:
        return f"{self._base}/api/v4{path}"

    @staticmethod
    def _encode_repo(repo_full_name: str) -> str:
        return repo_full_name.replace("/", "%2F")

    async def get_pr_info(self, repo_full_name: str, pr_number: int) -> PRInfo:
        encoded = self._encode_repo(repo_full_name)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                self._api(f"/projects/{encoded}/merge_requests/{pr_number}"),
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        return PRInfo(
            number=data["iid"],
            title=data["title"],
            url=data["web_url"],
            author=data["author"]["username"],
            base_branch=data["target_branch"],
            head_branch=data["source_branch"],
            body=data.get("description") or "",
        )

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> DiffResult:
        encoded = self._encode_repo(repo_full_name)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                self._api(f"/projects/{encoded}/merge_requests/{pr_number}/diffs"),
                headers=self._headers(),
            )
            resp.raise_for_status()
            diffs = resp.json()

        raw_parts: list[str] = []
        files: list[str] = []
        added = removed = 0
        for d in diffs:
            raw_parts.append(d.get("diff", ""))
            files.append(d.get("new_path", ""))
            for line in d.get("diff", "").splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    added += 1
                elif line.startswith("-") and not line.startswith("---"):
                    removed += 1

        return DiffResult(
            raw_diff="\n".join(raw_parts),
            files_changed=files,
            lines_added=added,
            lines_removed=removed,
        )

    async def post_review_comment(self, repo_full_name: str, pr_number: int, body: str) -> str:
        encoded = self._encode_repo(repo_full_name)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self._api(f"/projects/{encoded}/merge_requests/{pr_number}/notes"),
                headers=self._headers(),
                json={"body": body},
            )
            resp.raise_for_status()
            return str(resp.json()["id"])
