# CodeSentinel

CodeSentinel is a self-hosted AI code review platform that automatically reviews pull requests and posts inline comments to GitHub, GitLab, and Gitea. It runs entirely on your own hardware using [Ollama](https://ollama.com/) for local LLM inference — no code or diffs ever leave your server. An optional [Groq](https://groq.com/) API fallback is available for burst capacity. A single Docker Compose stack — FastAPI app, Ollama, and Caddy reverse proxy — is all you need to get started. A CPU-only server with 8 GB of RAM is sufficient to run the default 7B coding model.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Webhook Setup](#webhook-setup)
- [Plans & Billing](#plans--billing)
- [Development Setup](#development-setup)
- [Architecture Overview](#architecture-overview)
- [License](#license)

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Docker + Docker Compose v2 | `docker compose version` >= 2.0 |
| 8 GB RAM | 6 GB reserved for Ollama (7B model), 2 GB for OS + app |
| CPU | No GPU required — Ollama runs on CPU by default |
| Publicly reachable URL | Required for webhook delivery from GitHub/GitLab/Gitea; see [Cloudflare Tunnel guide](docs/cloudflare_tunnel.md) for home servers |

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/Mattakushi432/CodeSentinel.git
cd CodeSentinel

# 2. Copy and edit the environment file
cp .env.example .env
# At minimum, set SECRET_KEY to a random 32-byte hex string:
#   python -c "import secrets; print(secrets.token_hex(32))"
# Also set BASE_URL to your public URL (needed for webhook URLs)

# 3. Start all services
docker compose up -d

# 4. Pull the default LLM model (downloads ~4 GB, do this once)
docker exec codesentinel_ollama ollama pull qwen2.5-coder:7b-instruct

# 5. Open the UI
open http://localhost:8000
```

> **First run note:** The app waits for Ollama to pass its healthcheck before dispatching review jobs, so the model pull can happen concurrently while the app is already running. You will see `worker: no pending jobs` in the logs until a webhook arrives.

---

## Configuration

All settings are loaded from the `.env` file. Copy `.env.example` and adjust the values below. Every variable has a working default so you only need to touch what you care about.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./data/codesentinel.db` | SQLAlchemy connection string. Switch to `postgresql+psycopg2://user:pass@host/db` for production multi-writer workloads. |
| `SECRET_KEY` | `change-me-in-production` | Random secret used to sign sessions and magic-link tokens. **Must be changed before going live.** Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `BASE_URL` | `http://localhost:8000` | Public base URL of the deployment. Used to construct webhook URLs shown in the UI and links inside emails. |

### LLM

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama` for local inference, `groq` to route through the Groq cloud API. |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | URL of the Ollama API. Change to `http://localhost:11434` if running Ollama outside Docker. |
| `OLLAMA_MODEL` | `qwen2.5-coder:7b-instruct` | Ollama model tag. Any model available via `ollama pull` works; 7B is the recommended minimum. |
| `GROQ_API_KEY` | *(empty)* | Groq API key. Required only when `LLM_PROVIDER=groq`. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model ID. |

### Email

Magic-link authentication requires SMTP. [Resend](https://resend.com) offers 3,000 free emails/month and works out of the box with the defaults.

| Variable | Default | Description |
|----------|---------|-------------|
| `SMTP_HOST` | *(empty)* | SMTP server hostname, e.g. `smtp.resend.com`. Leave empty to disable email (useful for local dev). |
| `SMTP_PORT` | `587` | SMTP port. Use `587` for STARTTLS or `465` for implicit SSL. |
| `SMTP_USER` | *(empty)* | SMTP username. |
| `SMTP_PASSWORD` | *(empty)* | SMTP password or API key. |
| `SMTP_FROM` | `noreply@codesentinel.dev` | Sender address for outgoing emails. |

### Stripe Billing

Leave all Stripe variables empty to disable billing — all users will have unrestricted access.

| Variable | Default | Description |
|----------|---------|-------------|
| `STRIPE_SECRET_KEY` | *(empty)* | Stripe secret key (`sk_live_...` or `sk_test_...`). |
| `STRIPE_WEBHOOK_SECRET` | *(empty)* | Stripe webhook signing secret (`whsec_...`). Obtain from the Stripe Dashboard after adding a webhook endpoint. |
| `STRIPE_PRICE_PRO` | *(empty)* | Stripe Price ID for the Pro monthly plan (`price_...`). |
| `STRIPE_PRICE_TEAM` | *(empty)* | Stripe Price ID for the Team monthly plan (`price_...`). |

### Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_DIFF_LINES` | `500` | Maximum diff lines sent to the LLM per review. Larger diffs are truncated to this limit to keep inference times predictable. |
| `WORKER_POLL_INTERVAL` | `10` | Seconds between database polls for pending review jobs. |
| `LLM_TIMEOUT` | `300` | Seconds to wait for an LLM response before marking a job as failed. Increase for very large diffs on slow hardware. |

### Caddy

| Variable | Default | Description |
|----------|---------|-------------|
| `CADDY_DOMAIN` | *(empty)* | Your public domain, e.g. `review.example.com`. Caddy provisions a Let's Encrypt TLS certificate automatically when this is set. |

---

## Webhook Setup

See [docs/webhook_setup.md](docs/webhook_setup.md) for full step-by-step instructions for GitHub, GitLab, and Gitea.

**Quick summary:**

1. Add a repository in the CodeSentinel dashboard — you will be shown a webhook URL and a generated secret.
2. Register that URL and secret in your git host's webhook settings, selecting pull request / merge request events only.
3. Open a PR — CodeSentinel receives the webhook, queues a review job, runs inference, and posts comments when done.

The webhook endpoint pattern is:

```
{BASE_URL}/webhooks/{repo_id}
```

If your server is behind a home router or firewall, follow [docs/cloudflare_tunnel.md](docs/cloudflare_tunnel.md) to make it reachable without opening a port.

---

## Plans & Billing

Billing is fully optional. When no Stripe keys are configured, every user gets unrestricted access.

| Plan | Price | Reviews / month | Repositories | Seats |
|------|-------|-----------------|--------------|-------|
| Free | $0 | 25 | 1 | 1 |
| Pro | $19/mo | 500 | 10 | 1 |
| Team | $49/mo | Unlimited | Unlimited | 10 |

Stripe handles payment processing and sends webhooks to `/billing/webhook` to update subscription status in real time.

---

## Development Setup

```bash
# Python 3.12+ required
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements-dev.txt

# Configure local environment
cp .env.example .env
# Set SECRET_KEY; DATABASE_URL can stay as SQLite for local dev

# Apply database migrations
alembic upgrade head

# Start the dev server with auto-reload
uvicorn app.main:app --reload

# Run the full test suite with coverage
pytest --cov=app --cov-report=term-missing

# Lint and format
ruff check .
ruff format .
```

To run Ollama locally without Docker:

```bash
# Install Ollama (https://ollama.com/download) then:
ollama pull qwen2.5-coder:7b-instruct
ollama serve
# In .env: OLLAMA_BASE_URL=http://localhost:11434
```

### Smoke Test

Validate a running deployment against live HTTP endpoints (stdlib only, no extra installs):

```bash
python scripts/smoke_test.py --base-url http://localhost:8000
```

---

## Architecture Overview

CodeSentinel is a deliberately simple **FastAPI monolith** — no microservices, no external message broker.

```
Browser / Git host
      |
   Caddy  (TLS termination, reverse proxy → :8000)
      |
  FastAPI app
   ├── Jinja2 + HTMX UI    /dashboard, /repositories, /reviews, /rules
   ├── REST API             /api/docs  (Swagger UI)
   ├── Webhook receiver     /webhooks/{repo_id}
   ├── Stripe webhooks      /billing/webhook
   └── Prometheus metrics   /metrics
      |
  Background worker  (asyncio task — polls DB every WORKER_POLL_INTERVAL seconds)
      |
   Ollama              (local LLM inference, CPU-only, mem_limit: 6g)
   SQLite / PostgreSQL  (review_jobs, repositories, users, organizations)
```

**Key design decisions:**

- **No Celery / Redis.** The review worker is a single `asyncio.create_task` that polls the `review_jobs` table. This keeps the Docker stack to three containers and eliminates broker operational overhead.
- **SQLite for small teams.** Perfectly adequate for tens of reviews per day. Switch to PostgreSQL via `DATABASE_URL` when you need concurrent writers or horizontal scaling.
- **Magic-link auth.** Signed JWTs delivered by email — no password storage, no OAuth complexity.
- **Prometheus-first observability.** Key metrics (job counts, LLM latency, queue depth) are exposed at `/metrics`. A Grafana dashboard and Prometheus alerting rules are provided in `monitoring/`.

---

## License

MIT — see [LICENSE](LICENSE).
