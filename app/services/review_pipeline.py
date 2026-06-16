import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.repository import Repository
from app.models.review import Review
from app.models.review_job import JobStatus, ReviewJob
from app.models.rule import Rule
from app.services.git_hosts import get_git_host_client
from app.services.git_hosts.base import DiffResult
from app.services.llm import get_llm_client
from app.services.prompt_builder import build_system_prompt, build_user_prompt, chunk_diff

logger = logging.getLogger(__name__)


def _parse_issues(raw_text: str) -> list[dict]:
    """Extract JSON array from LLM output. Handles markdown code blocks."""
    text = raw_text.strip()
    # Strip markdown code block if present
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        # Find first [ to last ]
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start : end + 1]

    try:
        issues = json.loads(text)
        if not isinstance(issues, list):
            return []
        # Validate each issue has required fields
        valid = []
        for issue in issues:
            if isinstance(issue, dict) and "severity" in issue and "message" in issue:
                valid.append({
                    "file": issue.get("file", ""),
                    "line": issue.get("line"),
                    "severity": issue.get("severity", "low"),
                    "message": str(issue.get("message", "")),
                })
        return valid
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse LLM JSON output: %s", raw_text[:200])
        return []


def _escape_md(text: str) -> str:
    """Escape LLM-generated text to prevent Markdown injection in PR comments."""
    return text.replace("[", "\\[").replace("]", "\\]").replace("<", "&lt;").replace(">", "&gt;")


def _format_review_comment(issues: list[dict], model: str, pr_title: str) -> str:
    if not issues:
        return (
            "## CodeSentinel Review\n\n"
            "No issues found in this PR.\n\n"
            f"<sub>Reviewed by {model}</sub>"
        )

    high = [i for i in issues if i["severity"] == "high"]
    medium = [i for i in issues if i["severity"] == "medium"]
    low = [i for i in issues if i["severity"] == "low"]

    lines = ["## CodeSentinel Review\n"]

    if high:
        lines.append(f"### High ({len(high)})\n")
        for i in high:
            loc = f"`{_escape_md(i['file'])}`" + (f" line {i['line']}" if i.get("line") else "")
            lines.append(f"- **{loc}**: {_escape_md(i['message'])}")
        lines.append("")

    if medium:
        lines.append(f"### Medium ({len(medium)})\n")
        for i in medium:
            loc = f"`{_escape_md(i['file'])}`" + (f" line {i['line']}" if i.get("line") else "")
            lines.append(f"- **{loc}**: {_escape_md(i['message'])}")
        lines.append("")

    if low:
        lines.append(f"### Low ({len(low)})\n")
        for i in low:
            loc = f"`{_escape_md(i['file'])}`" + (f" line {i['line']}" if i.get("line") else "")
            lines.append(f"- **{loc}**: {_escape_md(i['message'])}")
        lines.append("")

    lines.append(f"<sub>Reviewed by {model} | CodeSentinel</sub>")
    return "\n".join(lines)


def _categorize_error(exc: Exception) -> str:
    name = type(exc).__name__
    msg = str(exc)
    if "timeout" in msg.lower() or "Timeout" in name:
        return "LLM request timed out"
    if "ConnectError" in name or "ConnectionError" in name:
        return "Could not reach LLM or Git host — check network/config"
    if "401" in msg or "403" in msg or "Unauthorized" in msg or "Forbidden" in msg:
        return "Git host authentication failed — check access token"
    if "404" in msg or "Not Found" in msg:
        return "Repository or PR not found on Git host"
    if "rate limit" in msg.lower() or "429" in msg:
        return "Git host rate limit exceeded — retry later"
    if "JSONDecodeError" in name or "json" in msg.lower():
        return "LLM returned invalid JSON — review prompt or model"
    return "Internal error — check server logs for details"


async def run_review(job_id: int, db: Session) -> None:
    settings = get_settings()

    job: ReviewJob | None = db.get(ReviewJob, job_id)
    if not job or job.status != JobStatus.pending:
        return

    job.status = JobStatus.processing
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    try:
        repo: Repository = job.repository
        org = repo.organization
        git_client = get_git_host_client(repo.git_host, repo.base_url, repo.get_access_token())
        llm_client = get_llm_client()

        pr_info = await git_client.get_pr_info(repo.repo_full_name, job.pr_number)
        diff = await git_client.get_pr_diff(repo.repo_full_name, job.pr_number)

        job.diff_lines = diff.total_lines
        job.pr_title = (pr_info.title or "")[:500]
        job.pr_url = (pr_info.url or "")[:500]
        job.pr_author = (pr_info.author or "")[:255]

        if diff.total_lines == 0:
            job.status = JobStatus.skipped
            job.error_msg = "Empty diff"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        rules: list[Rule] = (
            db.query(Rule)
            .filter(Rule.org_id == repo.org_id, Rule.enabled == True)  # noqa: E712
            .all()
        )
        system_prompt = build_system_prompt(rules, diff)

        all_issues: list[dict] = []
        raw_outputs: list[str] = []

        if diff.total_lines > settings.max_diff_lines:
            chunks = chunk_diff(diff, settings.max_diff_lines)
        else:
            chunks = [diff.raw_diff]

        for chunk in chunks:
            chunk_diff_obj = DiffResult(raw_diff=chunk, files_changed=[], lines_added=0, lines_removed=0)
            user_prompt = build_user_prompt(chunk_diff_obj, pr_info.title, pr_info.body)
            llm_resp = await llm_client.generate(system_prompt, user_prompt)
            raw_outputs.append(llm_resp.text)
            all_issues.extend(_parse_issues(llm_resp.text))
            job.model_used = llm_resp.model

        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for issue in all_issues:
            sev = issue.get("severity", "low")
            if sev in severity_counts:
                severity_counts[sev] += 1

        comment_body = _format_review_comment(all_issues, job.model_used or "qwen2.5-coder", pr_info.title)
        comment_id = await git_client.post_review_comment(repo.repo_full_name, job.pr_number, comment_body)

        review = Review(
            job_id=job.id,
            issues_json=all_issues,
            severity_high=severity_counts["high"],
            severity_medium=severity_counts["medium"],
            severity_low=severity_counts["low"],
            posted_comment_id=comment_id,
            raw_llm_output="\n---\n".join(raw_outputs),
        )
        db.add(review)

        org.increment_monthly_reviews(db)
        job.status = JobStatus.done
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Job %d completed: %d issues found", job_id, len(all_issues))

    except Exception as exc:
        logger.exception("Job %d failed: %s", job_id, exc)
        job.status = JobStatus.error
        job.error_msg = _categorize_error(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
