# Banc d'essai « computer use »

Mesure, sur de vrais formulaires de candidature, ce qu'un modèle qui « voit »
l'écran (Muse Spark de Meta, ou tout modèle compatible) sait remplir : taux de
remplissage, nombre d'étapes, temps, jetons consommés, et où il bloque.

**Rien n'est jamais soumis** : toute requête autre que GET est coupée au niveau
du réseau, un clic sur un bouton d'envoi est refusé, la touche Entrée aussi. Le
candidat est fictif (Camille Test, `example.com`).

## Lancer (sur ta machine : la clé reste chez toi)

```bash
cd tools/agent-bench
npm install && npx playwright install chromium
export MODEL_API_KEY=...            # clé Meta Model API

node bench.mjs --probe              # 1. la clé et le format de réponse sont-ils bons ?
node bench.mjs                      # 2. formulaire de test local
node bench.mjs <url> <url> ...      # 3. vrais formulaires (Greenhouse, Lever, Workday…)
HEADLESS=0 node bench.mjs <url>     #    pour regarder le navigateur travailler
```

Chaque lancement écrit `report-<date>.json` (champs remplis, actions, jetons,
requêtes bloquées) et une capture `result-<site>.png`. Envoie-moi le rapport :
c'est lui qui dira si ça vaut une intégration.

Autre modèle : `MODEL_API_BASE` et `MODEL` (API au format « Responses »).

## La sonde : rejouable, navigateur ou extension ? (sans IA)

```bash
node probe.mjs <url> [<url> …]          # ou : node probe.mjs --file liens.txt
```

Pour chaque lien « Postuler » : elle rend la page, lit les champs (noms, types,
obligatoires, champs cachés, part déjà présente dans le HTML brut), remplit
avec le candidat fictif, clique sur « Envoyer » et **coupe la requête** — rien
ne part, mais elle note ce qui serait parti (adresse, format JSON / multipart /
urlencoded, noms des champs, en-têtes comme `next-action` ou un jeton CSRF).
Verdict :

- **rejouable** : la requête d'envoi est connue et sans captcha → Alice peut
  l'envoyer sans navigateur ;
- **navigateur** : formulaire présent mais pas de requête observée (champs
  obligatoires non reconnus, envoi en plusieurs étapes) ;
- **extension** : captcha ou connexion demandée → seulement dans le navigateur
  du candidat, avec son clic ;
- **introuvable** : pas de formulaire sur la page.

Rapport : `probe-<date>.json` et une capture par site.

## À savoir

- Le format exact de l'outil `computer` de Meta n'a pas pu être vérifié depuis
  l'environnement de développement : il suit leur documentation (outil
  `{"type": "computer"}`, réponses `computer_call`, retours
  `computer_call_output` avec capture). Si `--probe` renvoie une erreur de
  format, le rapport d'erreur suffit pour corriger.
- Les sites avec compte, captcha ou anti-robot bloqueront : c'est justement ce
  qu'on veut mesurer.
