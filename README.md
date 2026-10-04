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
| `RESEND_API_KEY` | e-mails | Candidatures, notifications, connexion, alertes (domaine `MAIL_DOMAIN`) |
| `AUTH_SECRET` | oui | Signature des sessions de connexion |
| `OPS_ALERT_EMAIL` | — | Alertes quand une promesse n'est pas tenue |
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

### La bonne alternance

`LBA_API_KEY` : clé d'un compte développeur sur
[api.apprentissage.beta.gouv.fr](https://api.apprentissage.beta.gouv.fr).

- **Clé production** : la recherche d'offres marche tout de suite, sans
  habilitation.
- **Envoi des candidatures** : exige une habilitation accordée à
  l'organisation, sur demande à
  contact-api@labonnealternance.apprentissage.beta.gouv.fr. Sans elle, l'API
  répond 403 : l'envoi échoue proprement (dossier prêt, alerte
  `OPS_ALERT_EMAIL`) et rien n'est rapporté comme parti.
- **Clé sandbox** : pour tester l'envoi avant l'habilitation. Tous les
  échanges, recherche comprise, passent alors par un environnement de test :
  les offres ne sont pas réelles. À réserver au développement, jamais en
  production.

Lire leurs CGU avant la mise en production (consentement du candidat à
l'envoi en son nom).

---

## Authentification

Connexion sans mot de passe : un lien et un code à 6 chiffres envoyés depuis
`alice@alice-agent.fr` (Resend) par
[`api/auth_routes.py`](backend/job-discovery/app/api/auth_routes.py). L'API
signe elle-même les sessions (`AUTH_SECRET`, `SESSION_DAYS`) ; rien à
configurer côté frontend. Jetons à usage unique valables 15 minutes,
empreintes seules en base, 5 essais de code, 5 demandes par adresse et par
quart d'heure. Le lien ouvert dans un autre onglet fait reprendre l'onglet
d'origine (l'onboarding en cours n'est pas perdu). Un rechargement garde la
session ; sans session, `/` et `/dashboard` mènent à la connexion plutôt qu'à
l'onboarding. Les jetons Supabase Auth restent acceptés si
`SUPABASE_JWT_SECRET` est fourni.

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
  connexion avec la même adresse (la connexion prouve la possession de
  l'adresse).

L'onboarding reste ouvert jusqu'à l'activation : l'analyse du CV et la mise en
forme ne demandent pas de compte. L'adresse est confirmée à la dernière étape,
sans perdre ce qui a été saisi. Sans `AUTH_SECRET`, l'API refuse (503) plutôt
que d'ouvrir — sauf en développement (`DEBUG=true`) ou avec
`AUTH_DISABLED=true`.

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
| Email | `simple` | Implémenté ; adresses extraites des annonces |
| La bonne alternance | `simple` | Transmis par l'API de l'État (`POST /job/v1/apply`) |
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

### Adapter un CV — ce que ça veut dire

Adapter un CV à une offre, c'est réécrire l'accroche et la présentation pour ce
poste, ouvrir le CV sur les **points forts pour ce poste**, reformuler les
réalisations de chaque expérience vers ce que l'annonce demande (reformuler,
regrouper, réordonner — jamais ajouter un outil, un chiffre ou une
responsabilité absents du parcours) et placer en tête les compétences
demandées. **Rien n'est retiré** : expériences, formation et langues restent
toutes. Le CV général du
candidat ne bouge pas ; la version adaptée est rangée sur la candidature.

Le parcours vit côté serveur (`candidates.cv_content`) : l'onboarding l'envoie
à l'activation, l'éditeur le relit sur n'importe quel appareil, et s'il manque
encore une section alors qu'un CV a été déposé, il est relu depuis ce PDF
([`cv_completeness.py`](backend/job-discovery/app/agents/application/cv_completeness.py))
sans écraser ce qui a été saisi. Les sections encore vides sont signalées.

Un PDF déposé ne se réécrit pas : l'adapter passe par un modèle de mise en
page (classique par défaut), et l'interface propose d'en choisir un. Le pack
ne contient **jamais** le CV d'origine à la place du CV adapté : si la mise en
page échoue, le téléchargement le dit et aucun envoi ne part. Les paquets
Typst (cv-engine, fontawesome) sont embarqués dans le dépôt : la mise en page
ne dépend d'aucun téléchargement au moment du rendu.

L'état d'un dossier est unique et partagé (`GET …/apply/{job_id}/state`) : la
fiche d'une offre, le panneau de candidature et la liste le lisent tous, et
une candidature déjà préparée ne propose plus jamais « Préparer ».

### Qui envoie la candidature

Chaque offre porte un mode, affiché partout (`feasibility.apply_mode`) :

| Mode | Quand | Ce qui se passe |
| --- | --- | --- |
| « Alice postule » | adresse e-mail publiée + Resend/SMTP, offre La bonne alternance + clé, ou ATS + envoi navigateur | Alice envoie elle-même, selon le mandat |
| « Prêt en un clic » | ATS ou formulaire sans envoi automatique, e-mail sans SMTP | tout est rempli, le candidat confirme |
| « À finir sur le site » | portail France Travail, canal inconnu | le dossier est prêt, le candidat l'envoie |

Une mission traite d'abord les offres qu'Alice peut réellement envoyer. Quel que soit le mode, « Postuler » se termine toujours sur le
dossier téléchargeable (CV adapté, lettre, annonce) et un bouton « J'ai
postulé » qui fait entrer la candidature dans le suivi (relance comprise).

### Missions

Une mission est **une seule passe, sans durée, et un seul objectif** :
préparer et postuler sont les deux temps du même geste. Elle cherche de
nouvelles offres (France Travail, La bonne alternance), prépare le dossier
complet des 3, 5 ou 10 meilleures — celles qu'Alice peut envoyer en premier —
puis envoie ce qui peut partir. Seule question au lancement : envoyer
directement, ou présenter d'abord chaque envoi. Choisir l'envoi vaut
autorisation pour cette mission (doublons, entreprises bloquées et quota
restent appliqués).
Chaque action est écrite au journal au moment où elle a lieu et diffusée en
direct dans la conversation ; l'utilisateur peut fermer l'onglet, un e-mail
rend compte à la fin. Sans worker Celery joignable, la mission tourne dans le
processus de l'API plutôt que de ne pas tourner.

### Promesses non tenues

Quand Alice ne peut pas tenir une promesse (CV non composé, envoi échoué,
dossier impossible, mission vide ou en erreur, e-mail non délivré),
[`incidents.py`](backend/job-discovery/app/agents/incidents.py) l'écrit au
journal du candidat avec une alternative concrète, et alerte
`OPS_ALERT_EMAIL` (une fois par type, par candidat et par jour).

### Conversations par offre

Une question posée depuis une offre part dans la conversation de cette offre
(une seule par offre) : Alice reçoit l'annonce, le statut et le dossier comme
contexte, et la barre latérale (bouton à gauche de l'en-tête) range ces
conversations sous le nom de l'entreprise, à côté du fil général. Les chiffres
restent communs : ils sont relus en base à chaque tour.

### Pack et envoi pendant une mission

Une mission construit pour chaque offre du haut du panier un **pack** complet
— CV adapté et lettre — par
le même module que le bouton « adapter » du Canvas
([`pack.py`](backend/job-discovery/app/agents/application/pack.py)). Une
mission passe ensuite chaque pack au dispatcher : ce que le mandat
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
- **Le portail France Travail reste hors de portée de l'envoi automatique.**
  Il exige le compte candidat de l'utilisateur, et il n'existe pas d'API
  « postuler ». La seule voie serait une session navigateur autorisée par
  l'utilisateur lui-même (voir `frontend/spec/moteur_candidature.md`, P1).
- **Recruitee n'est pas encore branché.** Son API de site carrière accepte
  les candidatures sans clé employeur, mais le format exact de la pièce jointe
  n'a pas pu être vérifié et les boards (sous-domaines) ne s'énumèrent pas
  comme ceux des autres ATS. Prochaine source à intégrer après La bonne
  alternance.
- **Les ATS (Greenhouse, Lever, Ashby) ne sont collectés que par le beat
  Celery.** Sans services `worker` et `beat` déployés, seules les sources
  interrogées à la demande (France Travail, La bonne alternance) alimentent
  les offres.

---

## Sécurité

`backend/job-discovery/.env` contient des secrets réels. Vérifier qu'il est
ignoré par Git **avant le premier commit** — voir le `.gitignore` à la racine.

Toute clé qui aurait déjà été commitée doit être considérée comme compromise et
régénérée.
