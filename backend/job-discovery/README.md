# Job Discovery — Multi-Agent Pipeline

Système de veille automatisé pour découvrir les offres d'emploi du "marché caché" — 
directement depuis les pages carrières des entreprises (Greenhouse, Lever, Workday, etc.).

## Quick Start

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Architecture

- **Seeding** : WTTJ sitemap + FT120/Next40 + SIRENE API
- **ATS Resolver** : Détection automatique du canal de recrutement
- **Scrapers** : Greenhouse API, Lever API (daily via Celery Beat)
- **API** : FastAPI + PostgreSQL + Redis
