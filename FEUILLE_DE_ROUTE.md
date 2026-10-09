# Feuille de route — avant le lancement

Décidé avec Briand le 9 octobre 2026. On coche au fur et à mesure, avec le
commit en référence. Les problèmes de fond restent listés dans
`PROBLEMES_OUVERTS.md`.

Ordre : **1 → 2 → 3 → 4 → 5**, l'infrastructure payante au lancement.

---

## 1. Architecture et tenue en charge (le plus critique)

Constat : les 10 Go de trafic sortant Supabase (204 % du quota gratuit, période
de grâce jusqu'au **8 novembre**, ensuite erreurs 402 = Alice coupée) viennent
du code, pas de l'hébergement. Charger un candidat ramenait son CV en PDF, sa
photo, sa signature, toutes ses candidatures et toutes les offres liées ; ce
chargement était répété toutes les 2,5 s (mission), 30 s (cloche) et 2 min
(messages), même onglet caché.

- [x] Relations en cascade coupées (candidat → candidatures → offres,
      entreprise → offres)
- [x] Les rafraîchissements automatiques ne chargent plus le candidat
      (mission, journal, messages) et s'arrêtent quand l'onglet est caché
- [x] PDF des envois (`resume_blob`) chargés seulement au téléchargement
- [x] Recherche d'offres dans le chat : import et recalcul limités (plus à
      chaque message)
- [x] Mise en page des CV (Typst) hors du fil principal du serveur
- [ ] Mesurer : trafic sortant Supabase sur 48 h après déploiement

**Infrastructure — à décider au lancement**

| | Quand | Pourquoi |
|---|---|---|
| Supabase Pro (25 $) | dès que de vrais utilisateurs arrivent | sauvegardes quotidiennes, connexions, pas de pause ; et si le trafic dépasse encore 5 Go après correction |
| Railway Pro (20 $) | au lancement | plusieurs instances, service « worker » pour les missions, logs 30 jours |
| VPS | non | administration système à notre charge, une seule machine |

À faire à la mise en production (configuration) :
- [ ] Service `worker` (Celery) + Redis sur Railway : les missions ne tournent
      plus dans le serveur web
- [ ] `DATABASE_URL` sur le *Transaction pooler* de Supabase (port 6543)
- [ ] Quota d'envoi Scaleway relevé (la connexion passe par e-mail)
- [ ] Alerte de budget Gemini (Google Cloud)

## 2. Faille et abus (coûts non maîtrisés)

- [x] Routes sans connexion qui appellent l'IA ou Typst : connexion
      obligatoire pour `cv-content`, `audit-cv`, `download-cover-letter` ;
      limites par heure (IP sans connexion, compte sinon, plafond global) pour
      celles de l'inscription (`parse-resume` 5/h/IP, `parse-linkedin`,
      `download-cv`, `render-cv`, `render-preview-svg`)
- [x] `parse-linkedin` : seulement https://*.linkedin.com (le serveur allait
      chercher n'importe quelle adresse contenant « linkedin.com »)
- [x] Comptés comme un message : import d'offre collée, réponses de
      l'extension, relance rédigée, lettre écrite pendant une candidature (et
      plus aucune lettre pour une offre hors de la liste)
- [x] Limite atteinte au téléchargement : 402, plus d'erreur 500 ni d'alerte
- [x] Dossier réservé avant l'appel à l'IA, sous verrou, rendu en cas d'échec
      (vérifié : 10 demandes simultanées, limite 3 → 3 accordées)
- [x] Téléchargements et mises en page : plafond horaire par compte (au lieu
      d'un cache)
- [ ] Recherches d'entreprises ratées des spontanées : non comptées (bornées
      par mission : 5 × le nombre demandé)
- [ ] Un message à Alice peut coûter 3 à 5 appels au modèle (outils) : borné
      par la limite de messages, à surveiller sur la facture Gemini

## 3. Offres d'écoles et de CFA

Décision : **écartées quand l'indice est fort**, signalées sinon.

- [x] Garder à l'import : secteur et code NAF (France Travail), NAF, SIRET et
      raison sociale (La bonne alternance), dans `description_parsed.employer`
- [x] Règle « organisme de formation » (`signals.training_org_evidence`) :
      NAF 85, nom (école, CFA, campus, institut, academy… sauf vrais
      employeurs : Institut Pasteur, CNRS…), phrases (« formation gratuite et
      rémunérée », « entreprises partenaires », « admissions »…)
- [x] Deux indices concordants → écartée (motif « organisme de formation »
      dans le journal) ; un seul → gardée avec « ⚠ Probablement une école qui
      recrute des élèves » ; seulement pour l'alternance et les stages (un CDI
      de formateur dans un CFA reste un vrai poste)
- [ ] À valider sur de vraies offres : me signaler toute école passée au
      travers ou tout vrai poste écarté, pour ajuster les phrases

## 4. L'utilisateur au centre

- [x] Boutons de réponse sous la dernière question d'Alice (« Oui, montre-moi
      » / « Plus tard », « Oui, vas-y » / « Pas maintenant »…)
- [x] Inscription : étape « L'allure de tes CV » (modèle, couleur, photo, avec
      l'aperçu de son vrai CV), enregistrée au profil avant la première
      mission : tous les dossiers la suivent
- [x] Inscription : étape « Ta signature » ; sans signature, une candidature
      attend avant l'envoi (signer une fois, ou feu vert pour l'envoyer ainsi)
- [x] Accueil : ce qu'Alice sait faire, en 3 cartes cliquables
- [ ] Photo du CV importé proposée d'office (extraction de l'image du PDF)
- [ ] À valider en vrai : un parcours d'inscription complet sur mobile et
      ordinateur

## 5. Passage à l'abonnement

Décision : **en gratuit, une mission prépare les dossiers inclus et montre les
autres offres verrouillées** (on ne paie jamais ce qui est verrouillé).

- [x] Mission gratuite : au-delà de la formule, les offres retenues sont
      annoncées (« J'ai retenu N autres offres pour toi : … ») avec un bouton
      « Débloquer », sans rien rédiger pour elles
- [x] Spontanées : choix visible mais verrouillé (🔒 3, 🔒 5) ; un clic ouvre
      la proposition, l'assistant de mission reste ouvert dessous
- [x] Bilan de la semaine (e-mail) : en gratuit, nombre d'offres retenues qui
      attendent leur dossier, et ce que l'abonnement débloque
- [x] Au bon moment : 4ᵉ dossier, téléchargement, message, mission → fenêtre
      d'abonnement (402) ; encart permanent dans la barre latérale
- [ ] Mesurer : taux de passage à l'abonnement, et à quel moment (Lemon
      Squeezy + `usage_events`)
