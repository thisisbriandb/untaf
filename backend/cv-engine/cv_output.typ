// Import the cv-engine design system
#import "@preview/cv-engine:0.1.0": *

// Apply the rendercv template with custom configuration
#show: rendercv.with(
  name: "Jean Dupont",
  title: "Jean Dupont's CV",
  footer: context { [#emph[Jean Dupont -- #str(here().page())\/#str(counter(page).final().first())]] },
  top-note: [ #emph[Dernière mise à jour en Juil. 2026] ],
  locale-catalog-language: "fr",
  text-direction: ltr,
  page-size: "us-letter",
  page-top-margin: 0.7in,
  page-bottom-margin: 0.7in,
  page-left-margin: 0.7in,
  page-right-margin: 0.7in,
  page-show-footer: true,
  page-show-top-note: true,
  colors-body: rgb(0, 0, 0),
  colors-name: rgb(0, 79, 144),
  colors-headline: rgb(0, 79, 144),
  colors-connections: rgb(0, 79, 144),
  colors-section-titles: rgb(0, 79, 144),
  colors-links: rgb(0, 79, 144),
  colors-footer: rgb(128, 128, 128),
  colors-top-note: rgb(128, 128, 128),
  typography-line-spacing: 0.6em,
  typography-alignment: "justified",
  typography-date-and-location-column-alignment: right,
  typography-font-family-body: "Source Sans 3",
  typography-font-family-name: "Source Sans 3",
  typography-font-family-headline: "Source Sans 3",
  typography-font-family-connections: "Source Sans 3",
  typography-font-family-section-titles: "Source Sans 3",
  typography-font-size-body: 10pt,
  typography-font-size-name: 30pt,
  typography-font-size-headline: 10pt,
  typography-font-size-connections: 10pt,
  typography-font-size-section-titles: 1.4em,
  typography-small-caps-name: false,
  typography-small-caps-headline: false,
  typography-small-caps-connections: false,
  typography-small-caps-section-titles: false,
  typography-bold-name: true,
  typography-bold-headline: false,
  typography-bold-connections: false,
  typography-bold-section-titles: true,
  links-underline: false,
  links-show-external-link-icon: false,
  header-alignment: center,
  header-photo-width: 3.5cm,
  header-space-below-name: 0.7cm,
  header-space-below-headline: 0.7cm,
  header-space-below-connections: 0.7cm,
  header-connections-hyperlink: true,
  header-connections-show-icons: true,
  header-connections-display-urls-instead-of-usernames: false,
  header-connections-separator: "",
  header-connections-space-between-connections: 0.5cm,
  section-titles-type: "with_partial_line",
  section-titles-line-thickness: 0.5pt,
  section-titles-space-above: 0.5cm,
  section-titles-space-below: 0.3cm,
  sections-allow-page-break: true,
  sections-space-between-text-based-entries: 0.3em,
  sections-space-between-regular-entries: 1.2em,
  entries-date-and-location-width: 4.15cm,
  entries-side-space: 0.2cm,
  entries-space-between-columns: 0.1cm,
  entries-allow-page-break: false,
  entries-short-second-row: true,
  entries-degree-width: 1cm,
  entries-summary-space-left: 0cm,
  entries-summary-space-above: 0cm,
  entries-highlights-bullet:  "•" ,
  entries-highlights-nested-bullet:  "•" ,
  entries-highlights-space-left: 0.15cm,
  entries-highlights-space-above: 0cm,
  entries-highlights-space-between-items: 0cm,
  entries-highlights-space-between-bullet-and-text: 0.5em,
  date: datetime(
    year: 2026,
    month: 7,
    day: 21,
  ),
)


= Jean Dupont

  #headline([Ingénieur Développeur Full Stack])

#connections(
  [#connection-with-icon("location-dot")[Paris, France]],
  [#link("mailto:jean.dupont@example.com", icon: false, if-underline: false, if-color: false)[#connection-with-icon("envelope")[jean.dupont\@example.com]]],
  [#link("+33 6 12 34 56 78", icon: false, if-underline: false, if-color: false)[#connection-with-icon("phone")[+33 6 12 34 56 78]]],
  [#link("https://jeandupont.dev", icon: false, if-underline: false, if-color: false)[#connection-with-icon("link")[jeandupont.dev]]],
  [#link("https://linkedin.com/in/jeandupont", icon: false, if-underline: false, if-color: false)[#connection-with-icon("linkedin")[jeandupont]]],
  [#link("https://github.com/jeandupont", icon: false, if-underline: false, if-color: false)[#connection-with-icon("github")[jeandupont]]],
)


== Experience

#regular-entry(
  [
    #strong[Tech Solutions], Développeur Lead Backend

    - Conception et développement d'une architecture microservices traitant 1M+ requêtes\/jour

    - Management d'une équipe agile de 6 développeurs

    - Optimisation des requêtes SQL et réduction de la latence API de 45\%

  ],
  [
    Paris, France

    Mars 2022 – présent

    

    4 ans 5 mois

  ],
)

#regular-entry(
  [
    #strong[DataCorp], Développeur #strong[Python] \/ Django

    - Développement d'APIs RESTful sécurisées pour l'intégration de données bancaires

    - Mise en place des pipelines CI\/CD automatisés avec GitLab CI

  ],
  [
    Lyon, France

    Sept. 2019 – Fév. 2022

    

    2 ans 6 mois

  ],
)

== Education

#education-entry(
  [
    #strong[École Nationale Supérieure d'Informatique], Informatique et Systèmes d'Information

    - Mention Très Bien

    - Projet de fin d'études : Traitement automatique du langage naturel (NLP)

  ],
  [
    Paris, France

    Sept. 2014 – Juin 2019

  ],
  degree-column: [
    #strong[Master 2]
  ],
)

== Competences

#strong[Langages:] #strong[Python], #strong[TypeScript], SQL, HTML\/CSS

#strong[Frameworks:] #strong[FastAPI], NestJS, React, Django

#strong[Outils & DevOps:] #strong[Docker], Kubernetes, Git, PostgreSQL, Redis

== Langues

- Français (Langue maternelle)

- Anglais (Professionnel courant - C1)
