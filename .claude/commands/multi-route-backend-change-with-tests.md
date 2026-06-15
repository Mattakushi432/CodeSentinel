---
name: multi-route-backend-change-with-tests
description: Workflow command scaffold for multi-route-backend-change-with-tests in CodeSentinel.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /multi-route-backend-change-with-tests

Use this workflow when working on **multi-route-backend-change-with-tests** in `CodeSentinel`.

## Goal

Coordinated backend changes affecting multiple route handlers, often for security, middleware, or settings updates, always accompanied by new or updated tests.

## Common Files

- `app/routers/auth.py`
- `app/routers/billing.py`
- `app/routers/dashboard.py`
- `app/routers/repositories.py`
- `app/routers/reviews.py`
- `app/routers/rules.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit multiple files in app/routers/ (e.g., auth.py, billing.py, repositories.py, reviews.py, rules.py, webhooks.py) to implement the change.
- Update shared backend logic or middleware (e.g., app/main.py, app/services/).
- Update or add Pydantic models or database logic if needed (e.g., app/models/, app/database.py).
- Update or add tests in tests/ (e.g., tests/conftest.py, tests/test_auth_router.py) to cover new logic or edge cases.
- Update requirements.txt if new dependencies are introduced.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.