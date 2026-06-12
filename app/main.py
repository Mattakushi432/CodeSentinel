import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from prometheus_client import make_asgi_app, Counter, Histogram, Gauge
from app.config import get_settings
from app.database import init_db
from app.worker.tasks import review_worker
from app.routers import auth, dashboard, repositories, reviews, rules, billing, webhooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Prometheus metrics
review_jobs_total = Counter("codesentinel_review_jobs_total", "Total review jobs", ["status"])
llm_inference_seconds = Histogram(
    "codesentinel_llm_inference_seconds",
    "LLM inference latency",
    buckets=[10, 30, 60, 120, 180, 300, 600],
)
queue_depth = Gauge("codesentinel_queue_depth", "Pending review jobs in queue")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")

    worker_task = asyncio.create_task(review_worker())
    logger.info("Background review worker started")

    yield

    worker_task.cancel()
    try:
        await worker_task
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

    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=86400 * 30)

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
        return RedirectResponse(url=exc.headers["Location"])

    return app


app = create_app()
