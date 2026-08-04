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

    # Courtier injoignable : échouer vite plutôt que faire attendre.
    # Par défaut kombu réessaie une vingtaine de secondes, ce qui transforme
    # « Redis n'est pas lancé » en requête HTTP qui pend puis retombe en 500.
    # Le worker, lui, garde son comportement de reconnexion au démarrage.
    broker_transport_options={
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "max_retries": 0,
    },
    # Même chose côté magasin de résultats : c'est lui, et non le courtier,
    # qui retentait pendant une vingtaine de secondes à chaque enfilement.
    result_backend_transport_options={
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "retry_policy": {"timeout": 2.0},
    },

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
    # Le registre des boards ATS bouge lentement : un passage par semaine
    # suffit, et il tourne avant les scrapes du jour.
    "weekly-discover-ats-boards": {
        "task": "app.agents.discovery.tasks.discover_ats_boards",
        "schedule": crontab(hour=4, minute=0, day_of_week=1),
    },
    # Une mission dont le worker est mort doit être close vite : Alice ne
    # doit jamais annoncer un travail en cours qui n'a plus lieu.
    "sweep-stale-missions": {
        "task": "app.agents.discovery.tasks.sweep_stale_missions",
        "schedule": crontab(minute="*/5"),
    },
    "daily-resolve-unresolved": {
        "task": "app.agents.resolver.tasks.resolve_unresolved_companies",
        "schedule": crontab(hour=5, minute=0),
    },
}
