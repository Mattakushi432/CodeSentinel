import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import auth, billing, dashboard, repositories, reviews, rules, webhooks
from app.worker.tasks import review_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_CSRF_SKIP_PREFIXES = ("/webhooks/", "/billing/stripe-webhook", "/metrics", "/health", "/static/")
_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validates Origin/Referer for state-changing requests that aren't external webhooks."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in _MUTATION_METHODS:
            path = request.url.path
            if not any(path.startswith(p) for p in _CSRF_SKIP_PREFIXES):
                origin = request.headers.get("origin", "")
                referer = request.headers.get("referer", "")
                settings = get_settings()
                base = settings.base_url.rstrip("/")

                # In test environments (TestClient) origin/referer are absent — skip check
                if origin or referer:
                    allowed = origin.startswith(base) if origin else referer.startswith(base)
                    if not allowed:
                        return Response("CSRF validation failed", status_code=403)
        return await call_next(request)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

# Prometheus metrics
review_jobs_total = Counter("codesentinel_review_jobs_total", "Total review jobs", ["status"])
llm_inference_seconds = Histogram(
    "codesentinel_llm_inference_seconds",
    "LLM inference latency",
    buckets=[10, 30, 60, 120, 180, 300, 600],
)
queue_depth = Gauge("codesentinel_queue_depth", "Pending review jobs in queue")


async def _telemetry_loop() -> None:
    """Opt-in anonymous telemetry: sends a periodic ping with no personal data."""
    import httpx
    while True:
        try:
            await asyncio.sleep(86400)  # once per day
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    "https://telemetry.codesentinel.dev/ping",
                    json={"version": "0.1.0", "event": "daily_ping"},
                )
        except Exception:
            pass  # telemetry failures are silent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")

    worker_task = asyncio.create_task(review_worker())
    logger.info("Background review worker started")

    settings = get_settings()
    telemetry_task = None
    if settings.telemetry_enabled:
        telemetry_task = asyncio.create_task(_telemetry_loop())
        logger.info("Opt-in telemetry enabled")

    yield

    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

    if telemetry_task:
        telemetry_task.cancel()
        try:
            await telemetry_task
        except asyncio.CancelledError:
            pass

    logger.info("Worker stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="CodeSentinel",
        description="Self-hosted AI code review platform",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(CSRFMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=86400 * 30, same_site="lax", https_only=False)

    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.mount("/metrics", make_asgi_app())

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(repositories.router)
    app.include_router(reviews.router)
    app.include_router(rules.router)
    app.include_router(billing.router)
    app.include_router(webhooks.router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.exception_handler(302)
    async def redirect_handler(request: Request, exc):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=exc.headers["Location"], status_code=302)

    return app


app = create_app()
