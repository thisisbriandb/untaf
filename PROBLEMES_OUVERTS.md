# Problèmes ouverts

Ce qui est recensé et **pas encore résolu**, pour ne rien oublier. À tenir à
jour : on raye (ou on retire) une ligne quand elle est corrigée et poussée, avec
le commit en référence.

Dernière mise à jour : 8 octobre 2026.

Gravité : 🔴 bloquant · 🟠 important · 🟡 mineur

---

## 1. La promesse « Alice postule pour toi »

Le cœur du problème produit. État des lieux honnête :

| Canal d'envoi automatique | État réel |
|---|---|
| E-mail au recruteur | 🔴 **Aucune adresse e-mail sur les ~5 000 offres en base.** L'envoi par e-mail ne concerne aujourd'hui presque aucune offre : la projection « Alice envoie par e-mail » était fausse. |
| La bonne alternance (API) | 🔴 Habilitation demandée, **aucune réponse** de leur part. |
| Recruitee (API publique) | 🟠 Codé mais **jamais testé en conditions réelles**. À valider avec une vraie candidature (la tienne, sur une offre Recruitee réelle). |
| Greenhouse, Lever (formulaires) | 🔴 **Protégés par captcha** (reCAPTCHA chez Greenhouse, hCaptcha + Cloudflare chez Lever) : la sonde l'a montré le 8 octobre. Rejouer depuis un serveur est impossible sans contourner le captcha (ligne rouge). |
| Formulaires propres à l'employeur | 🟠 Non envoyés automatiquement depuis le commit a1b72a5 (dossier à finir sur le site). |

Conséquence : **aujourd'hui, Alice n'envoie presque rien seule.** Les pistes,
dans l'ordre :

- 🔴 **Mesurer** : lancer `tools/agent-bench/probe.mjs` sur 20 à 50 liens variés
  (sites d'entreprises, sites français, Welcome to the Jungle, Workday, Indeed,
  France Travail) pour savoir quelle part est rejouable, navigateur, extension.
- 🟠 **Candidatures spontanées — v1 en place**, à valider en production :
  l'annuaire (recherche-entreprises.api.gouv.fr) et la recherche du site par
  Gemini n'ont pu être testés qu'avec des réponses simulées. À faire : régler
  `PUBLIC_API_URL` et un sous-domaine d'envoi dédié (`SPONTANEOUS_FROM_EMAIL`),
  mesurer la part d'entreprises qui publient une adresse, surveiller le coût
  des recherches Gemini, ajouter La Bonne Boîte comme source si son API donne
  des signaux d'embauche utiles.
- 🟠 **Trouver des adresses de recrutement** pour les offres existantes : page
  carrière / contact / mentions légales de l'employeur (jamais d'adresse
  devinée type `rh@`).
- 🟠 **Relancer La bonne alternance** (contact-api@labonnealternance.apprentissage.beta.gouv.fr)
  et demander en attendant une **clé sandbox** pour tester.
- 🟠 **Extension, chantier principal** pour Greenhouse / Lever / Workday / WTTJ :
  intégration dans Alice (« Postuler avec l'extension » depuis le dossier),
  envoi détecté automatiquement, mémoire partagée des formulaires, lecture de
  la structure comme la sonde (listes maison, boutons radio), réponses aux
  questions par Muse **en mode texte** (pas de captures d'écran), publication
  sur le Chrome Web Store.
- 🟡 **Muse « computer use »** : testé. Bon sur un petit formulaire (7 champs,
  88 s), mais perdu sur Greenhouse (26 étapes, 12 min, champs retapés) et
  accents perdus. À garder pour les questions en mode texte, pas pour piloter
  la page.
- 🟡 **Adzuna / Jooble** : plus d'offres, mais sans nouveau canal d'envoi (les
  offres finiront par l'extension). Déduplication à prévoir.
- 🟡 **Alice en serveur MCP** : que l'agent du candidat (Claude, ChatGPT, Muse…)
  puisse récupérer les dossiers prêts et signaler l'envoi.
- 🟡 **Envoi depuis la boîte Gmail / Outlook du candidat** (idée de l'article
  JobPilot) : `gmail.send` demande une validation Google.

---

## 2. Audit — série 2 : ce qui fait croire que ça marche

Inscription et profil.

- 🟠 **Les villes ne filtrent pas** : recherche France Travail nationale (aucun
  département transmis), villes = 12 points sur 100, au-delà de 3 villes
  ignorées chez La bonne alternance. `france_travail_task.py` l. 229-262,
  `labonnealternance_task.py` l. 97.
- 🟠 **Mandat non modifiable après l'inscription** : un seul type de contrat,
  pas de salaire, « Mon mandat » en lecture seule. `MissionView.tsx`.
- 🟠 **« Rythme » est un filtre caché** : « Sur site » décoché par défaut.
  `CriteriaStep.tsx` l. 79, `matching.py` l. 207.
- 🟠 **Interrupteur « Candidatures à valider » sans effet** : aucune
  notification n'est envoyée. `ParametresView.tsx` l. 26,
  `notifications/__init__.py`.
- 🟠 **RGPD** : ni suppression de compte, ni export ; le CV complet reste dans le
  navigateur après déconnexion (`cv_profile:*`). `ParametresView.tsx`,
  `session.ts`.
- 🟠 **Mobile : le lien de connexion fait perdre l'inscription** (le code est
  refusé une fois le lien ouvert ailleurs, l'inscription ne vit qu'en mémoire).
  `auth_routes.py` l. 156-174, `EmailSignIn.tsx`, `AliceExperience.tsx`.
- 🟠 **Le parcours extrait n'est jamais montré** avant « c'est bien moi »
  (expériences, formation, années d'expérience). `AliceExperience.tsx`.
- 🟡 **Mode dégradé sans IA** : « Paris » par défaut, « 45 ans » lu comme 45 ans
  d'expérience, compétences seulement techniques. `resume_parser.py`.
- 🟡 **CV en anglais ou long** : puces non traduites, fin du CV tronquée sans le
  dire au-delà de 12 000 caractères. `resume_parser.py`.
- 🟡 **Ville figée à « France »** sur tous les CV générés. `cv_resolver.py`,
  `cv-profile.ts`.

---

## 3. Audit — série 3 : après l'envoi

Suivi, réponses, extension.

- 🟠 **Réponse via un ATS : on répond au no-reply** (le Reply-To d'origine n'est
  pas lu). `inbox.py`, `inbox-client.ts`.
- 🟠 **Après le premier échange, le fil sort d'Alice** : mettre l'adresse de
  réponse d'Alice en copie dans le transfert et le bouton « Répondre ».
- 🟠 **Changer l'e-mail dans l'éditeur de CV détourne la réception, sans
  vérification**. Séparer e-mail du CV et adresse du compte.
  `cv-profile.ts`, `api/candidates.py`.
- 🟠 **L'extension remplit aussi les cadres de tiers** (chat, publicité) et met
  le CV dans n'importe quel champ fichier (photo, diplôme). `background.js`,
  `fields.js`, `manifest.json`.
- 🟠 **Formulaire en plusieurs étapes** : fausse question « Tu as envoyé ? » et
  statut qui recule (Entretien → Envoyée). `content.js`, `api/apply.py`
  (`mark_applied`).
- 🟠 **Candidature finie depuis sa messagerie** : réponses invisibles pour Alice
  (adresse de réponse absente du mailto) ; invitation à noter une réponse
  masquée. `outcome.py`, `MessagesView.tsx`.
- 🟠 **Relance « en un clic » souvent sans destinataire**, promet un CV en pièce
  jointe impossible par mailto, retouches non enregistrées. `followup.py`,
  `CandidaturesView.tsx`.
- 🟡 Corps de l'e-mail introuvable chez Resend : message vide pour toujours
  (ne pas enregistrer, laisser Resend réessayer).
- 🟡 Un même e-mail adressé à deux candidats n'est livré qu'au premier.
- 🟡 Une erreur de chargement de la boîte s'affiche comme « réception pas encore
  active ».
- 🟡 Alice sous-compte les candidatures envoyées (APPLIED seulement) et ne sait
  pas lire la boîte de réception dans la conversation.

---

## 4. Missions et dossiers (restes de l'audit, hors série 1)

- 🟠 **Mandat resserré : les offres déjà préparées partent quand même**.
  `tasks.py` l. 594-596, `mission_runner.py`.
- 🟠 **Message trompeur « à envoyer toi-même sur le site »** pour tout refus
  (quota, pause, CV impossible…). `mission_runner.py` l. 295-306.
- 🟠 **Chaque mission retraite les mêmes dossiers et gonfle les compteurs**.
  `mission_runner.py` (`_targets`).
- 🟡 Offre en anglais : lettre et CV toujours en français.
- 🟡 E-mail de fin de mission : toujours « 0 offres vues » (`scanned` jamais
  compté).
- 🟡 Quota affiché ≠ quota appliqué (`missions.py` vs `dispatcher.py`).
- 🟡 Nom « Employeur non précisé » encore brut dans certains messages
  (`mission_runner.py`, `dispatches.py`, `apply.py`).
- 🟡 Deux missions lancées en même temps : verrou non transactionnel (non
  prouvé).
- 🟡 Offres anonymes **déjà fusionnées** en production avant le commit 505030b :
  non réparées rétroactivement.

---

## 5. Configuration et mise en production (de ton côté)

- 🔴 **Fusionner et redéployer** la branche `claude/eloquent-franklin-ls77hs`
  (migrations Alembic jusqu'à `a3d7e9f1c2b5`).
- 🟠 **Abonnement Lemon Squeezy** : produit hebdomadaire, variables
  `LEMONSQUEEZY_*`, webhook `/api/billing/lemonsqueezy` (voir README,
  « Abonnement »), test en mode test avant la mise en production.
- 🟡 Pas de limite de taille sur `/api/inbound/email` (pièces jointes jusqu'à
  ~25 Mo) ; l'API Resend des pièces jointes reçues est supposée, non vérifiée.
- 🟡 Les codes ROME BTP / Enseignement ajoutés (`france_travail.py`) sont à
  vérifier.
- 🔴 `FRONTEND_URL` sur Railway (sinon les liens des e-mails mènent à localhost).
- 🟠 **Envoi des e-mails** : Scaleway Transactional Email (domaine vérifié SPF /
  DKIM / DMARC, `SCALEWAY_TEM_SECRET_KEY`, `SCALEWAY_PROJECT_ID`). Railway
  bloque le SMTP hors offre Pro.
- 🟠 **Réception des réponses** : Cloudflare Email Routing + Worker
  (`infra/cloudflare-email-worker/`), `INBOUND_SECRET`, test, puis
  `INBOUND_DOMAIN`.
- 🟠 **Extension** : compte développeur Chrome Web Store, domaine de production
  dans `manifest.json`, politique de confidentialité.
- 🟡 Worker / beat Celery non déployés (la collecte des ATS se rattrape à la
  première recherche, au plus toutes les 20 h).
- 🟡 Retester en production le téléchargement du CV adapté et du dossier.

---

## 6. Sécurité

- 🔴 **Révoquer les deux clés Meta** partagées dans la conversation et en créer
  une nouvelle, gardée hors du dépôt (variable d'environnement uniquement).
- 🟠 Garde d'accès `guard_candidate_path` non auditée en détail (l'audit n'a
  rien trouvé d'anormal sur les routes lues).
