---
workflow: motion-graphics
flow: automation
storyboard: no
message: "L'extension Alice arrive : postule avec ton propre compte, en un clic, sans jamais donner tes identifiants."
destination: instagram-reels
aspect: 1080x1920
language: fr
length: 12s
---

## Intent

Teaser « coming soon » de l'extension navigateur d'Alice (alice-agent.fr). L'extension
tourne dans le navigateur de l'utilisateur, avec sa propre session sur ses sites
d'emploi : sur une offre, elle remplit la candidature avec le dossier préparé par
Alice (CV adapté, lettre, réponses), l'utilisateur relit et clique sur Envoyer.
Argument clé : « tes identifiants ne quittent jamais ton ordinateur ».
Ton : premium, mystérieux puis évident ; même identité que la vidéo de lancement.

## Assets

- assets/brand/alice-eyes.svg — logo d'Alice (deux anneaux verts, les yeux).
- frame.md — design system (fond #FAFAF8, encre #1A1918, unique accent #006045, Geist).

## Notes

- Ne PAS afficher de logos ni d'interfaces de marques tierces (LinkedIn, Indeed…) :
  une fenêtre de navigateur et une page d'offre génériques, stylisées.
- Ne pas promettre de date. « Bientôt » / « Coming soon ».
- Polices et GSAP en local (assets/fonts, assets/vendor/gsap.min.js) : le
  navigateur de rendu n'a pas d'accès réseau.
- Pas de voix off. Son ajouté ensuite par l'orchestrateur (musique + effets).
