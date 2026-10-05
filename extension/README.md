# Extension navigateur Alice (prototype)

Alice agit **dans ton navigateur, sur ta session** : elle ajoute à ta liste
l'offre que tu regardes, et remplit le formulaire de candidature que tu as sous
les yeux (identité, lettre, CV adapté joint, réponses tirées de ton parcours).
**Le bouton « Envoyer » reste à toi** : rien ne part sans ton clic.

## Installer (mode développeur)

1. `chrome://extensions` → activer « Mode développeur ».
2. « Charger l'extension non empaquetée » → choisir ce dossier `extension/`.
3. Se connecter sur le site d'Alice (alice-agent.fr, ou http://localhost:3000
   en local) : l'extension reprend la session toute seule (`bridge.js` lit la
   session et l'adresse de l'API, publiée par le site dans
   `<meta name="alice-api">`).

## Ce qu'elle fait

- **Pastille** (les deux yeux) en bas à droite, *seulement* sur une page qui
  ressemble à une offre (JSON-LD `JobPosting`, ATS connu : Greenhouse, Lever,
  Workable, Recruitee, Welcome to the Jungle, Indeed, LinkedIn…) ou à un
  formulaire de candidature (champ CV), y compris dans un iframe. Ailleurs,
  l'extension n'affiche rien et **n'envoie rien** au serveur.
- **Ajouter à Alice** : envoie le texte de l'annonce à `POST /apply/import` ;
  l'offre entre dans ta liste avec son score et ses motifs.
- **Remplir avec Alice** : retrouve l'offre (`GET /extension/match?url=`), ou
  l'ajoute, puis chaque cadre de la page remplit ce qu'il contient :
  - prénom, nom, e-mail, téléphone, LinkedIn, GitHub, site, ville ;
  - la lettre du dossier dans le champ « lettre / motivation » ;
  - le **CV adapté à l'offre** (PDF) dans le champ fichier (rédigé à la
    demande s'il ne l'est pas encore) ;
  - les autres questions via `POST /extension/answers` (Gemini), à partir du
    parcours et de l'offre, **sans rien inventer** : sans réponse, le champ
    reste vide.
  - Jamais remplis : RGPD/consentement, conditions, handicap, genre, origine…
  - Vert = rempli, orange = à compléter toi-même. Une saisie existante n'est
    jamais écrasée.
- **Après l'envoi** : « Tu as envoyé ta candidature ? » → la candidature
  passe dans ton suivi (`mark-applied`), relance comprise.

## Fichiers

| Fichier | Rôle |
|---|---|
| `manifest.json` | MV3 |
| `background.js` | seul à parler à l'API (jeton, pas de CORS), cache du CV, relais entre cadres |
| `bridge.js` | sur le site d'Alice : transmet la session |
| `fields.js` | lecture des champs (libellés, groupes, options) et saisie compatible React/Vue |
| `content.js` | détection d'offre, pastille, remplissage par cadre, suivi de l'envoi |
| `popup.html/js` | état de connexion et les deux gestes sur l'onglet ouvert |

## Limites du prototype

- Permission `<all_urls>` : nécessaire pour remplir sur n'importe quel ATS ;
  à justifier lors d'une publication sur le Chrome Web Store.
- Formulaires en plusieurs étapes (Workday, Taleo) : remplir étape par étape
  (relancer « Remplir » sur chaque page). Listes déroulantes « maison »
  (non `<select>`) : laissées en orange.
- Le domaine de production du site doit figurer dans `manifest.json`
  (`alice-agent.fr` par défaut) pour que la session soit reprise.
