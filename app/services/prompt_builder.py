from app.models.rule import Rule
from app.services.git_hosts.base import DiffResult

_SYSTEM_PROMPT_TEMPLATE = """\
You are CodeSentinel, an expert code reviewer. Your task is to analyze the provided git diff and identify real, actionable issues.

RULES:
{custom_rules}
- Focus on bugs, security vulnerabilities, performance issues, and serious code quality problems.
- Ignore formatting/style issues unless they cause bugs.
- Only report issues with HIGH confidence. False positives are worse than missing an issue.
- Severity levels: "high" (bugs/security), "medium" (performance/logic), "low" (maintainability).

OUTPUT FORMAT:
Respond ONLY with a valid JSON array. No markdown, no explanation, no code blocks.
If no issues found, return an empty array [].

Example:
[
  {{"file": "src/auth.py", "line": 42, "severity": "high", "message": "SQL injection: use parameterized queries instead of string formatting"}},
  {{"file": "src/utils.py", "line": 10, "severity": "medium", "message": "N+1 query: move DB call outside loop"}}
]
"""

_MAX_DIFF_CHARS = 12000  # ~3000 tokens, safe for 7B models


def build_system_prompt(rules: list[Rule]) -> str:
    if rules:
        custom = "\n".join(
            f"- [{r.name}] {r.description or r.prompt_snippet or ''}"
            for r in rules
            if r.enabled
        )
    else:
        custom = "- Apply general best practices."
    return _SYSTEM_PROMPT_TEMPLATE.format(custom_rules=custom)


def build_user_prompt(diff: DiffResult, pr_title: str = "", pr_body: str = "") -> str:
    raw = diff.raw_diff
    if len(raw) > _MAX_DIFF_CHARS:
        raw = raw[:_MAX_DIFF_CHARS] + "\n\n[diff truncated — too large]"

    parts: list[str] = []
    if pr_title:
        parts.append(f"PR Title: {pr_title}")
    if pr_body:
        parts.append(f"PR Description: {pr_body[:500]}")
    parts.append(f"\nDiff:\n```diff\n{raw}\n```")
    return "\n".join(parts)


def chunk_diff(diff: DiffResult, max_lines: int) -> list[str]:
    """Split large diffs into reviewable chunks by file boundary."""
    chunks: list[str] = []
    current_lines: list[str] = []
    current_count = 0

    for line in diff.raw_diff.splitlines():
        if line.startswith("diff --git") and current_count >= max_lines:
            if current_lines:
                chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_count = 1
        else:
            current_lines.append(line)
            current_count += 1

    if current_lines:
        chunks.append("\n".join(current_lines))

    return chunks or [diff.raw_diff]
