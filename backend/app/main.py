import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import settings
from app.database import init_db
from app.middleware.tenant import TenantMiddleware
from app.routers import candidates, jobs, pipeline, resumes, tenants, users
from app.schemas.common import ErrorDetail

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown hooks."""
    logger.info("Starting Smart ATS API (env=%s)", settings.ENVIRONMENT)
    if settings.ENVIRONMENT in ("development", "test"):
        # In production, use Alembic migrations instead
        await init_db()
        logger.info("Database tables created / verified")
    yield
    logger.info("Smart ATS API shutting down")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Smart Enterprise ATS API",
    version="1.0.0",
    description=(
        "B2B multi-tenant Applicant Tracking System with NLP-powered "
        "candidate parsing, semantic matching, and customizable pipeline management."
    ),
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware (order matters — outermost first) ──────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(tenants.router)
app.include_router(users.router)
app.include_router(jobs.router)
app.include_router(pipeline.router)
app.include_router(resumes.router)
app.include_router(candidates.router)


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorDetail(
            type="https://ats.api/errors/validation-error",
            title="Validation Error",
            status=422,
            detail=str(exc),
        ).model_dump(),
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorDetail(
            type="https://ats.api/errors/internal-server-error",
            title="Internal Server Error",
            status=500,
            detail="An unexpected error occurred. Please try again later.",
        ).model_dump(),
    )


# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/health", tags=["System"], include_in_schema=False)
async def health_check() -> dict:
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    }
