# Délégation de missions à Alice

La délégation de missions doit devenir une fonctionnalité centrale de l'application. L'objectif est que l'utilisateur ait réellement le sentiment de confier une mission à un agent autonome plutôt que d'utiliser un simple chatbot.

Cette fonctionnalité doit être intégrée naturellement dans l'interface d'Alice afin de renforcer la promesse principale du produit : **déléguer sa recherche d'emploi à un agent IA**.

---

# Déclencher une mission

Depuis l'interface de conversation, l'utilisateur doit pouvoir demander à Alice d'effectuer une mission.

Cette interaction peut prendre la forme d'un pop-up ou d'un assistant conversationnel dans lequel Alice guide l'utilisateur en lui posant quelques questions.

Par exemple :

* « Quelle mission souhaites-tu me confier ? »
* « Pendant combien de temps souhaites-tu que je travaille dessus ? »
* « Souhaites-tu que je postule automatiquement ou que je te présente uniquement les meilleures opportunités ? »

L'objectif est de rendre la délégation simple, naturelle et conversationnelle.

---

# Définir le périmètre de la mission

Une mission peut être caractérisée par plusieurs paramètres :

* son objectif (rechercher des offres, postuler, préparer des candidatures, etc.) ;
* sa durée d'exécution (par exemple 30 minutes, 2 heures ou une demi-journée) ;
* les actions autorisées par l'utilisateur ;
* les critères de recherche (métier, localisation, type de contrat, salaire, télétravail, etc.).

Une fois ces paramètres définis, Alice confirme la mission avant de la lancer.

---

# Exécution de la mission

Pendant toute la durée définie, Alice exécute les actions qui lui ont été confiées.

Selon les autorisations accordées, elle peut notamment :

* rechercher des offres d'emploi sur différentes plateformes ;
* analyser leur pertinence par rapport au profil du candidat ;
* adapter le CV et la lettre de motivation si nécessaire ;
* préparer les candidatures ;
* envoyer les candidatures lorsque cela est autorisé ;
* enregistrer toutes les actions réalisées.

L'objectif est que l'utilisateur puisse quitter l'application pendant qu'Alice poursuit son travail de manière autonome.

---

# Visualiser une mission en cours

Une mission active doit être visible directement dans l'interface.

L'utilisateur doit pouvoir consulter :

* le nom de la mission ;
* son état (en préparation, en cours, terminée ou interrompue) ;
* le temps restant avant sa fin ;
* la progression des actions réalisées.

Une représentation visuelle, comme un compte à rebours ou une barre de progression, permet de matérialiser le travail effectué par Alice et de rendre l'expérience plus vivante.

---

# Consulter le résumé d'une mission

À tout moment, l'utilisateur doit pouvoir ouvrir une mission pour consulter son activité.

Alice présente alors un résumé des actions réalisées, par exemple :

* nombre d'offres analysées ;
* nombre d'offres retenues ;
* candidatures envoyées ;
* entreprises contactées ;
* documents générés ou adaptés ;
* éventuels points nécessitant une validation.

Ce résumé doit être rédigé par Alice dans un style conversationnel, comme un véritable compte rendu de mission.

---

# Une expérience immersive

L'expérience doit donner le sentiment qu'Alice travaille réellement pendant toute la durée de la mission.

Les animations, les transitions et les retours d'état doivent renforcer cette impression, sans surcharger l'interface.

L'utilisateur doit percevoir qu'Alice est en train d'effectuer un travail concret en arrière-plan, et non simplement attendre la fin d'un traitement technique.

---

# Pipeline d'automatisation des candidatures

Cette fonctionnalité repose sur une pipeline capable d'exécuter les différentes étapes d'une candidature.

À terme, cette pipeline pourra notamment :

* détecter de nouvelles offres pertinentes ;
* analyser les critères de chaque annonce ;
* sélectionner les candidatures les plus adaptées ;
* préparer les documents nécessaires ;
* compléter automatiquement les formulaires lorsque cela est possible ;
* envoyer des candidatures par e-mail ou via les plateformes compatibles, conformément aux autorisations accordées par l'utilisateur ;
* enregistrer un historique détaillé de chaque action effectuée.

Dans un premier temps, il est possible de mettre en place une version simulée de cette pipeline afin de valider l'expérience utilisateur et les interactions avec Alice avant d'intégrer progressivement les automatisations réelles.

---

# Objectif produit

Cette fonctionnalité doit matérialiser la promesse principale de l'application.

L'utilisateur ne vient plus seulement discuter avec une IA : il lui confie une mission, Alice travaille de manière autonome pendant une période donnée, puis elle revient avec un compte rendu détaillé des actions réalisées.

C'est cette capacité à exécuter des missions et à rendre des comptes qui différencie Alice d'un assistant conversationnel classique et renforce sa position d'agent IA dédié à la recherche d'emploi.
