# Alice Community

La liste publique des alternances et des stages, sur le modèle des listes de
stages de Simplify : un canal d'acquisition gratuit. Chaque offre renvoie à
l'annonce d'origine et propose « Postuler avec Alice ».

## Ce qui existe

- **API** (publique, sans connexion, cache de 15 min) :
  - `GET /api/community/recherche?kind=alternance|stage|emploi&q=&city=&family=&alice=&new=&direct=&page=` : recherche paginée (50 par page) avec les métiers présents ;
  - `GET /api/community/offres/{id}` : une offre (lien « Avec Alice » de la liste GitHub) ;
  - `GET /api/community/offres?kind=…` : liste complète d'un type (sans type : alternances et stages) ;
  - `GET /api/community/liste.md?kind=alternance|stage` : la liste en Markdown.
- **Page** : `alice-agent.fr/communaute`, statique, régénérée toutes les 15 min,
  filtres par métier, ville, « Alice envoie », nouveautés.
- **Passage vers Alice** : « Postuler avec Alice » retient l'offre, mène à
  l'inscription (ou au tableau de bord), puis l'ajoute à la liste du candidat
  et l'ouvre (`POST /api/candidates/{id}/apply/{job}/adopt`).
  Lien direct : `/communaute?offre=<id>` (utilisé par la liste GitHub).

## Sources

- Offres d'Alice : France Travail, La bonne alternance, sites carrière
  (Greenhouse, Lever, Ashby, Workable, Recruitee). Prioritaires en cas de
  doublon : ce sont celles où Alice sait postuler.
- **Agrégateurs** (table `external_listings`, collecte quotidienne à 4 h 40 UTC,
  tâche `collect_aggregators`) :
  - **Adzuna** : renseigner `ADZUNA_APP_ID` et `ADZUNA_APP_KEY` dans Railway
    (clé gratuite sur developer.adzuna.com). Conditions lues le 12/10/2026 :
    publication permise si chaque offre porte la mention « Adzuna » liée à
    adzuna.fr (fait sur la page, la fenêtre et la liste GitHub) ; 250 appels
    par jour, 1 000 par semaine, 2 500 par mois. La collecte en fait au plus 30
    par jour (`ADZUNA_PAGES_PER_QUERY`, 10 par défaut, × 3 recherches).
    En fin de partenariat, retirer leurs données :
    `python -c "import asyncio; from app.agents.discovery.aggregators import purge_source; print(asyncio.run(purge_source('adzuna')))"`
  - **Jooble** : connecteur prêt mais inactif. Ne renseigner `JOOBLE_API_KEY`
    qu'après avoir lu leurs conditions (non consultables d'ici) et vérifié
    la forme de leur API, qui n'a pas pu être testée.
- Jamais d'extraction depuis Indeed ou LinkedIn (CGU, droit des bases de
  données). Une offre vue là-bas s'ajoute à son propre Alice via l'extension.
- Une offre d'agrégateur choisie sur la liste devient une offre privée du
  candidat (`POST /api/candidates/{id}/apply/listing/{listing}/adopt`) :
  CV et lettre préparés depuis l'extrait, candidature finie sur le site.

## Publier la liste sur GitHub (une fois)

1. Créer un dépôt **public**, par exemple `alice-community/alternances-2027`.
2. Y copier le contenu de `github-list/` (README.md, STAGES.md, `.github/`).
3. Dans le dépôt : Settings → Secrets and variables → Actions → **Variables** →
   `ALICE_API_URL` = l'adresse publique de l'API (celle de Railway).
4. Onglet Actions → « Mise à jour de la liste » → **Run workflow**.
   Ensuite, l'action tourne seule chaque matin.
5. Ajouter au dépôt une description et les sujets `alternance`, `stage`,
   `emploi`, `france`, `etudiants` : c'est ce qui le fait remonter.

## Règles de contenu

- Montré : intitulé, employeur, ville, date, source. Ni description ni
  coordonnées de recruteur. La source est citée et l'annonce d'origine liée.
- Exclu : offres collées par un candidat, employeurs anonymes, offres que la
  source ne liste plus depuis 10 jours ou publiées il y a plus de 60 jours.

## Premier emploi

Onglet des CDI et CDD ouverts aux jeunes diplômés : expérience exigée de
2 ans au plus selon la source (France Travail : « débutant accepté » = 0),
ou, sans cette donnée, une annonce qui le dit (« débutant accepté », « jeune
diplômé », « junior »…). Un intitulé « senior », « confirmé », « manager »…
l'exclut toujours. La liste GitHub reste celle des alternances et des stages.
