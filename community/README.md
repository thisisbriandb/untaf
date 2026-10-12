# Alice Community

La liste publique des alternances et des stages, sur le modèle des listes de
stages de Simplify : un canal d'acquisition gratuit. Chaque offre renvoie à
l'annonce d'origine et propose « Postuler avec Alice ».

## Ce qui existe

- **API** (publique, sans connexion, cache de 15 min) :
  - `GET /api/community/offres?kind=alternance|stage` : JSON pour la page ;
  - `GET /api/community/liste.md?kind=alternance|stage` : la liste en Markdown.
- **Page** : `alice-agent.fr/communaute`, statique, régénérée toutes les 15 min,
  filtres par métier, ville, « Alice envoie », nouveautés.
- **Passage vers Alice** : « Postuler avec Alice » retient l'offre, mène à
  l'inscription (ou au tableau de bord), puis l'ajoute à la liste du candidat
  et l'ouvre (`POST /api/candidates/{id}/apply/{job}/adopt`).
  Lien direct : `/communaute?offre=<id>` (utilisé par la liste GitHub).

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
