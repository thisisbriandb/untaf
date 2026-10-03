#!/bin/sh
# Point d'entrée de l'image. Une seule image, trois services Railway :
# chacun choisit son rôle par la variable ROLE.
#
#   ROLE=web     API FastAPI (défaut) — applique les migrations au démarrage
#   ROLE=worker  worker Celery
#   ROLE=beat    planificateur Celery (une seule instance, jamais plus)
set -e

echo "[start] rôle : ${ROLE:-web}"

case "${ROLE:-web}" in
  web)
    # L'hôte de la base, sans le mot de passe. La « Direct connection » de
    # Supabase (db.<ref>.supabase.co) n'existe qu'en IPv6, que Railway ne
    # sort pas : on le dit en clair plutôt que par une pile d'appels.
    python - <<'EOF'
import os, sys
from urllib.parse import urlsplit
url = urlsplit(os.environ.get("DATABASE_URL", ""))
print(f"[start] base : {url.username}@{url.hostname}:{url.port}", flush=True)
host = url.hostname or ""
if host.startswith("db.") and host.endswith(".supabase.co"):
    print(
        "[start] ERREUR : DATABASE_URL pointe sur la « Direct connection » de "
        "Supabase, joignable en IPv6 seulement. Utiliser la chaîne « Session "
        "pooler » (hôte aws-0-<région>.pooler.supabase.com, utilisateur "
        "postgres.<ref>).", file=sys.stderr, flush=True,
    )
    sys.exit(1)
EOF
    echo "[start] migrations de la base…"
    alembic upgrade head
    echo "[start] migrations à jour — API sur le port ${PORT:-8000}"
    # 0.0.0.0, pas « :: » : asyncio ouvre « :: » en IPv6 seul
    # (IPV6_V6ONLY), et le healthcheck de Railway arrive en IPv4.
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
      --proxy-headers --forwarded-allow-ips='*'
    ;;
  worker)
    exec celery -A app.celery_app:celery_app worker --loglevel=info \
      --concurrency="${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    exec celery -A app.celery_app:celery_app beat --loglevel=info
    ;;
  *)
    echo "ROLE inconnu : $ROLE (attendu : web, worker ou beat)" >&2
    exit 1
    ;;
esac
