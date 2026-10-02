#!/bin/sh
# Point d'entrée de l'image. Une seule image, trois services Railway :
# chacun choisit son rôle par la variable ROLE.
#
#   ROLE=web     API FastAPI (défaut) — applique les migrations au démarrage
#   ROLE=worker  worker Celery
#   ROLE=beat    planificateur Celery (une seule instance, jamais plus)
set -e

case "${ROLE:-web}" in
  web)
    alembic upgrade head
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
