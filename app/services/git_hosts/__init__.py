from app.services.git_hosts.base import DiffResult, GitHostClient, PRInfo
from app.services.git_hosts.gitea import GiteaProvider
from app.services.git_hosts.github import GitHubProvider
from app.services.git_hosts.gitlab import GitLabProvider
from app.utils.ssrf import is_ssrf_url

__all__ = [
    "GitHostClient",
    "PRInfo",
    "DiffResult",
    "GitHubProvider",
    "GitLabProvider",
    "GiteaProvider",
    "get_git_host_client",
]


def get_git_host_client(git_host: str, base_url: str | None, access_token: str | None) -> GitHostClient:
    if base_url and is_ssrf_url(base_url):
        raise ValueError(f"base_url targets a forbidden internal address: {base_url!r}")
    match git_host:
        case "github":
            return GitHubProvider(access_token=access_token)
        case "gitlab":
            return GitLabProvider(base_url=base_url or "https://gitlab.com", access_token=access_token)
        case "gitea":
            return GiteaProvider(base_url=base_url or "", access_token=access_token)
        case _:
            raise ValueError(f"Unknown git host: {git_host}")
