# Module d'emailing

Le module d'emailing constitue une brique essentielle de l'écosystème d'Alice. Son objectif est de permettre à l'agent de communiquer avec l'utilisateur, de l'informer des actions réalisées et, lorsque celui-ci l'autorise, d'envoyer des candidatures directement depuis son adresse e-mail.

L'ensemble du fonctionnement doit reposer sur un principe fondamental : **aucune action n'est réalisée sans le consentement explicite de l'utilisateur**.

---

# Authentification et autorisations

Afin qu'Alice puisse envoyer des e-mails au nom du candidat, l'utilisateur doit pouvoir connecter son adresse e-mail à l'application.

Cette connexion permettra, après autorisation explicite, de donner à Alice la capacité :

* d'envoyer des candidatures ;
* d'envoyer des lettres de motivation ;
* de transmettre les CV générés ;
* de répondre automatiquement à certaines offres lorsque cela est demandé.

Les autorisations doivent être clairement présentées afin que l'utilisateur sache précisément quelles actions Alice est autorisée à effectuer.

L'utilisateur doit pouvoir retirer ces autorisations à tout moment depuis les paramètres de l'application.

---

# Candidatures par e-mail

Certaines offres d'emploi demandent explicitement de postuler par e-mail et indiquent une adresse de contact.

Lorsque la pipeline d'Alice détecte ce type d'offre, elle peut :

* identifier l'adresse de candidature ;
* préparer les documents nécessaires ;
* générer un e-mail adapté ;
* joindre le CV et la lettre de motivation ;
* envoyer la candidature depuis l'adresse e-mail du candidat, si celui-ci a accordé les autorisations nécessaires.

Cette automatisation permet de couvrir également les offres qui ne disposent pas d'un formulaire de candidature classique.

---

# Notifications des actions réalisées

L'utilisateur doit être régulièrement informé des actions effectuées par Alice.

Ces notifications peuvent notamment concerner :

* une candidature envoyée ;
* une nouvelle offre correspondant à son profil ;
* la génération d'un nouveau CV ;
* la création d'une lettre de motivation ;
* la détection de nouvelles opportunités ;
* la fin d'une mission confiée à Alice.

L'objectif est que l'utilisateur sache en permanence ce qu'Alice a fait en son nom.

---

# Rapports d'activité

Alice pourrait générer automatiquement des comptes rendus synthétiques des actions réalisées.

Ces rapports peuvent être envoyés périodiquement (quotidiennement, hebdomadairement ou selon les préférences de l'utilisateur) et contenir, par exemple :

* les offres analysées ;
* les candidatures envoyées ;
* les entreprises contactées ;
* les documents générés ;
* les éventuelles réponses reçues ;
* les prochaines actions prévues.

Selon les besoins, ces rapports pourraient également être disponibles au format PDF afin que l'utilisateur conserve un historique de son activité.

---

# Notifications intelligentes

Le module d'emailing ne doit pas uniquement servir aux candidatures.

Il constitue également un moyen pour Alice de communiquer avec l'utilisateur lorsqu'un événement important survient.

Par exemple :

* Alice a terminé l'analyse d'un nouveau CV ;
* de nouvelles offres pertinentes ont été identifiées ;
* une mission demandée par l'utilisateur est terminée ;
* une candidature nécessite une validation ;
* une action ne peut pas être réalisée en raison d'une autorisation manquante.

Les e-mails doivent être utiles, contextualisés et éviter les notifications inutiles.

---

# Intégration avec le comportement d'Alice

Le module d'emailing doit être entièrement intégré au fonctionnement de l'agent.

Lorsqu'Alice réalise une action importante, elle doit pouvoir décider, selon le contexte et les préférences de l'utilisateur, s'il est pertinent d'envoyer une notification ou non.

L'objectif est que l'utilisateur ait réellement l'impression de collaborer avec un agent autonome qui agit, prend des initiatives dans le cadre des autorisations accordées et rend compte de son travail de manière transparente.

Cette communication régulière renforce la confiance et matérialise la promesse centrale du produit : permettre à l'utilisateur de déléguer une partie de sa recherche d'emploi tout en restant informé des actions réalisées en son nom.
