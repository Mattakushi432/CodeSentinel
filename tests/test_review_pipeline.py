from app.services.git_hosts.base import DiffResult
from app.services.prompt_builder import build_system_prompt, build_user_prompt, chunk_diff
from app.services.review_pipeline import _format_review_comment, _parse_issues


class TestParseIssues:
    def test_valid_json_array(self):
        raw = '[{"file": "a.py", "line": 5, "severity": "high", "message": "SQL injection"}]'
        issues = _parse_issues(raw)
        assert len(issues) == 1
        assert issues[0]["severity"] == "high"

    def test_json_in_markdown_block(self):
        raw = '```json\n[{"file": "b.py", "severity": "medium", "message": "N+1 query"}]\n```'
        issues = _parse_issues(raw)
        assert len(issues) == 1

    def test_empty_array(self):
        assert _parse_issues("[]") == []

    def test_invalid_json_returns_empty(self):
        assert _parse_issues("not json at all") == []

    def test_non_array_returns_empty(self):
        assert _parse_issues('{"file": "a.py"}') == []

    def test_filters_invalid_issues(self):
        raw = '[{"file": "a.py"}, {"file": "b.py", "severity": "low", "message": "ok"}]'
        issues = _parse_issues(raw)
        assert len(issues) == 1  # first entry missing required fields


class TestFormatComment:
    def test_no_issues(self):
        comment = _format_review_comment([], "qwen2.5-coder", "Fix auth")
        assert "No issues found" in comment
        assert "qwen2.5-coder" in comment

    def test_with_issues(self):
        issues = [
            {"file": "auth.py", "line": 10, "severity": "high", "message": "SQL injection"},
            {"file": "utils.py", "line": None, "severity": "low", "message": "magic number"},
        ]
        comment = _format_review_comment(issues, "qwen2.5-coder", "Fix auth")
        assert "High" in comment
        assert "SQL injection" in comment
        assert "Low" in comment


class TestPromptBuilder:
    def test_build_system_prompt_no_rules(self):
        prompt = build_system_prompt([])
        assert "CodeSentinel" in prompt
        assert "JSON" in prompt

    def test_build_user_prompt(self):
        diff = DiffResult(raw_diff="+ added line\n- removed line", files_changed=["a.py"], lines_added=1, lines_removed=1)
        prompt = build_user_prompt(diff, "Fix bug", "Fixes the auth issue")
        assert "Fix bug" in prompt
        assert "added line" in prompt

    def test_chunk_diff_splits_by_file(self):
        raw = "\n".join([
            "diff --git a/a.py b/a.py",
            *[f"+line {i}" for i in range(600)],
            "diff --git a/b.py b/b.py",
            "+line in b",
        ])
        diff = DiffResult(raw_diff=raw, files_changed=["a.py", "b.py"], lines_added=601, lines_removed=0)
        chunks = chunk_diff(diff, max_lines=500)
        assert len(chunks) == 2
