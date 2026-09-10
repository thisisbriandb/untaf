# Moteur de candidature — spécification

## 1. Objectif

Aujourd'hui, une candidature aboutit sur une plateforme et une seule
(Greenhouse), et aucune n'est jamais réellement partie. L'objectif est de
maximiser le nombre de candidatures **réellement automatisables** sur le stock
déjà collecté, sans revenir vers l'utilisateur à chaque offre.

Principe directeur :

> Ne jamais demander à l'utilisateur une information ou une action qui peut
> être résolue automatiquement de manière fiable.

### Où en est le stock — mesures, pas estimations

```
total                                  1 986
── France Travail (portail)              805   40,5 %
── ATS (Greenhouse / Ashby / Lever)    1 046   52,7 %
── formulaire employeur                   86    4,3 %
── e-mail                                  49    2,5 %   (0 adresse valide)

éprouvé de bout en bout (Greenhouse)     817   41,1 %
jamais éprouvé                         1 169   58,9 %
```

Le chiffre de « 83 % non exploités » ne correspond à aucune mesure. Les deux
vrais chiffres sont **40,5 %** (France Travail) et **58,9 %** (jamais éprouvé
de bout en bout). Cette correction change l'ordre des priorités : le gisement
principal n'est pas France Travail, c'est le stock ATS qu'on collecte déjà et
qu'on ne sait pas encore remplir entièrement.

---

## 2. France Travail — connexion différée, jamais à l'onboarding

### Le vrai poids de France Travail

40,5 % du volume collecté. Mais rapporté aux offres **effectivement retenues**
pour les candidats :

```
Offres retenues : 386

Greenhouse       246   63,7 %   score moyen 72
Lever             71   18,4 %   score moyen 77
Ashby             63   16,3 %   score moyen 64
France Travail     6    1,6 %   score moyen 57
```

**1,6 % de la valeur, et la plus faible qualité de correspondance.** C'est la
mesure qui commande toute cette section : aucun arbitrage d'expérience
utilisateur ne se justifie pour un soixantième du bénéfice.

### Le problème d'expérience

805 offres exigent une authentification sur le portail candidat. Deux écueils :

- une demande d'authentification **au milieu d'une candidature** casse l'élan
  au pire moment ;
- une demande **à l'onboarding** est pire encore : beaucoup d'utilisateurs ne
  connaissent pas France Travail et cherchent sur Indeed ou LinkedIn. Leur
  imposer la création d'un compte ajoute une étape avant toute valeur perçue,
  et c'est là que les parcours s'abandonnent.

### Ce qui est retenu : la demande différée

France Travail **n'apparaît pas dans l'onboarding**. Alice travaille sur les
98,4 % restants. Quand elle rencontre des offres France Travail qui valent la
peine, elle le dit dans la conversation :

> « J'ai 6 offres qui passent par France Travail. Connecte ton compte une fois
> et je m'en occupe — sinon je te les mets de côté. »

La demande arrive **après** que la valeur a été démontrée, elle est
facultative, et elle est justifiée par un nombre concret. Refuser doit rester
sans conséquence : les offres sont mises de côté, pas perdues.

Une fois connecté, une **session authentifiée appartenant à l'utilisateur** est
conservée et réutilisée par l'agent navigateur pour les candidatures suivantes.

```
Utilisateur s'authentifie lui-même
        ↓
contexte de session conservé (chiffré)
        ↓
agent navigateur réutilise la session
        ↓
formulaire de candidature accessible
        ↓
remplissage + upload CV + soumission
```

Exigences de conception :

- L'utilisateur s'authentifie **lui-même**, sur les pages de France Travail.
  L'application ne saisit jamais ses identifiants à sa place.
- Aucun mot de passe n'est stocké. Seul le contexte de session l'est, chiffré
  au repos, avec une durée de vie explicite et une révocation possible depuis
  l'interface.
- La session est **strictement liée à un utilisateur**. Aucun partage entre
  comptes.
- L'expiration doit être détectée et remontée comme un état, pas comme une
  erreur technique : « ta session France Travail a expiré, reconnecte-toi »
  est une information utilisable, « HTTP 302 » ne l'est pas.

### Ce qui est écarté, et pourquoi

**Compte candidat mutualisé** (un compte pour plusieurs utilisateurs).
Trois raisons, dont deux suffiraient séparément :

- *Ça ne tient pas techniquement.* Un compte qui postule à des centaines
  d'offres, depuis des IP variées, avec des CV portant des noms différents, est
  détecté rapidement. La sanction est la fermeture du compte : on perdrait le
  canal entier, pas une candidature.
- *Ça pollue le dossier d'un tiers.* L'espace candidat enregistre les
  candidatures comme actes positifs de recherche d'emploi, qui conditionnent
  l'indemnisation. Y mélanger les démarches de plusieurs personnes altère le
  dossier d'un demandeur d'emploi réel.
- *Ça présente une fausse identité* au recruteur et au service public.

Écarté.

**Création automatique d'un compte France Travail à l'onboarding.**
« Demandeur d'emploi » est un statut administratif porteur de droits et
d'obligations. Le créer programmatiquement au nom d'un utilisateur revient à
déposer une déclaration auprès d'une administration à sa place. Écarté.

### À valider avant implémentation

- Les CGU de France Travail sur l'accès automatisé à l'espace candidat.
- **France Travail Connect** comme alternative officielle. Réserve établie :
  ses API en écriture sont *Ajout de compétence* et *Déclaration de démarche*
  — **il n'existe pas d'API « postuler »**. L'accès est conditionné à un audit
  et le service doit être gratuit pour les demandeurs d'emploi.

Autrement dit : même par la voie officielle, les 805 offres ne deviennent pas
candidatables par API. La session navigateur reste le seul chemin.

---

## 3. Socle candidat — collecter une fois, réutiliser partout

**C'est le chantier prioritaire.** Il débloque plus d'offres que France
Travail (1 046 contre 805) et ne dépend d'aucune validation externe.

### Le problème, mesuré

Sondage sur 5 boards Greenhouse réels, 50 champs obligatoires :

```
couverts par le profil actuel    22   (44 %)
hors socle                       28   (56 %)
dont listes déroulantes          22
```

Prétentions salariales, disponibilité, autorisation de travail, mobilité. Si
l'utilisateur doit répondre à chaque candidature, la promesse du produit tombe.

### Ce qu'on collecte

À la configuration du moteur — pas pendant une candidature :

| Donnée | Usage |
| --- | --- |
| Disponibilité / date de début | Champ récurrent, souvent obligatoire |
| Préavis à effectuer | Complément de la disponibilité |
| Prétentions salariales | Fourchette, pas un montant sec |
| Mobilité géographique | Ville, région, remote accepté |
| Type de contrat recherché | Déjà partiellement dans le mandat |
| Autorisation de travail | Nationalité UE, visa, besoin de parrainage |
| Permis de conduire | Fréquent hors tech |
| Niveau d'études | Souvent une liste déroulante |
| LinkedIn / GitHub / portfolio | Champs facultatifs très fréquents |

Ces réponses vivent dans le profil candidat, pas dans une candidature. Elles
sont modifiables à tout moment et réutilisées sans redemander.

### Règle

> Une information demandée plusieurs fois est collectée une seule fois.

Corollaire important : les questions **par board** se répètent. Les 156 offres
Doctolib partagent le même formulaire. Une réponse renseignée une fois
débloque tout le board.

### Ce qu'on ne remplit jamais automatiquement

Les questions démographiques — genre, origine, handicap, statut de vétéran.
Leur déclaration est facultative par construction ; y répondre à la place du
candidat serait décider pour lui. Le classifieur les marque déjà `DEMOGRAPHIC`
et les laisse vides.

---

## 4. Champs ouverts — génération contextualisée

Certains champs obligatoires ne se remplissent pas depuis une valeur statique :

> « Pourquoi souhaitez-vous rejoindre notre entreprise ? »
> « What excites you about working in healthcare ? »

Le moteur dispose déjà de tout le contexte nécessaire : CV, profil, offre,
entreprise, et souvent la lettre de motivation déjà rédigée pour cette offre.

```
CV + profil + offre + entreprise
            ↓
     analyse du contexte
            ↓
   génération de la réponse
            ↓
      remplissage du champ
```

Exigence : la réponse doit être **spécifique à l'offre**, pas un passe-partout
réutilisé. C'est déjà la règle appliquée aux lettres de motivation ; elle vaut
ici. Une réponse générique se repère immédiatement et dessert le candidat.

Contrainte de coût : **un seul appel par page**, pas un par champ. Les champs
restant à générer sont regroupés et traités ensemble.

---

## 5. Escalade — l'humain en dernier recours

Quand un champ obligatoire n'est couvert par rien :

1. chercher dans le profil candidat ;
2. dériver depuis le CV ;
3. analyser le contexte de l'offre ;
4. générer une réponse si c'est pertinent ;
5. si aucune réponse fiable n'est possible → demander à l'utilisateur.

L'intervention humaine est réservée aux cas réellement exceptionnels. Et quand
elle survient, la réponse est **enregistrée dans le socle** : la question ne
doit pas se reposer.

---

## 6. Listes déroulantes React

### État constaté

Quatre stratégies testées sur `#country` (Doctolib), quatre échecs :

1. `fill()` — écrit dans le DOM sans émettre les événements clavier attendus
2. clic sur `[role="option"]` — les 244 options sont dans le DOM en
   permanence, le clic visait un élément masqué
3. vérification par `aria-activedescendant` — attribut de pilotage clavier,
   vidé après le clic
4. frappe d'un préfixe puis `ArrowDown` + `Entrée` — la liste se filtre
   correctement (244 → 3 options), mais la sélection ne s'enregistre pas

Le comportement actuel est **honnête** : ces champs sortent en
`unhandled_fields`, jamais en « rempli ». Une version antérieure rapportait
« France » comme saisi alors que le formulaire serait parti vide.

### Ce qu'il faut

- Journaliser chaque tentative : stratégie employée, événements émis, état du
  composant avant et après. Sans cette trace, on continue de deviner.
- Détecter le type réel de composant plutôt que de supposer.
- Vérifier la prise en compte contre un **état durable**, jamais contre un
  attribut transitoire. Deux faux positifs ont déjà été introduits ainsi.
- Au-delà de N stratégies échouées, escalader vers l'agent navigateur.

C'est le cas d'escalade type : un composant dont l'interaction ne se déduit pas
du DOM.

---

## 7. Moteur DOM

Deux modules sont écrits, testés et mesurés, mais **pas encore branchés** :

```
form_parser.py       lit tous les signaux d'un champ en une seule évaluation JS
field_classifier.py  signaux → type sémantique, sans appel modèle

Doctolib (Greenhouse)   17/19 champs classés (89 %)   0 inconnu obligatoire
Alan (Ashby)            17/21 champs classés (81 %)   0 inconnu obligatoire
```

`CandidateAgent` utilise encore le schéma publié par l'ATS, ce qui le limite à
Greenhouse : Ashby ne publie pas d'API de questions, et un formulaire employeur
n'a aucun schéma.

**La bascule vers l'extracteur DOM est le prochain pas.** C'est elle qui étend
le remplissage aux 229 offres Ashby, Lever et formulaires employeurs.

Signaux à exploiter : arbre DOM, attributs, `label`, relations
`label`/`input`/`select`, composants personnalisés, événements, état React,
éléments réellement interactifs.

---

## 8. Architecture cible

```
Niveau 1  Données structurées    profil candidat
Niveau 2  Inférence              dérivé du CV, de l'offre, du contexte
Niveau 3  Génération             réponses textuelles contextualisées
Niveau 4  Interaction DOM        manipulation directe des composants
Niveau 5  Agent navigateur       exploration et interaction avancées
Niveau 6  Escalade utilisateur   dernier recours, mémorisé ensuite
```

Chaque niveau n'est sollicité que si le précédent échoue. Un formulaire
entièrement couvert par le niveau 1 ne déclenche **aucun appel modèle** —
c'est déjà le comportement de `needs_model()`.

---

## 9. Canal e-mail — reporté

Le canal couvre **0 offre exploitable** : les 49 offres classées `EMAIL`
contiennent une phrase France Travail (« Pour postuler, utiliser le lien
suivant : … ») et non une adresse.

Correctif immédiat, indépendant du reste : les reclasser en `EXTERNAL_LINK` à
l'ingestion, pour que l'interface cesse de proposer un envoi impossible.

La configuration d'envoi n'est pas un blocage : un service transactionnel
(Resend, Postmark, SES) se branche rapidement et couvre les notifications,
confirmations de candidature et demandes d'intervention. À traiter avec la
notification de fin de mission, qui manque également.

---

## 10. Priorités

### P0 — débloquer le stock déjà collecté

- [ ] Collecter le socle candidat à la configuration du moteur
- [ ] Brancher l'extracteur DOM sur `CandidateAgent`
- [ ] Générer les réponses aux champs ouverts, un appel par page
- [ ] Journaliser chaque tentative de remplissage et son résultat

### P1 — France Travail (1,6 % des offres retenues — à traiter en conséquence)

- [ ] Récupérer le bloc contact à l'ingestion : `contact_json` est **null** sur
      les 805 offres, donc `urlPostulation` n'a jamais été capturée. Certaines
      offres ont peut-être une voie directe qu'on ignore.
- [ ] Demande de connexion différée, déclenchée dans la conversation
- [ ] Valider les CGU sur l'accès automatisé
- [ ] Session utilisateur persistante, chiffrée, révocable
- [ ] Détection et remontée lisible de l'expiration de session

### P2 — fiabilité d'interaction

- [ ] Résoudre les listes déroulantes React
- [ ] Escalade vers l'agent navigateur après N échecs
- [ ] Vérification systématique contre un état durable

### P3 — notifications

- [ ] Service d'emailing transactionnel
- [ ] Notification de fin de mission
- [ ] Reclasser les 49 offres `EMAIL`

---

## Résultat attendu

Un moteur qui ne se contente pas de « remplir un formulaire », mais qui
comprend, complète, vérifie et corrige une candidature — et qui, quand il ne
sait pas, le dit plutôt que de le prétendre.
