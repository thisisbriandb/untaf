# Publier l'extension sur le Chrome Web Store

Paquet : `./build.sh` → `dist/alice-extension-<version>.zip` (manifest de
production : sans `localhost`). Visuels : `store/`.

## 1. Compte développeur (une fois)

1. https://chrome.google.com/webstore/devconsole — se connecter avec le compte
   Google qui portera l'extension (idéalement un compte dédié à Alice).
2. Payer les frais d'inscription uniques (5 $), accepter le contrat.
3. Renseigner l'adresse e-mail de contact et la **vérifier** (obligatoire pour
   publier).

## 2. Nouvel élément

« Nouvel élément » → importer `dist/alice-extension-1.0.0.zip`.

## 3. Fiche (onglet « Fiche Play Store »)

- **Langue** : français.
- **Nom** (repris du manifest) : Alice — candidatures en un clic
- **Résumé** (repris du manifest, 132 caractères max) :
  Alice remplit le formulaire de candidature avec ton CV adapté et ta lettre. Tu relis, tu cliques sur Envoyer.
- **Description** :

```
Postuler, c'est remplir dix fois les mêmes champs. Alice le fait pour toi.

Sur une offre d'emploi ou un formulaire de candidature, clique sur « Remplir avec Alice » :
• tes coordonnées (nom, e-mail, téléphone, LinkedIn…) ;
• ton CV adapté à cette offre, joint au bon champ ;
• ta lettre de motivation rédigée pour cette entreprise ;
• les réponses aux questions du formulaire, tirées de ton parcours — sans rien inventer.

Les champs remplis passent en vert, ceux qu'Alice ne peut pas remplir en orange. Tu relis, tu complètes, et c'est toi qui cliques sur « Envoyer ».

Tu gardes la main
• Tes identifiants restent chez toi : l'extension utilise ta session sur les sites d'emploi, sans jamais lire ni envoyer tes mots de passe.
• Rien ne part sans ton clic.
• Les champs sensibles (consentements, handicap, genre, origine…) ne sont jamais remplis.
• Discrète : elle n'apparaît que sur les offres d'emploi et les formulaires de candidature.

« Ajouter à Alice » range aussi l'offre que tu regardes dans ta liste, avec ton score de correspondance, et Alice suit ta candidature une fois envoyée.

Nécessite un compte Alice (gratuit) sur alice-agent.fr.
```

- **Catégorie** : Productivité (ou « Outils » selon la liste proposée).
- **Icône** : `store/icone-128.png` (dessin 96×96 et marge transparente de 16 px, comme le demande Google).
- **Image promotionnelle en haut de la page** (1400×560, facultative) : `store/banniere-1400x560.png`.
- **Captures d'écran** (1280×800) : `store/capture-1-remplissage.png`,
  `store/capture-2-confiance.png`.
- **Petite vignette promotionnelle** (440×280) : `store/vignette-440x280.png`.
- **Site officiel** : https://www.alice-agent.fr
- **Assistance** : briand@alice-agent.fr

## 4. Confidentialité (onglet « Pratiques de confidentialité »)

**Objectif unique** :

```
Aider le candidat à postuler aux offres d'emploi : ajouter l'offre consultée à sa liste Alice et remplir le formulaire de candidature ouvert avec son profil, son CV adapté et sa lettre. Le candidat relit et envoie lui-même.
```

**Justification des autorisations** :

- `storage` :
  ```
  Garder la session Alice de l'utilisateur (pour ne pas lui redemander de se connecter) et, temporairement, le CV adapté à l'offre en cours de remplissage.
  ```
- `webNavigation` :
  ```
  Lister les cadres (iframes) de l'onglet : de nombreux formulaires de candidature (Greenhouse, Lever, Workday…) sont intégrés dans un iframe sur le site de l'employeur. L'extension remplit chaque cadre avec ce qu'il contient.
  ```
- Accès aux sites (`<all_urls>` et scripts de contenu sur http/https) :
  ```
  Les offres et formulaires de candidature sont hébergés sur des milliers de domaines différents (sites carrière des employeurs, ATS comme Greenhouse, Lever, Workday, Teamtailor, SmartRecruiters…) qu'il est impossible de lister à l'avance. Le script détecte localement si la page est une offre ou un formulaire de candidature ; sur toute autre page, il n'affiche rien et n'envoie rien. Le remplissage n'a lieu que sur un clic de l'utilisateur, et l'envoi de la candidature reste toujours son geste.
  ```
- Code distant : **Non**, l'extension n'exécute aucun code distant (elle appelle
  l'API d'Alice pour des données, pas pour du code).

**Utilisation des données** — cocher :

- ☑ Informations permettant d'identifier personnellement l'utilisateur (nom,
  e-mail, téléphone, CV : utilisés pour remplir les formulaires).
- ☑ Informations d'authentification (le jeton de session Alice, pas les
  identifiants des sites d'emploi).
- ☑ Contenu du site Web (texte de l'annonce et intitulés des champs, envoyés à
  Alice sur un clic de l'utilisateur ; adresse de la page d'offre).
- ☑ Historique Web (l'adresse d'une page qui ressemble à une offre est envoyée
  automatiquement pour savoir si l'offre est déjà dans la liste).
- ☐ Tout le reste (santé, finances, localisation, activité utilisateur,
  communications) : non. Le clic sur « Envoyer » n'est remarqué que localement.

Puis cocher les trois engagements (pas de vente à des tiers, pas d'usage sans
rapport avec l'objectif unique, pas d'usage pour évaluer la solvabilité).

**Règles de confidentialité** : https://www.alice-agent.fr/confidentialite

## 5. Instructions de test pour la revue

Les reviewers ont besoin d'un compte. Créer un compte Alice dédié
(ex. `revue-chrome@alice-agent.fr`), y déposer un CV de démonstration, puis
coller dans « Instructions de test » :

```
1. Se connecter sur https://www.alice-agent.fr avec le compte de test fourni (lien de connexion envoyé à l'adresse indiquée, ou code : voir ci-dessous).
2. L'extension reprend la session automatiquement (bouton de l'extension : « Connecté »).
3. Ouvrir une offre, par exemple sur https://www.alice-agent.fr/communaute → « Annonce » sur une offre d'un site carrière (Greenhouse, Lever…).
4. Sur la page de l'offre ou du formulaire, cliquer sur la pastille Alice (en bas à droite) puis « Remplir avec Alice ». Les champs remplis passent en vert. Rien n'est envoyé au recruteur sans clic sur « Envoyer ».
```

Attention : la connexion se fait par lien ou code reçu par e-mail. Il faut
donc que la boîte du compte de test soit lisible par toi pendant la revue
(transférer le code au besoin), ou prévoir un accès de test.

## 6. Envoyer en revue

« Envoyer pour examen ». Avec l'accès à tous les sites, l'examen est plus long
(souvent quelques jours, parfois plus). Choisir « Publier automatiquement
après approbation » ou publier à la main.

Après publication : remplacer sur le site les mentions « Bientôt » par le lien
du Chrome Web Store.

## Mettre à jour

Augmenter `version` dans `manifest.json`, relancer `./build.sh`, importer le
nouveau zip dans « Package » → « Importer un nouveau package ».
