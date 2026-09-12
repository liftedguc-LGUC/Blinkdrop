from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from .repository import InMemoryRepository, Repository
from .routes_api import router as api_router
from .seed import JOBS, seed_records
from .static_files import router as static_router


def build_repository() -> Repository:
    settings = get_settings()
    if settings.backend == "firestore":
        from .firestore_repo import FirestoreRepository  # noqa: PLC0415 — optional dependency

        return FirestoreRepository(settings.project_id, settings.firestore_database)
    return InMemoryRepository(jobs={job.job_ref: job for job in JOBS})


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.repo = build_repository()
    if settings.seed_on_startup and await app.state.repo.count_exceptions() == 0:
        await seed_records(app.state.repo)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    # The schema documented every route including the seeding one, handing a
    # scanner a map of the mutation API. Off unless explicitly enabled.
    docs = {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}
    if not settings.expose_docs:
        docs = {"docs_url": None, "redoc_url": None, "openapi_url": None}

    app = FastAPI(title="Blinkdrop", lifespan=lifespan, **docs)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)

    # API first. The static catch-all is single-segment so it cannot shadow
    # /api/..., but /healthz is single-segment and genuinely does depend on
    # this order.
    app.include_router(api_router)
    app.include_router(static_router)
    return app


app = create_app()
