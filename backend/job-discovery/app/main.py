"""
FastAPI application — job-discovery API server.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.auth import guard_candidate_path
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
from app.api.pipeline import router as pipeline_router
from app.api.me import router as me_router
from app.api.conversations import router as conversations_router
from app.api.auth_routes import router as auth_router
from app.api.extension import router as extension_router
from app.api.inbox import router as inbox_router
from app.api.optout import router as optout_router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Additive, idempotent DDL for columns introduced after the initial
# `create_all` — that call never alters an existing table. Bridge until
# Alembic is wired in; each entry must stay safe to re-run.
_PENDING_COLUMNS = (
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS matching_criteria JSONB",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS resume_file BYTEA",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS resume_filename VARCHAR(255)",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS resume_mime VARCHAR(100)",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS cv_design JSONB",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS cv_content JSONB",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS signature_image TEXT",
    "ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS contact_json JSONB",
    "ALTER TABLE missions ADD COLUMN IF NOT EXISTS allowed_channels VARCHAR[]",
    "ALTER TABLE missions ADD COLUMN IF NOT EXISTS blocked_companies VARCHAR[]",
    # Boards découverts via un index web public (voir board_registry).
    "ALTER TYPE seedsource ADD VALUE IF NOT EXISTS 'ATS_INDEX'",
    # Instantané des pièces jointes : ce qui a été envoyé doit rester
    # téléchargeable tel quel, même si le candidat modifie son CV ensuite.
    "ALTER TABLE application_dispatches ADD COLUMN IF NOT EXISTS resume_blob BYTEA",
    "ALTER TABLE application_dispatches ADD COLUMN IF NOT EXISTS resume_name VARCHAR(255)",
    "ALTER TABLE application_dispatches ADD COLUMN IF NOT EXISTS letter_subject VARCHAR(500)",
    "ALTER TABLE application_dispatches ADD COLUMN IF NOT EXISTS letter_body TEXT",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS notification_prefs JSONB",
    "ALTER TABLE candidates ADD COLUMN IF NOT EXISTS auth_user_id UUID",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_candidates_auth_user_id ON candidates (auth_user_id)",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup (dev only — use Alembic in prod)."""
    # Import all models so they're registered with Base.metadata
    import app.models  # noqa: F401

    if settings.auth_bypassed:
        logger.warning(
            "AUTH_DISABLED=true : toutes les gardes sont levées. "
            "Réservé au développement local, jamais en production."
        )

    if settings.debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created (debug mode)")

    async with engine.begin() as conn:
        for statement in _PENDING_COLUMNS:
            try:
                await conn.execute(text(statement))
            except Exception as e:  # noqa: BLE001 — never block startup on DDL
                logger.warning("Schema bridge failed (%s): %s", statement, e)

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
    # Toute route dont le chemin désigne un candidat n'est accessible qu'à son
    # propriétaire. Posée ici, la garde couvre aussi les routes de demain.
    dependencies=[Depends(guard_candidate_path)],
)

# CORS — allow frontend
ALLOWED_ORIGINS = list(dict.fromkeys([
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3010",
    "http://localhost:3011",
    *settings.cors_origin_list,
]))
# Un appel refusé par CORS ne laisse qu'un « OPTIONS … 400 » dans les logs :
# la liste effective, écrite au démarrage, permet de comprendre pourquoi.
logger.info("Origines CORS autorisées : %s", ", ".join(ALLOWED_ORIGINS))
if not settings.debug and "localhost" in settings.frontend_url:
    # Les liens des e-mails (connexion, comptes rendus) mèneraient à localhost.
    logger.error(
        "FRONTEND_URL vaut %s : les liens envoyés par e-mail ne mèneront pas au site. "
        "Renseigner l'adresse publique du front (ex. https://alice-agent.fr).",
        settings.frontend_url,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
app.include_router(pipeline_router, prefix="/api")
app.include_router(me_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(extension_router, prefix="/api")
app.include_router(inbox_router, prefix="/api")
app.include_router(optout_router, prefix="/api")


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
