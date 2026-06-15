import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import init_db
from app.limiter import limiter
from app.routers import auth, billing, dashboard, repositories, reviews, rules, webhooks
from app.worker.tasks import review_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_CSRF_SKIP_PREFIXES = ("/webhooks/", "/billing/stripe-webhook", "/metrics", "/health", "/static/")
_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validates Origin/Referer for state-changing requests that aren't external webhooks."""

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._base = get_settings().base_url.rstrip("/")

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in _MUTATION_METHODS:
            path = request.url.path
            if not any(path.startswith(p) for p in _CSRF_SKIP_PREFIXES):
                origin = request.headers.get("origin", "")
                referer = request.headers.get("referer", "")
                allowed = origin.startswith(self._base) if origin else referer.startswith(self._base)
                if not allowed:
                    return Response("CSRF validation failed", status_code=403)
        return await call_next(request)


_STATIC_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers and generates a per-request CSP nonce for inline scripts."""

    async def dispatch(self, request: Request, call_next) -> Response:
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)

        csp = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data:; "
            f"font-src 'self' https://fonts.gstatic.com; "
            f"connect-src 'self'; "
            f"frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp
        for header, value in _STATIC_SECURITY_HEADERS.items():
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
        except Exception as exc:
            logger.debug("Telemetry ping failed (non-fatal): %s", exc)


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


class HealthResponse(BaseModel):
    status: str
    version: str


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="CodeSentinel",
        description="Self-hosted AI code review platform",
        version="0.1.0",
        docs_url="/api/docs" if settings.dev_mode else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    _https = settings.base_url.startswith("https://")
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=86400 * 30, same_site="lax", https_only=_https)

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    if settings.metrics_token:
        _raw_metrics = make_asgi_app()

        async def _guarded_metrics(scope, receive, send):
            if scope["type"] == "http":
                headers = dict(scope.get("headers", []))
                auth_header = headers.get(b"authorization", b"").decode()
                expected = f"Bearer {settings.metrics_token}"
                if auth_header != expected:
                    await send({"type": "http.response.start", "status": 401, "headers": [[b"content-length", b"0"]]})
                    await send({"type": "http.response.body", "body": b""})
                    return
            await _raw_metrics(scope, receive, send)

        app.mount("/metrics", _guarded_metrics)

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(repositories.router)
    app.include_router(reviews.router)
    app.include_router(rules.router)
    app.include_router(billing.router)
    app.include_router(webhooks.router)

    if settings.dev_mode:
        app.add_api_route("/auth/dev-login", auth.dev_login, methods=["GET"])

    @app.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(status="ok", version="0.1.0")

    @app.exception_handler(auth._LoginRequired)
    async def login_required_handler(request: Request, exc: auth._LoginRequired):
        return RedirectResponse(url="/auth/login", status_code=302)

    return app


app = create_app()
