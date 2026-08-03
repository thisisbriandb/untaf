"""
Celery application — broker via Redis, with Beat schedule for daily scraping.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings


celery_app = Celery(
    "job_discovery",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,

    # Reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,

    # Rate limiting (respect target sites)
    worker_concurrency=settings.scrape_max_concurrent,

    # Auto-discover tasks in agents subpackages
    imports=[
        "app.agents.seeding.tasks",
        "app.agents.resolver.tasks",
        "app.agents.discovery.tasks",
    ],
)

# ── Beat Schedule ────────────────────────────────────────
# Daily scraping at 6 AM Paris time
celery_app.conf.beat_schedule = {
    "daily-scrape-greenhouse": {
        "task": "app.agents.discovery.tasks.scrape_all_greenhouse",
        "schedule": crontab(hour=6, minute=0),
    },
    "daily-scrape-lever": {
        "task": "app.agents.discovery.tasks.scrape_all_lever",
        "schedule": crontab(hour=6, minute=15),
    },
    # France Travail en premier : c'est la source la plus large, les ATS
    # viennent la compléter.
    "daily-ingest-france-travail": {
        "task": "app.agents.discovery.tasks.ingest_france_travail_daily",
        "schedule": crontab(hour=5, minute=30),
    },
    "daily-scrape-ashby": {
        "task": "app.agents.discovery.tasks.scrape_all_ashby",
        "schedule": crontab(hour=6, minute=30),
    },
    "daily-resolve-unresolved": {
        "task": "app.agents.resolver.tasks.resolve_unresolved_companies",
        "schedule": crontab(hour=5, minute=0),
    },
}
