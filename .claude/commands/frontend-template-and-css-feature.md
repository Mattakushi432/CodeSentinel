---
name: frontend-template-and-css-feature
description: Workflow command scaffold for frontend-template-and-css-feature in CodeSentinel.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /frontend-template-and-css-feature

Use this workflow when working on **frontend-template-and-css-feature** in `CodeSentinel`.

## Goal

Frontend feature or redesign that consistently updates multiple HTML templates and shared CSS, often for new UI elements or visual effects.

## Common Files

- `app/templates/auth/login.html`
- `app/templates/auth/magic_link_sent.html`
- `app/templates/base.html`
- `app/templates/dashboard/index.html`
- `app/templates/dashboard/repos.html`
- `app/templates/dashboard/review_detail.html`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit or add multiple HTML template files in app/templates/ (e.g., login, dashboard, reviews, partials).
- Update shared CSS (e.g., app/static/css/main.css) to implement new styles or animations.
- Optionally update or add JavaScript for interactive effects.
- Test changes across all affected pages for consistency and accessibility.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.