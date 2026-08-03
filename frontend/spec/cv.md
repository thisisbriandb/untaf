# Respecter les choix de l'utilisateur dans l'éditeur de CV

L'ensemble du parcours, depuis l'onboarding jusqu'au dashboard, doit respecter les choix exprimés par l'utilisateur concernant son CV. Le système ne doit jamais imposer un modèle, une mise en page ou une personnalisation qui n'a pas été explicitement demandée.

## Ne pas imposer un modèle de CV

Si l'utilisateur indique qu'il souhaite conserver son CV d'origine, aucun modèle ne doit lui être attribué automatiquement.

Le Canva doit alors s'ouvrir avec son CV actuel, tel qu'il a été importé, afin qu'il puisse simplement consulter ou modifier son contenu sans que la présentation soit modifiée.

En revanche, si l'utilisateur exprime le souhait de changer de modèle ou de moderniser son CV, c'est à ce moment-là qu'Alice peut lui proposer les différents modèles disponibles.

Le choix du modèle doit toujours être une décision de l'utilisateur et non une décision prise par le système.

---

## Préserver la liberté de personnalisation

Aujourd'hui, lorsqu'un modèle est appliqué automatiquement, celui-ci impose également sa palette de couleurs et son apparence générale.

Cette approche limite la personnalisation.

L'utilisateur devrait pouvoir choisir indépendamment :

* le modèle ;
* les couleurs ;
* le style visuel ;
* les différents paramètres de personnalisation.

L'objectif est que le Canva soit entièrement configurable selon les préférences de l'utilisateur, sans imposer de choix par défaut.

---

## Adapter le flux d'ouverture du Canva

Lorsque l'utilisateur ouvre son CV depuis la conversation avec Alice, plusieurs cas doivent être pris en compte.

### Cas n°1 : conserver le CV original

Alice ouvre directement le Canva avec le CV importé.

L'utilisateur peut consulter et modifier son contenu sans changer son apparence.

### Cas n°2 : modifier uniquement le contenu

Si l'utilisateur souhaite uniquement modifier certaines informations (expériences, compétences, résumé, etc.), le système conserve la mise en page actuelle.

### Cas n°3 : changer le design du CV

Si l'utilisateur souhaite modifier le design ou la structure de son CV, Alice peut alors proposer un changement de modèle.

Cette étape doit intervenir uniquement lorsque l'utilisateur en manifeste le besoin.

---

## Penser les parcours dans leur globalité

Chaque interaction doit prendre en compte les différentes intentions possibles de l'utilisateur.

Le produit ne doit pas être conçu autour d'un parcours unique, mais autour de plusieurs scénarios :

* conserver son CV tel quel ;
* modifier uniquement les informations ;
* moderniser la présentation ;
* changer complètement de modèle ;
* personnaliser le design.

L'objectif est d'éviter les comportements automatiques qui donnent une impression de produit inachevé ou qui vont à l'encontre des attentes de l'utilisateur.

---

# Renforcer le rôle d'Alice dans la génération de contenu

Au-delà de l'UX/UI, il serait pertinent de renforcer l'intelligence comportementale d'Alice.

Une approche intéressante serait de définir un véritable **agent** à travers un ensemble de prompts système ou un fichier de configuration décrivant son comportement, son rôle et sa manière de rédiger.

Cela permettrait d'obtenir des réponses plus cohérentes et plus qualitatives tout au long de l'expérience.

---

## Produire un contenu réellement personnalisé

Aujourd'hui, les résumés générés pour les CV restent souvent très génériques.

On retrouve régulièrement des formulations comme :

* « Passionné par les nouvelles technologies... »
* « Développeur motivé... »
* « Curieux et autonome... »

Ce type de contenu est devenu extrêmement courant et n'apporte que très peu de différenciation.

À la place, Alice devrait analyser le parcours du candidat dans son ensemble avant de rédiger un résumé.

Elle devrait notamment prendre en compte :

* les expériences professionnelles ;
* les compétences réellement mises en œuvre ;
* les responsabilités exercées ;
* les réalisations significatives ;
* les technologies maîtrisées ;
* la progression du parcours ;
* les éléments qui rendent le candidat unique.

Le résumé doit être construit autour de ce qui distingue réellement le candidat, plutôt que de s'appuyer sur des formulations génériques.

---

## Mettre le candidat en valeur

L'accroche est l'un des premiers éléments lus par un recruteur. Elle doit donc devenir un véritable outil de différenciation.

L'objectif d'Alice n'est pas simplement de remplir une section du CV, mais de mettre en avant le profil du candidat en racontant son parcours de manière pertinente et crédible.

Chaque génération de contenu doit chercher à répondre à une question simple :

> **Pourquoi ce candidat mérite-t-il davantage l'attention qu'un autre ?**

Toutes les suggestions d'Alice doivent contribuer à répondre à cette question en s'appuyant sur des faits concrets issus du parcours de l'utilisateur, plutôt que sur des formulations passe-partout.
