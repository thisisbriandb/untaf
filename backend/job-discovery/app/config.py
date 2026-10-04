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
        """
        Origines autorisées : CORS_ORIGINS, plus le site de FRONTEND_URL avec
        et sans « www. ». Oublier CORS_ORIGINS faisait refuser au navigateur
        chaque appel du site (OPTIONS → 400) alors que FRONTEND_URL, lui,
        était renseigné pour les e-mails.
        """
        origins = [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]
        front = self.frontend_url.strip().rstrip("/")
        if front.startswith(("http://", "https://")):
            scheme, _, host = front.partition("://")
            host = host.split("/", 1)[0]
            bare = host.removeprefix("www.")
            origins += [f"{scheme}://{bare}", f"{scheme}://www.{bare}"]
        return list(dict.fromkeys(origins))

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

    # ── Authentification ─────────────────────────────────
    # Connexion par e-mail (lien + code envoyés via Resend). L'API signe
    # elle-même les sessions avec AUTH_SECRET — une longue chaîne aléatoire,
    # à ne jamais changer en production (toutes les sessions tomberaient).
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    auth_secret: str = ""
    #: Durée de vie d'une session, en jours.
    session_days: int = 30
    #: Jetons Supabase Auth, acceptés en plus si un projet les émet : secret
    #: JWT du projet (HS256) ou JWKS public de SUPABASE_URL.
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    #: Développement local uniquement : lève toutes les gardes. Jamais en
    #: production — n'importe qui pourrait lire n'importe quel profil.
    auth_disabled: bool = False
    #: E-mails autorisés à déclencher scraping et seeding, séparés par des virgules.
    admin_emails: str = ""

    @property
    def auth_bypassed(self) -> bool:
        """
        Gardes levées : explicitement, ou en développement (DEBUG) quand
        aucune authentification n'est configurée — un `.env` local d'avant
        l'authentification ne doit pas bloquer toute l'application en 503.
        En production (DEBUG=false), l'absence de configuration reste un refus.
        """
        if self.auth_disabled:
            return True
        return self.debug and not (self.auth_secret or self.supabase_url or self.supabase_jwt_secret)

    @property
    def admin_email_list(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

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

    # ── La bonne alternance (API Apprentissage) ──────────
    # Clé gratuite d'un compte développeur sur api.apprentissage.beta.gouv.fr.
    # La recherche d'offres marche avec la clé de base ; l'envoi des
    # candidatures exige en plus la permission « candidature »
    # (applications:write), accordée par l'équipe La bonne alternance. Sans
    # cette permission, l'API répond 403 et Alice le signale.
    lba_api_key: str = ""
    lba_api_url: str = "https://api.apprentissage.beta.gouv.fr/api"

    @property
    def lba_configured(self) -> bool:
        return bool(self.lba_api_key.strip())

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
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    # ── E-mails (Resend, domaine alice-agent.fr) ─────────
    # Tout ce qui part — candidatures, notifications, liens de connexion,
    # alertes — passe par Resend quand la clé est là : un seul expéditeur
    # vérifié (SPF/DKIM du domaine), une seule délivrabilité à surveiller.
    # Le SMTP ci-dessus reste un repli.
    resend_api_key: str = ""
    mail_domain: str = "alice-agent.fr"
    #: Expéditeur des notifications et des liens de connexion.
    notify_from_email: str = ""
    notify_from_name: str = "Alice"
    #: Expéditeur des candidatures, affiché « Prénom Nom via Alice ». Les
    #: réponses du recruteur vont au candidat (Reply-To).
    application_from_email: str = ""
    #: Qui est prévenu quand Alice ne tient pas une promesse.
    ops_alert_email: str = "briand@alice-agent.fr"
    #: Racine du frontend, pour les liens des e-mails.
    frontend_url: str = "http://localhost:3000"

    @property
    def notify_sender(self) -> str:
        return self.notify_from_email or f"alice@{self.mail_domain}"

    @property
    def application_sender(self) -> str:
        return self.application_from_email or f"candidatures@{self.mail_domain}"

    @property
    def can_send_email(self) -> bool:
        """Une candidature par e-mail peut-elle réellement partir ?"""
        return bool(self.resend_api_key) or self.smtp_configured

    @property
    def can_notify(self) -> bool:
        return bool(self.resend_api_key) or self.smtp_configured

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
