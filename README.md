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

Le beat déclenche l'ingestion France Travail à 5h30, le reclassement des
contacts de candidature à 5h50, les scrapers ATS à partir de 6h, le
rafraîchissement du registre des boards le lundi à 4h, le balayage des missions
orphelines toutes les 5 minutes, la détection des relances dues à 8h40 et les
rapports d'activité (quotidien à 18h30, hebdomadaire le lundi à 8h50).

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
| `SUPABASE_URL` / `SUPABASE_JWT_SECRET` | oui | Vérification des jetons de session (JWKS ou secret HS256) |
| `AUTH_DISABLED` | — | `true` lève toutes les gardes — **développement local uniquement** |
| `ADMIN_EMAILS` | — | Comptes autorisés à déclencher scraping et seeding |
| `REDIS_URL` | Celery | Courtier des tâches planifiées |
| `DEBUG` | — | `true` crée les tables au démarrage |
| `GEMINI_API_KEY` | oui | Conversation, qualification, rédaction |
| `GEMINI_MODEL` | — | Défaut `gemini-1.5-flash` |
| `IDENTIFIER_FRANCE_TRAVAIL` | offres | `client_id` (format `PAR_…`) |
| `FRANCE_TRAVAIL_API` | offres | `client_secret` |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | envois | Sans eux, les candidatures sont **simulées** |
| `RESEND_API_KEY` / `NOTIFY_FROM_EMAIL` | notifications | E-mails d'Alice au candidat ; à défaut, le SMTP sert aussi |
| `FRONTEND_URL` | notifications | Racine des liens dans les e-mails (`/dashboard?tab=…`) |
| `FOLLOWUP_AFTER_DAYS` | — | Jours sans réponse avant de proposer une relance (défaut 7) |
| `SIRENE_API_TOKEN` | — | Enrichissement entreprises |

### France Travail

L'application doit être **abonnée à « Offres d'emploi v2 »** sur
[francetravail.io](https://francetravail.io) — l'abonnement est une action
distincte de la création de l'application. Sans lui, l'authentification renvoie
`invalid_client`.

Le scope OAuth doit contenir `application_{client_id}` en plus des scopes
d'API ; c'est géré par le code mais mal documenté côté France Travail.

---

## Authentification

Connexion sans mot de passe par Supabase Auth : un lien et un code reçus par
e-mail. Côté frontend, `NEXT_PUBLIC_SUPABASE_URL` et
`NEXT_PUBLIC_SUPABASE_ANON_KEY` (voir `frontend/.env.example`) ; ajouter
`<FRONTEND_URL>/auth/confirmed` aux *Redirect URLs* du projet. Pour que le
code à 6 chiffres apparaisse dans l'e-mail, ajouter `{{ .Token }}` au modèle
*Magic Link* (Authentication → Email Templates) ; sans lui, le lien suffit.

Chaque requête porte le jeton de session, vérifié par
[`app/auth.py`](backend/job-discovery/app/auth.py). Un profil n'est accessible
qu'au compte auquel il est rattaché (`candidates.auth_user_id`) :

- toute route dont le chemin contient `{candidate_id}` est gardée au niveau de
  l'application — une route ajoutée plus tard l'est d'office ;
- les routes sans ce paramètre (`/api/chat`, `/api/applications/…`, liste des
  candidats) vérifient l'appartenance explicitement ;
- les déclencheurs coûteux (seeding, résolution ATS, matching global) sont
  réservés à `ADMIN_EMAILS` ;
- les offres collées par un candidat ne sont lisibles que par lui ;
- un profil créé avant l'authentification est rattaché à la première
  connexion avec la même adresse. Le projet Supabase doit donc exiger la
  confirmation de l'e-mail (réglage par défaut).

L'onboarding reste ouvert jusqu'à l'activation : l'analyse du CV et la mise en
forme ne demandent pas de compte. L'adresse est confirmée à la dernière étape,
sans perdre ce qui a été saisi. Sans configuration, l'API refuse (503) plutôt
que d'ouvrir ; `AUTH_DISABLED=true` sert au développement local.

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
| Greenhouse / Lever / Ashby | `medium` | Formulaire rempli dans un navigateur |
| Formulaire employeur | `complex` | Socle commun rempli, le reste signalé |
| Portail France Travail | `impossible` | Compte candidat requis |

Le remplissage est **guidé par le schéma**, pas par des sélecteurs devinés :
`GET /jobs/{id}?questions=true` donne le nom, le type et le caractère
obligatoire de chaque champ. Ces noms apparaissent en `id` dans la page rendue
— les boards React ne mettent aucun attribut `name` — et restent stables là où
une classe CSS change à chaque refonte.

Chaque champ est traité indépendamment : ce qui résiste est consigné dans
`unhandled_fields` et remonté à l'utilisateur nommément (« il te manque :
téléphone, 2 questions propres à l'employeur ») plutôt que de faire échouer
l'ensemble. Rien n'est rapporté rempli sans que la page l'ait confirmé.

**Deux verrous indépendants** commandent la soumission : le mandat autorise la
candidature, et `BROWSER_SUBMIT_ENABLED` autorise le clic final. Tant que le
second est faux, le formulaire est rempli puis abandonné, et l'envoi est
enregistré en `SIMULATED`.

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

### Pack et envoi pendant une mission

Une mission « préparer » ou « postuler » construit pour chaque offre du haut du
panier un **pack** complet — CV adapté (accroche et synthèse) et lettre — par
le même module que le bouton « adapter » du Canvas
([`pack.py`](backend/job-discovery/app/agents/application/pack.py)). Une
mission « postuler » passe ensuite chaque pack au dispatcher : ce que le mandat
autorise part, le reste rejoint la **file de validation** (onglet
Candidatures, « Tout valider » en un geste). Si l'utilisateur a demandé à
valider chaque envoi pour cette mission, c'est la règle la plus stricte qui
l'emporte. Une candidature n'est jamais reproposée d'un cycle à l'autre.

### Contacts de candidature

Les adresses sont cherchées partout où elles se cachent — champ `courriel`,
consignes, coordonnées, description — par
[`contact_extract.py`](backend/job-discovery/app/agents/discovery/contact_extract.py),
qui écarte les boîtes de plateforme (`francetravail.fr`…) et les expéditeurs
automatiques, et préfère l'adresse entourée de mots de candidature. Le stock
existant est repassé chaque matin (`reclassify_apply_contacts`).

### Après la candidature

Chaque changement de statut est daté dans une frise. Sans réponse au bout de
`FOLLOWUP_AFTER_DAYS` jours, Alice rédige une relance (courte, propre à
l'offre) et la propose : le candidat l'envoie depuis sa messagerie en un clic.
Elle ne l'envoie pas elle-même — un second contact engage davantage que le
premier. Entretien, offre ou refus rejoignent le journal.

### Notifications

Alice écrit au candidat
([`notifications/`](backend/job-discovery/app/agents/notifications)) : fin de
mission (compte rendu et ce qui attend), candidature réellement envoyée,
relances dues, rapport quotidien ou hebdomadaire. Chaque type se coupe dans
Paramètres. La table `notifications` garde l'historique et sert de verrou
anti-doublon (`dedupe_key` unique) ; sans service d'envoi configuré, la
notification est enregistrée en `simulated`, jamais rapportée comme partie.

---

## État actuel

**Fonctionne** : onboarding, collecte multi-sources, matching explicable,
éditeur de CV avec choix de modèle, rédaction de lettres ancrée sur l'annonce,
signature manuscrite, missions bornées avec journal, packs adaptés par offre,
envoi pendant les missions et file de validation, candidature par email,
relances, notifications par e-mail et rapports d'activité.

**Simulé** : l'envoi, tant que SMTP n'est pas configuré ; les notifications,
tant que ni Resend ni SMTP ne le sont. L'interface l'indique explicitement.

**Absent** : lecture de la boîte de réception (les réponses des recruteurs sont
consignées à la main depuis Candidatures), connexion France Travail.

---

## Limites connues

- **Le canal e-mail dépend de ce que publient les annonces.** Les adresses
  sont désormais extraites des consignes et des descriptions, mais une offre
  France Travail sans adresse ni lien employeur reste réservée au portail.
- **Le pont `ALTER TABLE` de `main.py` fait doublon avec Alembic.** Il reste en
  place le temps de la bascule vers Supabase ; une fois la base migrée, c'est
  Alembic seul qui doit faire foi et le pont doit disparaître.
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
