"""
Application settings — loaded from environment variables.
Railway injects DATABASE_URL and REDIS_URL automatically.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Core ─────────────────────────────────────────────
    app_name: str = "job-discovery"
    debug: bool = False

    # ── Database (PostgreSQL) ────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_discovery"

    # ── Redis (Celery broker + result backend) ───────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Scraping ─────────────────────────────────────────
    scrape_interval_hours: int = 24
    scrape_request_timeout: int = 15  # seconds
    scrape_max_concurrent: int = 10
    scrape_user_agent: str = (
        "Mozilla/5.0 (compatible; UntafBot/1.0; +https://untaf.com/bot)"
    )

    # ── SIRENE API (INSEE) ───────────────────────────────
    sirene_api_token: str = ""

    # ── France Travail (API Offres d'emploi v2) ──────────
    # Les noms d'origine du .env sont conservés : IDENTIFIER_* porte le
    # client_id (PAR_…), FRANCE_TRAVAIL_API le secret.
    identifier_france_travail: str = ""
    france_travail_api: str = ""

    @property
    def france_travail_client_id(self) -> str:
        return self.identifier_france_travail.strip()

    @property
    def france_travail_client_secret(self) -> str:
        return self.france_travail_api.strip()

    # ── Gemini API (LLM) ─────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # ── Envoi de candidatures (SMTP) ─────────────────────
    # Tant que ces valeurs sont vides, aucune candidature ne peut partir : le
    # dispatcher bascule en simulation et le dit, il ne prétend jamais avoir
    # envoyé.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "Candidature"
    smtp_use_tls: bool = True

    @property
    def can_send_email(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    # ── Matching ─────────────────────────────────────────
    # Score minimum pour qu'une offre entre dans la liste du candidat.
    match_min_score: int = 55
    # Score à partir duquel l'offre passe en MATCHED (haut du panier).
    match_shortlist_score: int = 78


    @property
    def celery_broker_url(self) -> str:
        return self.redis_url

    @property
    def celery_result_backend(self) -> str:
        return self.redis_url


settings = Settings()
