from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PRInfo:
    number: int
    title: str
    url: str
    author: str
    base_branch: str
    head_branch: str
    body: str = ""


@dataclass
class DiffResult:
    raw_diff: str
    files_changed: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0

    @property
    def total_lines(self) -> int:
        return self.lines_added + self.lines_removed


class GitHostClient(ABC):
    @abstractmethod
    async def get_pr_info(self, repo_full_name: str, pr_number: int) -> PRInfo:
        ...

    @abstractmethod
    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> DiffResult:
        ...

    @abstractmethod
    async def post_review_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
    ) -> str:
        """Returns the comment ID as a string."""
        ...
