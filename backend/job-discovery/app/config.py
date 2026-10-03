"""
Application settings — loaded from environment variables.
Railway injects DATABASE_URL and REDIS_URL automatically.
"""

from pydantic import field_validator
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

    # ── CORS ─────────────────────────────────────────────
    # Origines autorisées en plus de localhost, séparées par des virgules.
    # En production : l'URL du frontend Vercel, ex. https://untaf.vercel.app
    cors_origins: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    # ── Database (PostgreSQL) ────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_discovery"

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg(cls, url: str) -> str:
        # Railway et Supabase fournissent postgres:// ou postgresql:// ; le
        # moteur est asynchrone et exige le pilote asyncpg.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix):]
        return url

    # Connexions ouvertes par processus (API, chaque worker). Le pooler de
    # Supabase en plafonne le total selon l'offre : 3 + 2 suffit largement à
    # ce volume, et laisse de la place au worker et au beat.
    db_pool_size: int = 5
    db_max_overflow: int = 10

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
    gemini_model: str = "gemini-3.8-flash"

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

    # ── Notifications au candidat ────────────────────────
    # Alice écrit au candidat (fin de mission, candidature partie, relances).
    # Resend est essayé en premier — un service transactionnel délivre mieux
    # qu'une boîte SMTP personnelle ; à défaut, le SMTP ci-dessus sert aussi.
    # Sans l'un ni l'autre, la notification est enregistrée en SIMULATED.
    resend_api_key: str = ""
    notify_from_email: str = ""
    notify_from_name: str = "Alice · Untaf"
    #: Racine du frontend, pour les liens des e-mails.
    frontend_url: str = "http://localhost:3000"

    @property
    def can_notify(self) -> bool:
        return bool(self.resend_api_key and self.notify_from_email) or self.can_send_email

    # ── Suivi des candidatures ───────────────────────────
    #: Jours sans réponse après lesquels Alice propose une relance.
    followup_after_days: int = 7

    # ── Candidature par pilotage navigateur ──────────────
    # Interrupteur volontairement distinct de l'autorisation du mandat. Le
    # mandat dit « tu peux postuler pour moi » ; ceci dit « ce déploiement a le
    # droit de cliquer sur Soumettre ». Tant que c'est faux, l'agent remplit le
    # formulaire et s'arrête avant l'envoi — la candidature est enregistrée en
    # SIMULATED, jamais en SENT.
    #
    # Même logique que SMTP : sans configuration explicite, on répète, on
    # n'envoie pas.
    browser_submit_enabled: bool = False
    #: Un navigateur visible aide à comprendre un échec en développement.
    browser_headless: bool = True

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
