# Contributing to CodeSentinel

Thank you for taking the time to contribute. CodeSentinel is a small, focused project — pull requests, bug reports, and documentation improvements are all welcome.

---

## Table of Contents

- [Development Environment](#development-environment)
- [Code Style](#code-style)
- [Running Tests](#running-tests)
- [Branch Naming](#branch-naming)
- [Pull Request Requirements](#pull-request-requirements)
- [Reporting Issues](#reporting-issues)
- [Architecture Notes](#architecture-notes)

---

## Development Environment

### Requirements

- Python 3.12 or newer
- Docker + Docker Compose v2 (optional but recommended for Ollama)
- Git

### Setup

```bash
# 1. Fork and clone
git clone https://github.com/<your-username>/CodeSentinel.git
cd CodeSentinel

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install all dev dependencies
pip install -r requirements-dev.txt

# 4. Configure your local environment
cp .env.example .env
# Minimum required: set a SECRET_KEY
# DATABASE_URL defaults to SQLite — no external DB needed for development

# 5. Apply migrations
alembic upgrade head

# 6. Start the dev server
uvicorn app.main:app --reload
```

The app will be available at `http://localhost:8000`. The Swagger UI is at `http://localhost:8000/api/docs`.

### Running Ollama locally (optional)

Install [Ollama](https://ollama.com/download), pull a model, then point `.env` at it:

```bash
ollama pull qwen2.5-coder:7b-instruct
ollama serve
```

```dotenv
# .env
OLLAMA_BASE_URL=http://localhost:11434
```

Alternatively, start only the Ollama container from Docker Compose:

```bash
docker compose up ollama -d
```

---

## Code Style

- **Formatter & linter:** [Ruff](https://docs.astral.sh/ruff/) — both formatting and linting are handled by Ruff. No Black, no Flake8.
- **Python version:** 3.12+. Use modern syntax: `X | Y` unions, `match` statements, `tomllib`, etc.
- **Type hints:** Required on all function signatures (parameters and return types). Use `from __future__ import annotations` only when needed for forward references.
- **Imports:** Absolute imports only. No relative imports (`from .foo import bar`).
- **Docstrings:** Write a one-line docstring for public functions and classes. Full Google-style docstrings for anything non-trivial.
- **No heavy dependencies:** See [Architecture Notes](#architecture-notes).

### Running the linter

```bash
# Check for issues
ruff check .

# Auto-fix safe issues
ruff check --fix .

# Format code
ruff format .
```

CI will fail if `ruff check .` exits non-zero or if `ruff format --check .` finds unformatted files.

---

## Running Tests

```bash
# Full suite with coverage report
pytest --cov=app --cov-report=term-missing

# Run a single test file
pytest tests/test_review_pipeline.py -v

# Run tests matching a keyword
pytest -k "webhook" -v

# Run with verbose output and stop on first failure
pytest -x -v
```

Tests use SQLite in-memory databases and mock external services (Ollama, GitHub API). They do not require a running server or network access.

### Coverage

The CI gate is currently set at **60% line coverage**. New code should include tests. If you add a new module, add a corresponding test file under `tests/`. Do not submit a PR that drops the project-wide coverage percentage.

---

## Branch Naming

Use the following prefixes:

| Prefix | When to use |
|--------|-------------|
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring without behaviour change |
| `test/` | Adding or fixing tests |
| `ci/` | CI/CD pipeline changes |

Examples:

```
feature/gitea-oauth
fix/webhook-signature-verification
docs/cloudflare-tunnel-guide
```

---

## Pull Request Requirements

Before opening a PR, make sure all of the following are true:

- [ ] `ruff check .` passes with no errors
- [ ] `ruff format --check .` passes (code is formatted)
- [ ] `pytest --cov=app` passes — all tests green
- [ ] Overall coverage has not dropped compared to the base branch
- [ ] New features include at least one test
- [ ] Public API changes (routes, models) are reflected in docstrings
- [ ] The PR description explains **why** the change is needed, not just what changed

### PR title format

Use the conventional commits style:

```
feat: add Gitea OAuth login
fix: verify webhook HMAC before reading body
docs: add Cloudflare Tunnel setup guide
refactor: extract LLM prompt builder to separate module
```

### Merging

PRs are squash-merged into `main`. Keep commits on your branch as granular as you like during development — they will be squashed.

---

## Reporting Issues

Use GitHub Issues. When reporting a bug, include:

1. CodeSentinel version (or commit hash)
2. Python version and OS
3. Relevant `.env` settings (redact secrets)
4. Full traceback from the app logs (`docker compose logs app`)
5. Steps to reproduce

For security vulnerabilities, **do not open a public issue.** Email the maintainer directly (see the GitHub profile).

---

## Architecture Notes

These constraints keep CodeSentinel simple to self-host. Please respect them when contributing:

**Keep the stack to three containers.**
`app` + `ollama` + `caddy`. Do not add Redis, RabbitMQ, a separate worker container, or any other service that increases the operational surface area for self-hosters.

**No new heavy dependencies.**
Before adding a new package, check `requirements.txt`. If a stdlib module or a small utility already in the tree can do the job, prefer that. For async HTTP, use `httpx` (already a dependency). For task queuing, extend the existing asyncio worker — do not introduce Celery or similar.

**Keep the monolith flat.**
All application code lives under `app/`. Sub-packages are: `models/`, `routers/`, `services/`, `services/git_hosts/`, `services/llm/`, `worker/`. Adding a new concern? Pick the right sub-package; do not create new top-level packages under `app/`.

**Database migrations via Alembic.**
Every schema change must have an Alembic migration in `alembic/versions/`. Never use `Base.metadata.create_all()` in production paths.

**No server-side JavaScript build step.**
The UI uses Jinja2 templates + HTMX + vanilla CSS. Do not introduce a Node.js build pipeline, webpack, or a frontend framework that requires compilation.
