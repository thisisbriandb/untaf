# Roadmap — Untaf / Alice

État des lieux et plan de travail pour finir le projet. Généré à partir d'un
scan complet du code (routes API, écrans frontend, agents, tâches planifiées)
le 2026-08-10. Chaque étape est pensée pour être testée indépendamment,
une par une.

Légende : ✅ solide, ne pas toucher · ⚠️ simulé/mocké (affiché comme réel mais
ne l'est pas) · 🪦 code mort · 🚧 manquant/à finir · 🐛 bug mineur repéré.

---

## 0. Schéma d'ensemble

| Domaine                                     | État | Détail                                                            |
| ------------------------------------------- | ---- | ----------------------------------------------------------------- | ------------------------------- |
| Onboarding (conversation, dépôt CV)         | ✅   | Fonctionne de bout en bout                                        |
| Extraction CV (PDF/LinkedIn)                | ✅   | Gemini + repli regex si pas de clé API                            |
| Matching offre ↔ candidat                   | ✅   | Algorithme déterministe, explicable                               |
| Collecte France Travail                     | ✅   | OAuth2, ingestion quotidienne planifiée                           | http://localhost:3000/dashboard |
| Collecte ATS (Greenhouse/Lever/Ashby)       | ✅   | Scrapers + fallback Playwright                                    |
| Découverte de nouveaux boards ATS           | ✅   | Via Common Crawl, hebdomadaire                                    |
| Missions bornées + journal                  | ✅   | Cycle Scan→Qualify→Match→Prepare fonctionnel                      |
| Rédaction CV / lettres                      | ✅   | Gemini + repli gabarit                                            |
| Candidature — canal email                   | ✅   | Chaque candidat configure sa propre adresse Gmail (2026-08-11) — simulée tant qu'il ne l'a pas fait |
| Candidature — envoi auto en mission         | 🚧   | Jamais branché, même en autonomie "full" (reste à faire)          |
| Candidature — canaux Greenhouse/Lever/Ashby | ✅   | Connecteurs écrits (2026-08-10) — simulation uniquement, jamais d'envoi réel |
| Agent navigateur (formulaires employeur)    | ✅   | Supprimé (2026-08-10) — code mort, jamais appelé                  |
| Onglet "Messages" (réponses recruteurs)     | ✅   | Vrai backend (2026-08-10) — modèle + API + frontend, vide tant qu'aucune source réelle n'écrit |
| Cloche de notifications                     | ✅   | Branchée (2026-08-10) sur le vrai journal de mission + les vrais messages |
| Navigation par onglets du dashboard         | ✅   | `DashboardSidebar.tsx` monté (2026-08-10)                          |
| Ancien wizard d'onboarding multi-étapes     | ✅   | Supprimé (2026-08-10) — 12 fichiers morts confirmés puis retirés  |
| Schéma de base de données                   | ✅   | Bridge supprimé (2026-08-10) — Alembic seul fait foi              |
| Source SIRENE (seeding entreprises)         | 🚧   | Inerte sans `SIRENE_API_TOKEN` (nécessite une inscription externe, pas fait) |
| `download-cv/{template_id}` (fallback GET)  | ✅   | Corrigé (2026-08-10) — tire le vrai profil du candidat en base    |
| Compteurs "nouveau" (companies/offers)      | ✅   | Corrigé (2026-08-10) — distinction insert/update via `xmax`       |
| **Authentification**                        | ✅   | Ajoutée (2026-08-10) — voir section 4, aucune n'existait avant     |

---

## 4. Authentification — ajoutée le 2026-08-10

Contexte : le projet visait un usage perso jusqu'ici. En passant à un objectif
de déploiement public, l'audit a trouvé **zéro authentification** —
`candidate_id` était un UUID dans `localStorage`, lu sans aucune vérification.
N'importe qui connaissant/devinant un `candidate_id` avait accès complet
(lecture ET écriture) au profil, CV, candidatures, messages de n'importe qui.
Comblé avant tout le reste, car plus urgent que n'importe quel connecteur.

**Ce qui a été construit** :
- Mots de passe hachés avec `argon2-cffi` (recommandation OWASP)
- Sessions côté serveur dans Redis (réutilise l'infra Celery existante),
  cookie httpOnly — révocation instantanée à la déconnexion
- `POST /candidates/` sert d'inscription (mot de passe obligatoire, `NOT
  NULL` en base — aucun compte ne peut exister sans, connexion immédiate) ;
  nouvelles routes `/auth/login`, `/auth/logout`, `/auth/me`. (Un
  `/auth/claim` temporaire a existé le temps de migrer les 2 comptes créés
  avant l'authentification — supprimé le 2026-08-11 une fois ces comptes
  effacés : tout le monde repart de zéro, plus de cas particulier.)
- **Vérification d'autorisation ajoutée sur les 38 endpoints qui manipulent
  un `candidate_id`** — chacun vérifie désormais que l'appelant est bien le
  candidat concerné (403 sinon)
- **Bonus trouvés en creusant, corrigés au passage** : `GET /applications/`
  laissait n'importe qui lister les candidatures de n'importe qui via un
  paramètre non vérifié ; `GET/PATCH /applications/{id}` n'avaient même pas
  de `candidate_id` à vérifier (ownership ajoutée par jointure) ; l'onboarding
  avait un vrai risque de prise de compte — sur un email déjà enregistré, le
  code faisait un `PUT` sur le profil existant **sans mot de passe** —
  remplacé par une redirection vers `/login`
- Nouvelle page `/login`, contexte d'authentification React
  (`app/auth-context.tsx`), wrapper `fetch` (`lib/api.ts`) qui force l'envoi
  du cookie de session sur les ~37 appels API existants

**Testé** : inscription, connexion (bon/mauvais mot de passe), déconnexion
(session Redis vraiment supprimée, pas juste le cookie local), accès refusé
sur le profil de quelqu'un d'autre (testé sur `candidates`, `mission`,
`messages`, `dispatches`, `apply`, `applications`, `chat`), flux de
réclamation des comptes existants (fonctionne une fois, s'auto-désactive).

**Volontairement pas fait** : `proxy.ts` (protection de route côté Next.js —
la vraie sécurité est déjà côté backend, ce serait juste un bonus visuel
contre le flash de chargement).

*Mise à jour 2026-08-11* : les 2 comptes créés avant l'authentification ont
été supprimés (à la demande explicite) — plus aucun cas particulier, tout le
monde crée son compte via l'onboarding normal. `/auth/claim` est retiré.
`password_hash` est maintenant `NOT NULL` en base : impossible qu'un compte
existe sans mot de passe.

---

## 5. SMTP par candidat — ajouté le 2026-08-11

Avant : une seule config SMTP globale (`.env`) pour toute l'app — toutes les
candidatures de tous les candidats seraient parties depuis la même boîte
mail (probablement celle de qui a déployé l'app). Demandé explicitement :
chaque candidat connecté utilise sa **propre** adresse.

**Ce qui a été construit** :
- `Candidate.smtp_email` + `Candidate.smtp_app_password_encrypted` — le mot
  de passe d'application est **chiffré** (Fernet, `app/auth/crypto.py`), pas
  haché comme le mot de passe de connexion : il doit être déchiffrable pour
  se connecter réellement au serveur SMTP
- Clé de chiffrement dans `.env` (`CREDENTIALS_ENCRYPTION_KEY`) — jamais en
  base, jamais commitée ; la perdre rend tous les mots de passe stockés
  illisibles définitivement
- Routes `GET/PUT/DELETE /candidates/{id}/smtp`, protégées comme les autres
  (`require_owner`) — jamais le mot de passe renvoyé au client, même chiffré
- `email_sender.py` utilise désormais les identifiants du candidat, plus
  aucune configuration globale
- Portée volontairement limitée à Gmail (`smtp.gmail.com:587`, TLS) pour
  cette version — pas de champs serveur/port pour rester simple pour un
  utilisateur non technique. Interface dans Paramètres → Envoi d'emails.

**Testé** : cycle complet sauvegarde → lecture → suppression via curl ;
chiffrement vérifié en base (ce n'est pas le mot de passe en clair) ; le
mot de passe déchiffré correspond exactement à l'original ; accès refusé
(403) sur la config SMTP de quelqu'un d'autre.

---

## 1. Ce qui est déjà nickel — ne pas retoucher

- **Onboarding conversationnel** — [AliceExperience.tsx](frontend/app/onboarding/components/AliceExperience.tsx)
- **Pipeline d'extraction CV** — [resume_parser.py](backend/job-discovery/app/agents/discovery/resume_parser.py) (Gemini + repli heuristique)
- **Moteur de matching** — [matching.py](backend/job-discovery/app/agents/discovery/matching.py) : filtres durs + score pondéré, 100% explicable
- **Collecte multi-source** — France Travail ([france_travail.py](backend/job-discovery/app/agents/discovery/france_travail.py)) + scrapers ATS ([scrapers/](backend/job-discovery/app/agents/discovery/scrapers/))
- **Cycle de mission** — [mission_runner.py](backend/job-discovery/app/agents/mission_runner.py) : Scan → Qualify → Match → Prepare, avec heartbeat et nettoyage des runs orphelins
- **Rédaction CV/lettres** — [cv_writer.py](backend/job-discovery/app/agents/discovery/cv_writer.py), [cover_letter.py](backend/job-discovery/app/agents/discovery/cover_letter.py)
- **Autorisation avant envoi** — [dispatcher.py](backend/job-discovery/app/agents/application/dispatcher.py) : quota, doublons, entreprises bloquées, canaux autorisés

Ne pas perdre de temps ici, ça marche déjà.

---

## 2. Plan de travail — étape par étape

### Étape 1 — Hygiène technique (fondations avant d'ajouter des features)

- [x] **Migrer le pont `ALTER TABLE` vers Alembic propre.** ~~Le code le
      signale lui-même comme dette temporaire~~ — supprimé de
      [main.py](backend/job-discovery/app/main.py). `alembic check` a confirmé
      zéro dérive entre la base live et les migrations existantes : les deux
      migrations couvraient déjà tout, le bridge était rendu inutile. En
      testant "base neuve" j'ai trouvé un vrai bug caché dessous : la
      migration heartbeat ([c3eae8fff71a](backend/job-discovery/alembic/versions/c3eae8fff71a_battement_de_coeur_des_runs_de_mission.py))
      recréait un index déjà posé par la migration initiale
      (`ix_mission_events_run_id`), ce qui faisait planter `alembic upgrade
      head` sur toute base vide. Corrigé.
      _Test (fait) : DB de test créée, `alembic upgrade head` depuis zéro,
      schéma comparé colonne par colonne à la base réelle — 9 tables,
      colonnes identiques._
- [x] **Supprimer le code mort de l'onboarding.** 18 fichiers passés en
      revue un par un (grep des imports croisés) : 6 étaient en fait utilisés
      par `CanvasCvEditor.tsx` dans le dashboard (`CandidateCvPreview.tsx` et
      les 5 formulaires de `editor/`) — gardés. Les 12 réellement morts
      (`WelcomeChoiceStep.tsx`, `Step1ImportDiagnostic.tsx`,
      `Step2ContentEditor.tsx`, `Step2CvEditor.tsx`, `Step3DesignStudio.tsx`,
      `Step4MatchingPreferences.tsx`, `MatchingScreen.tsx`,
      `TemplateSwipeCard.tsx`, `FictionalCVCard.tsx`, `NavigationBar.tsx`,
      `StepperHeader.tsx`, `editor/EditorSubStepper.tsx`) — supprimés.
      _Test (fait) : `npx tsc --noEmit` passe sans erreur._
- [x] **Décider du sort de `CandidateAgent`** — supprimé (confirmé mort par
      grep, aucun appelant). La mention dans le docstring de
      [mission_runner.py](backend/job-discovery/app/agents/mission_runner.py#L1)
      a été corrigée pour ne plus référencer une classe qui n'existe plus.
- [x] **Corriger les compteurs "nouveau"** — [discovery/tasks.py](backend/job-discovery/app/agents/discovery/tasks.py)
      utilisait `rowcount > 0` sur un `ON CONFLICT DO UPDATE`, toujours vrai
      qu'il s'agisse d'un insert ou d'une mise à jour. Remplacé par
      `RETURNING (xmax = 0)`, qui distingue vraiment insert et update côté
      Postgres. (Les 3 autres occurrences de `rowcount > 0` dans
      `seeding/tasks.py` utilisent `ON CONFLICT DO NOTHING` — déjà correctes,
      pas touchées.)
      _Test (fait) : script d'insertion en double sur une entreprise de
      test — 1er appel `new_count=1`, 2e appel `new_count=0` (avant le fix,
      c'était 1 les deux fois). Données de test nettoyées après coup._

### Étape 2 — Arrêter d'afficher du faux comme du vrai

Ces éléments donnent l'illusion que le produit fait plus qu'il ne fait —
priorité avant toute démo ou tout utilisateur externe.

- [x] **Onglet "Messages".** Backend réel construit : modèle
      [`RecruiterMessage`](backend/job-discovery/app/models/message.py),
      migration Alembic, API [`messages.py`](backend/job-discovery/app/api/messages.py)
      (`GET/POST /candidates/{id}/messages`, `/summary`, `/{id}/read`,
      `/read`), [MessagesView.tsx](frontend/app/dashboard/components/MessagesView.tsx)
      branché dessus — plus aucune donnée en dur. **Limite technique
      assumée** : sans SMTP réel ni boîte mail à interroger, il n'y a pas
      de source automatique de vraies réponses aujourd'hui — la table est
      réelle mais vide tant qu'un IMAP/webhook n'y écrit pas (`POST /messages`
      existe comme point d'entrée pour ce futur connecteur — voir Étape 5).
      _Test (fait) : cycle complet créer → lister → marquer lu via curl,
      vérifié sur un vrai candidat. Onglet vide sans donnée inventée._
- [x] **Cloche de notifications.** [DashboardHeader.tsx](frontend/app/dashboard/components/DashboardHeader.tsx)
      combine désormais les événements non lus du vrai journal de mission
      (`GET /mission/journal`) et les vrais messages non lus
      (`GET /messages?unread_only=true`), avec un "tout marquer comme lu"
      qui appelle les deux endpoints réels. Plus de `unreadCount` ni de
      contenu Doctolib codés en dur.
      _Test (fait) : testé sur un candidat avec un vrai historique de
      mission (1140 offres scannées, événements non lus authentiques)._
- [x] **Navigation du dashboard.** `DashboardSidebar.tsx` monté dans
      [page.tsx](frontend/app/dashboard/page.tsx) (`pl-14` ajouté au
      conteneur principal pour compenser la sidebar fixe). Les 5 onglets
      sont maintenant atteignables en 1 clic.
      _Test (fait) : `npx tsc --noEmit` propre, `/dashboard` compile et
      sert 200 après montage._

### Étape 3 — Compléter le cœur produit : l'envoi de candidatures

C'est le chantier le plus important : aujourd'hui Alice **prépare** des
candidatures mais ne les **envoie** jamais elle-même en mode autonome.

- [ ] **Brancher l'envoi automatique dans les missions.**
      [mission_runner.py:224-263](backend/job-discovery/app/agents/mission_runner.py#L224)
      (`_step_apply`) doit appeler le dispatcher au lieu de se contenter de
      logger _"L'envoi automatique n'est pas encore raccordé"_.
      _Test : lancer une mission en autonomie `full` sur un candidat avec
      SMTP configuré, vérifier qu'une candidature part réellement (pas
      simulée) sans intervention manuelle._
- [ ] **Configurer un vrai SMTP** pour sortir du mode simulé
      ([config.py:66-68](backend/job-discovery/app/config.py#L66), `can_send_email`).
      _Test : `POST /apply/{job_id}/stream` renvoie `real: true` au lieu de
      `simulated: true`._
- [x] **Implémenter les connecteurs Greenhouse/Lever/Ashby** —
      [ats_connectors.py](backend/job-discovery/app/agents/application/ats_connectors.py),
      branché dans [dispatcher.py](backend/job-discovery/app/agents/application/dispatcher.py)
      (`_send_via_ats`) et [feasibility.py](backend/job-discovery/app/agents/application/feasibility.py)
      (déplacés de `AUTOMATABLE_SOON` vers `IMPLEMENTED`). **Toujours en
      simulation** — `submit_ats_application` ne fait jamais de vraie
      requête POST, exactement comme l'email sans SMTP configuré.
      Niveau de certitude différent par plateforme, vérifié en lecture
      réelle (lecture seule, sans risque) :
      - **Greenhouse** publie le schéma exact du formulaire
        (`?questions=true`) : le connecteur sait distinguer une offre
        totalement automatisable d'une offre bloquée par une question
        requise non mappable, avec le motif exact. Vérifié en conditions
        réelles sur une offre Stripe (6 champs socle mappés, 10 questions
        requises non automatisables détectées correctement).
      - **Lever et Ashby** ne publient aucun schéma de formulaire via leur
        API publique (vérifié : leurs endpoints de listing n'exposent que
        les métadonnées de l'offre) — le connecteur le signale honnêtement
        plutôt que de prétendre une automatisation non vérifiable.
      _Test (fait) : `build_greenhouse_plan` testé contre une vraie offre
      Greenhouse (Stripe) et contre un schéma synthétique "propre" pour
      valider le chemin `automatable=True`. `submit_ats_application`
      vérifié pour ne jamais renvoyer `real: True`._
      **Reste à faire avant un vrai envoi** : vérifier manuellement
      `submit_url`/le format exact de la requête contre un board réel
      avant d'activer un POST effectif — non fait ici par choix (aucun
      envoi réel autorisé aujourd'hui).
- [x] **Agent navigateur** — supprimé, voir Étape 1. Le canal "formulaire
      employeur complexe" reste donc à construire de zéro s'il redevient
      prioritaire, plutôt que de reprendre du code mort.

### Étape 4 — Compléter les sources de données

- [ ] **Obtenir/configurer `SIRENE_API_TOKEN`** pour activer cette source de
      seeding d'entreprises ([sirene.py:42-44](backend/job-discovery/app/agents/seeding/sirene.py#L42),
      aujourd'hui silencieusement inerte).
      _Test : `POST /companies/seed` fait remonter des entreprises via
      SIRENE (vérifiable dans les logs)._
- [x] **Corriger le fallback `GET /download-cv/{template_id}`**
      ([candidates.py](backend/job-discovery/app/api/candidates.py)) —
      prend désormais `candidate_id` en query param obligatoire, charge le
      vrai `Candidate` en base et construit la requête de rendu depuis son
      `cv_content`/`skills` réels au lieu de `name`/`headline` arbitraires.
      _Test (fait) : sans `candidate_id` → 422 ; candidat inexistant → 404 ;
      vrai candidat → 200 avec un PDF valide généré depuis son vrai profil._

### Étape 5 — Chantiers plus lourds (à planifier séparément)

- [ ] **Suivi des réponses recruteurs** — nécessite un vrai modèle de
      données (aujourd'hui inexistant) et probablement une connexion IMAP
      ou un webhook, pas juste un fix de l'UI. À cadrer avant de commencer.
- [ ] **Migration Supabase** — `SUPABASE_URL`/`SUPABASE_KEY` sont dans `.env`
      mais non utilisées nulle part dans le code (confirmé par grep). Si
      l'objectif reste de bascule vers Supabase (mentionné dans le README),
      c'est un chantier complet de migration du stockage, pas une simple
      variable d'environnement à activer.

---

## 3. Comment utiliser ce fichier

Coche les cases au fur et à mesure. Chaque étape a un test de validation
explicite — ne passe à la suivante que si le test passe. L'ordre proposé
suit les dépendances (hygiène → honnêteté de l'UI → cœur produit → sources
de données → chantiers lourds), mais rien n'empêche de sauter à l'Étape 3
si l'envoi de candidatures est la priorité business.
