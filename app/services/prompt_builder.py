from app.models.rule import Rule
from app.services.git_hosts.base import DiffResult

_SYSTEM_PROMPT_TEMPLATE = """\
You are CodeSentinel, an expert code reviewer specializing in {language_context}. \
Analyze the provided git diff and identify real, actionable issues.

REVIEW PRIORITIES (in order):
1. Security vulnerabilities (SQL injection, XSS, path traversal, hardcoded credentials, insecure deserialization)
2. Correctness bugs (null dereferences, off-by-one errors, race conditions, resource leaks)
3. Performance issues (N+1 queries, unbounded loops, missing indexes, memory leaks)
4. Error handling (uncaught exceptions, missing validation, silent failures)
5. Maintainability (only flag severe issues — dead code with side effects, misleading variable names)

CUSTOM RULES:
{custom_rules}

STRICT GUIDELINES:
- Only report issues that appear DIRECTLY in the diff (added/modified lines).
- Do NOT report issues in context lines (unchanged code shown for context).
- Only report issues with HIGH confidence. Missing one issue is better than a false positive.
- Severity: "high" = must fix before merge; "medium" = should fix; "low" = nice to fix.
- Keep messages under 120 characters. Be specific: "use parameterized query" not "SQL injection".

OUTPUT FORMAT:
Respond ONLY with a valid JSON array. No markdown, no explanation.
If no issues found, return: []

Format:
[{{"file": "path/to/file.py", "line": 42, "severity": "high", "message": "specific actionable message"}}]
"""

_MAX_DIFF_CHARS = 12000  # ~3000 tokens, safe for 7B models

_EXT_TO_LANGUAGE = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript/React",
    ".jsx": "JavaScript/React",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".scala": "Scala",
    ".sh": "Shell/Bash",
    ".sql": "SQL",
    ".tf": "Terraform",
    ".yaml": "YAML/Config",
    ".yml": "YAML/Config",
    ".json": "JSON/Config",
}


def detect_languages(diff: DiffResult) -> str:
    """Return a human-readable string of languages detected from changed file extensions."""
    from pathlib import PurePosixPath
    langs: set[str] = set()
    for f in diff.files_changed:
        ext = PurePosixPath(f).suffix.lower()
        lang = _EXT_TO_LANGUAGE.get(ext)
        if lang:
            langs.add(lang)
    if not langs:
        return "general software engineering"
    return ", ".join(sorted(langs))


def build_system_prompt(rules: list[Rule], diff: DiffResult | None = None) -> str:
    language_context = detect_languages(diff) if diff else "general software engineering"
    if rules:
        custom = "\n".join(
            f"- [{r.name}] {r.description or r.prompt_snippet or ''}"
            for r in rules
            if r.enabled
        )
    else:
        custom = "- Apply general best practices for the detected languages."
    return _SYSTEM_PROMPT_TEMPLATE.format(custom_rules=custom, language_context=language_context)


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
