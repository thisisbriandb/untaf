# Image unique pour l'API, le worker et le beat (voir start.sh).
#
# Contexte de build : backend/. job-discovery charge cv-engine par un chemin
# relatif (../cv-engine) : les deux dossiers doivent rester voisins dans
# l'image, sinon la génération de CV et de lettres se désactive en silence.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# ── cv-engine (Typst + polices) ─────────────────────────────
COPY cv-engine /srv/cv-engine
RUN pip install -e "/srv/cv-engine[fonts]"

# ── job-discovery : dépendances d'abord, pour le cache ──────
WORKDIR /srv/job-discovery
COPY job-discovery/pyproject.toml job-discovery/README.md ./
RUN mkdir app && touch app/__init__.py \
    && pip install -e ".[browser]"

# Le worker exécute le repli navigateur du scraper. Sans le binaire Chromium
# et ses dépendances système, ce repli échoue par ImportError au moment où on
# en a besoin — c'est-à-dire quand une API d'ATS ne répond plus.
RUN playwright install --with-deps chromium

COPY job-discovery/ ./
COPY start.sh /usr/local/bin/start.sh
# Un start.sh extrait sous Windows peut porter des CRLF : sh les refuse.
RUN sed -i 's/\r$//' /usr/local/bin/start.sh && chmod +x /usr/local/bin/start.sh

CMD ["start.sh"]
