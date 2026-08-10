"""
FastAPI application — job-discovery API server.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.api.companies import router as companies_router
from app.api.jobs import router as jobs_router
from app.api.candidates import router as candidates_router
from app.api.applications import router as applications_router
from app.api.missions import router as missions_router
from app.api.dispatches import router as dispatches_router
from app.api.apply import router as apply_router
from app.api.chat import router as chat_router
from app.api.messages import router as messages_router
from app.api.auth import router as auth_router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup (dev only — use Alembic in prod)."""
    # Import all models so they're registered with Base.metadata
    import app.models  # noqa: F401

    if settings.debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created (debug mode)")

    yield

    await engine.dispose()


app = FastAPI(
    title="Untaf Job Discovery",
    description=(
        "Multi-agent pipeline for discovering hidden job postings "
        "from company career pages and ATS platforms."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3010",
        "http://localhost:3011",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length", "Content-Type"],
)

# Register API routers
app.include_router(companies_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(candidates_router, prefix="/api")
app.include_router(applications_router, prefix="/api")
app.include_router(missions_router, prefix="/api")
app.include_router(dispatches_router, prefix="/api")
app.include_router(apply_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(messages_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": settings.app_name}


@app.get("/api")
async def api_root():
    """API root — shows available endpoints."""
    return {
        "service": "job-discovery",
        "version": "0.1.0",
        "endpoints": {
            "companies": "/api/companies/",
            "companies_stats": "/api/companies/stats",
            "companies_seed": "/api/companies/seed",
            "jobs": "/api/jobs/",
            "jobs_stats": "/api/jobs/stats",
            "candidates": "/api/candidates/",
            "applications": "/api/applications/",
            "health": "/health",
        },
    }
