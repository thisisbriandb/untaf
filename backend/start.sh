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
    echo "[start] migrations de la base…"
    alembic upgrade head
    echo "[start] migrations à jour — API sur le port ${PORT:-8000}"
    # « :: » écoute en IPv6 et en IPv4 : le réseau interne de Railway, d'où
    # part le healthcheck, passe par IPv6.
    exec uvicorn app.main:app --host :: --port "${PORT:-8000}" \
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
