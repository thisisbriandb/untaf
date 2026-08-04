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

Le schéma est géré par Alembic :

```bash
cd backend/job-discovery
alembic upgrade head
```

La même commande installe le schéma sur Supabase : il suffit de pointer
`DATABASE_URL` sur la chaîne « Connection pooling » du projet. `alembic/env.py`
ignore les schémas internes de la plateforme (`auth`, `storage`, `realtime`),
sans quoi un `--autogenerate` proposerait de les supprimer.

Aucune clé d'API Supabase ne permet de migrer un schéma — il faut le mot de
passe de la base, distinct, disponible dans *Settings → Database*.

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

### 4. Services de fond — **pas optionnel**

```bash
docker compose up -d      # Redis + worker + beat
```

Ce n'est pas un confort : les missions s'exécutent dans le worker, pas dans le
process web. Sans lui, `POST /runs` répond **503** et le dit — plutôt que
d'accepter une mission que personne n'exécutera.

Le beat déclenche l'ingestion France Travail à 5h30, les scrapers ATS à partir
de 6h, le rafraîchissement du registre des boards le lundi à 4h, et le balayage
des missions orphelines toutes les 5 minutes.

Pour lancer les services à la main plutôt qu'en conteneur :

```bash
cd backend/job-discovery
celery -A app.celery_app worker -l info
celery -A app.celery_app beat -l info
```

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
(Greenhouse, Lever, Ashby, Workable). Les requêtes France Travail utilisent les
**codes ROME** déduits du mandat plutôt que des mots-clés : `motsCles` combine
les termes en ET et vide les résultats.

Côté ATS, la difficulté n'est pas de lire un board mais de savoir lesquels
existent : un slug n'est presque jamais le nom de marque, et aucun de ces
éditeurs ne publie l'annuaire de ses clients.
[`board_registry.py`](backend/job-discovery/app/agents/discovery/board_registry.py)
le résout par l'autre bout — l'index public Common Crawl recense les URL déjà
crawlées, donc une requête par domaine (`jobs.ashbyhq.com/*`) rend les slugs
directement. Chacun est ensuite validé contre l'API publique de l'ATS, qui fait
foi, et **seuls les boards publiant en France sont enregistrés** : sur un
échantillon aléatoire, 71 à 84 % des boards indexés sont encore vivants mais 5
à 9 % seulement recrutent ici.

Les collections les plus récentes de l'index saturent régulièrement (502/504) ;
le module retombe sur les crawls précédents, ce qui est sans conséquence : un
slug d'entreprise est un identifiant durable.

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
| Email | `simple` | Implémenté, mais **sans stock** (voir *Limites connues*) |
| Greenhouse / Lever / Ashby | `medium` | Connecteur à écrire |
| Formulaire employeur | `complex` | Agent navigateur requis |
| Portail France Travail | `impossible` | Compte candidat requis |

Sur les trois ATS, l'endpoint de candidature de l'API est authentifié par une
clé appartenant à l'employeur : il est réservé à ses intégrations, pas au
candidat. En revanche `GET /jobs/{id}?questions=true` expose **le schéma exact
du formulaire** sans authentification — noms de champs, types, obligatoires,
options. Les noms du socle (`first_name`, `last_name`, `email`, `phone`,
`resume`, `cover_letter`) sont identiques sur tous les boards testés : c'est un
contrat stable, contrairement à des sélecteurs CSS.

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

- **Le canal e-mail ne couvre rien.** Les offres classées `EMAIL` viennent de
  France Travail, dont le champ `courriel` contient une phrase (« Pour
  postuler, utiliser le lien suivant : … ») et non une adresse. Sur le stock
  actuel, **zéro** offre a une adresse exploitable : le seul canal implémenté
  s'applique à un ensemble vide. À reclasser en `EXTERNAL_LINK` à l'ingestion.
- **Le pont `ALTER TABLE` de `main.py` fait doublon avec Alembic.** Il reste en
  place le temps de la bascule vers Supabase ; une fois la base migrée, c'est
  Alembic seul qui doit faire foi et le pont doit disparaître.
- **Rien n'informe l'utilisateur** quand une mission se termine pendant son
  absence. L'état est exact en base, mais il faut revenir le consulter : aucun
  e-mail ni notification n'est envoyé. C'est le principal écart avec la
  promesse « confie-moi une mission et va faire autre chose ».
- **Les fichiers sont stockés dans Postgres** (`resume_file`, `resume_blob` en
  `bytea`, signature en base64). Chaque `pg_dump` les embarque, ce qui alourdit
  les sauvegardes et gonfle une base facturée à la taille. Leur place est
  Supabase Storage, avec seulement le chemin en base.
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
