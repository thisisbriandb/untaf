# Untaf — Alice

Alice est un agent de recherche d'emploi. On ne lui pose pas des questions : on
lui confie une mission. Elle collecte les offres, les confronte à un mandat,
adapte les documents, et rend compte de ce qu'elle a fait.

---

## Architecture

```
frontend/              Next.js 16 · React 19 · Tailwind 4
  app/onboarding/      Parcours conversationnel d'entrée
  app/dashboard/       Conversation + Canvas latéral
  lib/                 Clients API

backend/job-discovery/ FastAPI · SQLAlchemy 2 async · Celery
  app/agents/
    discovery/         Sources, qualification, matching
    application/       Candidature : faisabilité, prérequis, envoi
    mission_runner.py  Exécution d'une mission bornée
    persona.py         Définition unique d'Alice
  app/api/             Routes REST
  app/models/          Schéma de données

backend/cv-engine/     Compilation Typst → PDF (CV et lettres)
```

**Stockage** : PostgreSQL pour tout ce qui persiste, Redis comme courtier Celery.

---

## Prérequis

- Python 3.12+
- Node.js 20+
- PostgreSQL 14+
- Redis (uniquement pour les tâches planifiées)
- [Typst](https://typst.app) via `cv-engine` pour la génération PDF

---

## Installation

### 1. Base de données

```bash
createdb job_discovery
```

Les tables sont créées au démarrage quand `DEBUG=true`. En production il faut
passer par Alembic — voir *Limites connues*.

### 2. Backend

```bash
cd backend/job-discovery
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env      # puis renseigner les valeurs
uvicorn app.main:app --reload --port 8000
```

API sur `http://localhost:8000`, documentation interactive sur `/docs`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Interface sur `http://localhost:3000`.

### 4. Tâches planifiées (optionnel)

```bash
cd backend/job-discovery
celery -A app.celery_app worker -l info
celery -A app.celery_app beat -l info
```

Le beat déclenche l'ingestion France Travail à 5h30, puis les scrapers ATS.

---

## Variables d'environnement

Toutes dans `backend/job-discovery/.env`.

| Variable | Requis | Rôle |
| --- | --- | --- |
| `DATABASE_URL` | oui | PostgreSQL, pilote `asyncpg` |
| `REDIS_URL` | Celery | Courtier des tâches planifiées |
| `DEBUG` | — | `true` crée les tables au démarrage |
| `GEMINI_API_KEY` | oui | Conversation, qualification, rédaction |
| `GEMINI_MODEL` | — | Défaut `gemini-1.5-flash` |
| `IDENTIFIER_FRANCE_TRAVAIL` | offres | `client_id` (format `PAR_…`) |
| `FRANCE_TRAVAIL_API` | offres | `client_secret` |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | envois | Sans eux, les candidatures sont **simulées** |
| `SIRENE_API_TOKEN` | — | Enrichissement entreprises |

### France Travail

L'application doit être **abonnée à « Offres d'emploi v2 »** sur
[francetravail.io](https://francetravail.io) — l'abonnement est une action
distincte de la création de l'application. Sans lui, l'authentification renvoie
`invalid_client`.

Le scope OAuth doit contenir `application_{client_id}` en plus des scopes
d'API ; c'est géré par le code mais mal documenté côté France Travail.

---

## Comment ça marche

### Collecte

France Travail (API officielle, source principale) et les ATS publics
(Greenhouse, Lever, Ashby). Les requêtes France Travail utilisent les **codes
ROME** déduits du mandat plutôt que des mots-clés : `motsCles` combine les
termes en ET et vide les résultats.

### Qualification

Les offres France Travail sont structurées **sans LLM** — l'API fournit déjà le
contrat, l'expérience, le salaire et les compétences. Les offres ATS passent
par Gemini, faute de métadonnées.

### Matching

Un mandat (`MatchingCriteria`) combine des **filtres durs** — langue, pays,
métier, contrat — et des **dimensions notées** additives. Deux règles
structurantes :

- le score n'est attribué que sur preuve positive : une offre dont on ignore
  tout ne peut pas bien scorer ;
- ce qui n'est pas déterminé ne reçoit qu'un crédit partiel, jamais un
  laissez-passer.

Chaque offre écartée l'est avec un motif lisible, consultable dans le journal.

### Candidature

`feasibility.py` évalue ce qui est réellement automatisable :

| Canal | Complexité | État |
| --- | --- | --- |
| Email | `simple` | **Implémenté** |
| Greenhouse / Lever / Ashby | `medium` | Connecteur à écrire |
| Formulaire employeur | `complex` | Agent navigateur requis |
| Portail France Travail | `impossible` | Compte candidat requis |

Rien ne part sans autorisation du mandat, rien ne part deux fois, et un envoi
simulé n'est **jamais** rapporté comme réel — `SIMULATED` et `SENT` sont deux
états distincts.

---

## État actuel

**Fonctionne** : onboarding, collecte multi-sources, matching explicable,
éditeur de CV avec choix de modèle, rédaction de lettres ancrée sur l'annonce,
signature manuscrite, missions bornées avec journal, candidature par email.

**Simulé** : l'envoi, tant que SMTP n'est pas configuré. L'interface l'indique
explicitement.

**Absent** : connecteurs ATS, agent navigateur, suivi des réponses.

---

## Limites connues

- **Pas de migrations.** Les tables sont créées par `create_all` en mode debug,
  et les colonnes ajoutées après coup par un pont `ALTER TABLE … IF NOT EXISTS`
  dans `main.py`. À remplacer par Alembic avant toute mise en production.
- **Les missions vivent dans le process FastAPI** (`asyncio.create_task`). Un
  redémarrage les interrompt. Elles devraient tourner dans un worker Celery.
- **Le parcours détaillé est dupliqué** entre `localStorage` et
  `Candidate.cv_content`. Le serveur fait foi pour ce qu'Alice rédige.
- **L'historique de conversation transite par le navigateur** à chaque tour. Il
  ne survit pas à un changement d'appareil.

---

## Sécurité

`backend/job-discovery/.env` contient des secrets réels. Vérifier qu'il est
ignoré par Git **avant le premier commit** — voir le `.gitignore` à la racine.

Toute clé qui aurait déjà été commitée doit être considérée comme compromise et
régénérée.
