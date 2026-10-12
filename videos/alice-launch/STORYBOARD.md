---
format: 1080x1920
duration: 32s
message: "Alice trouve les offres, adapte ton CV et postule pour toi."
arc: PAS — hook → pain → product intro → demo (ask → work → result) → value stack → CTA
audience: "Étudiants et jeunes diplômés en France qui cherchent une alternance, un stage ou un premier emploi"
mode: autonomous
music: none
---

This video tells students and young graduates in France that Alice finds the offers, tailors their CV and applies for them.
No narration: on-screen kinetic type carries every line (the `voiceover` field is the on-screen copy and its reveal cadence). Music bed and sound design are host-made (`audio_meta.json`, `source: host`).

## Video direction

- **palette system** (`frame.md`): canvas `bg` #FAFAF8 warm off-white is the ground of every frame; `text` #1A1918 for all display type; `primary` #006045 is the ONLY accent — Alice's eyes, key words, check marks, the CTA pill, counters; `card-bg` / `border` green tints for card chrome. Frame 7 is the one exception: the field flips to solid `primary` with `bg`-coloured type (the energy peak). Pain frames (1–2) stay desaturated — ink + `text-light` grey, no green at all until Alice appears in frame 3: green = Alice.
- **type**: display = `h1` ramp (Geist 700, tracking -0.02em) pushed to poster scale for kinetic beats; body/meta = `body` / `tag`. Sentence case, French typography (non-breaking space before ? and %).
- **phone surface**: the real app screenshots (1170×2532, mobile @3x) sit inside ONE consistent floating phone card — rounded ~64px corners, thin `border` stroke, soft long shadow, ~76% of frame width, centered horizontally, occupying roughly 22%–82% of frame height — the same object in frames 4, 5 and 6 so the demo reads as one continuous device. Animate the screenshot by masking its regions (clip/inset reveals of the real pixels, region coordinates given per frame in screenshot pixels); rebuild ONLY the one component that must move (typed text, a counter, a check badge), matched to the screenshot's look (Geist/system sans, same colours).
- **captions above the phone**: frames 4–6 carry a short headline in the band 9%–20% of frame height, centered, ink `h2`-scale, key words in `primary`.
- **motion grammar**: long-tail `power3` / `expo.out` settles; no bounce, no elastic; kinetic beats use hard cuts and motion-blur fly-ins. Reveal each on-screen line on its cue (the `voiceover` copy IS the on-screen text); nothing front-loaded. Holds: subtle jitter at most.
- **rhythm**: fast (1–2) → breath + reveal (3) → steady demo pulse (4–6) → staccato peak (7) → calm held end card (8). Held reads: end of frame 3 (the promise lands still) and the back half of frame 8 (dead-still CTA).
- **sound**: host-made music bed (low-passed under frames 1–2, opening to full at the frame-3 reveal) + SFX cues per frame (`sfx:`), all mounted at root from `audio_meta.json` — frames embed no audio.
- **negative list**: no purple/blue AI gradients, no bokeh, no stock icons, no emoji, no browser chrome, no cursor; no slideshow front-loading; no screensaver drift; no lazy breathing; nothing important in the bottom 17% band (social UI) or the top 7%.

## Frame 1 — Lettre n°47

- scene: A cover letter types itself — "Madame, Monsieur," — the counter reads "Candidature n°47", the line backspaces and retypes, exhausted
- voiceover: "Candidature n°47. — Madame, Monsieur,"
- duration: 3.5s
- transition_in: cut
- status: animated
- src: compositions/frames/01-lettre-47.html
- type: hook
- persuasion: Pain validation
- beat: frustration
- blueprint: typewriter-reveal (Adapt)
- asset_candidates:
- focal: (typography only)
- sfx: keyboard-typing, backspace-ticks, low-thud

narrativeRole: open on the everyday ritual every job seeker recognises — the 47th identical letter.
keyMessage: tu connais ça.

Adapt: keep the type-on + backspace-retype signature; no brand pop at the end (the brand is saved for frame 3) — the line stalls instead, handing the frustration to frame 2.
Scene 1 (0.0–0.6s): bare `bg` field; a grey counter "Candidature n°46" in `counter`/`tag` style (scaled up for 1080 wide, ~34px) sits at ~30% height, left-aligned to the text column; a blinking caret appears at ~45% height, left margin ~12%. Rule-of-thirds, typography only.
Scene 2 (0.6–1.9s): "Madame, Monsieur," types character by character, ink, ~110px Geist 600, caret trailing; the counter hard-cuts 46→47 on the first keystroke.
Scene 3 (1.9–2.8s): the line backspaces fully (fast), caret blinks twice, then retypes "Madame, Monsieur," slower — the tiredness is the joke.
Scene 4 (2.8–3.5s): hold on the retyped line with the caret blinking; a faint grey ghost stack of identical "Madame, Monsieur," lines (5–6 copies, opacity 0.06→0.15, offset upward) fades up behind — the 46 before. Held read.

## Frame 2 — Zéro réponse

- scene: Pain lines land solo on a bare canvas, one per beat, then a giant "0 réponse." slams in and holds
- voiceover: "Un CV à refaire. — Une lettre à réécrire. — Un formulaire de plus. — 0 réponse."
- duration: 4s
- transition_in: cut
- status: animated
- src: compositions/frames/02-zero-reponse.html
- type: pain_point
- persuasion: Pain agitation
- beat: frustration + overwhelm
- blueprint: kinetic-type-beats (Reproduce — Problem variant)
- asset_candidates:
- focal: (typography only)
- sfx: whoosh-short ×3, impact-heavy

narrativeRole: agitate — the work is endless and it goes nowhere.
keyMessage: postuler est un travail à plein temps, et il ne paie pas.

Scene 1 (0.0–0.8s): "Un CV à refaire." motion-blur flies in from the right and resolves sharp at center (~45% height), ink, ~120px Geist 700, max 2 lines; a grey strike-through draws across "à refaire".
Scene 2 (0.8–1.6s): the previous line zooms past camera and blurs out as "Une lettre à réécrire." flies in from the left, same treatment.
Scene 3 (1.6–2.4s): "Un formulaire de plus." flies in from below and lands.
Scene 4 (2.4–4.0s): hard cut to the slam: a giant "0" (poster scale, ~40% of frame height) crashes in, scaling down from oversized to rest at ~40% height; "réponse." snaps in beneath it at ~120px; one short low-amplitude jitter on impact, then dead-still hold. All ink/grey — no green.

## Frame 3 — Alice arrive

- scene: The canvas clears; Alice's two eyes draw on and blink; the wordmark "Alice" lands; the tagline assembles verb by verb — "Elle cherche. Elle adapte. Elle postule."
- voiceover: "Et si quelqu'un le faisait pour toi ? — Alice. — Elle cherche. Elle adapte. Elle postule."
- duration: 4s
- transition_in: zoom-through
- status: animated
- src: compositions/frames/03-alice-arrive.html
- type: product_intro
- persuasion: Negative contrast → relief
- beat: curiosity → relief
- blueprint: logo-assemble-lockup (Adapt — Product_Intro parts-assembly)
- asset_candidates: assets/alice-eyes.svg — Alice logo, two green rings
- focal: assets/alice-eyes.svg
- roles: alice-eyes = cutout (rebuilt inline as two SVG ring strokes in `primary`, without the disc)
- sfx: riser-soft (ends at 1.2s), shimmer, pop ×3 (verbs)

narrativeRole: the turn — name the product and land the promise (message) right after the pain.
keyMessage: Alice fait les candidatures à ta place.

Adapt: keep the parts-assemble signature (the mark builds from parts — here, the two eyes); one question line precedes it.
Scene 1 (0.0–1.2s): "Et si quelqu'un le faisait pour toi ?" words land staggered at center (~45% height) in ink ~84px Geist 600, max 3 lines; holds; then shrinks toward center and fades.
Scene 2 (1.2–2.0s): on the empty `bg`, a soft `accent-light` radial glow ignites at center; the two eye rings self-draw clockwise in `primary` (stroke ~22px, ring Ø ~150px, gap ~90px), then blink once (vertical squash of both rings, smooth).
Scene 3 (2.0–2.8s): the eyes rise to ~32% height as the wordmark "Alice" unmasks beneath them (~260px Geist 700, ink, tracking -0.03em).
Scene 4 (2.8–4.0s): the tagline builds beneath the wordmark, one verb phrase per beat: "Elle cherche." · "Elle adapte." · "Elle postule." (stacked lines, ~72px, verbs in `primary`); then the full lockup holds still.

## Frame 4 — Tu demandes

- scene: The real Alice chat on the floating phone: the ask types into the user bubble, sends, Alice replies and the offer cards cascade in with their match scores (94 %, 91 %, 88 %…)
- voiceover: "Tu lui dis ce que tu cherches. — Elle trouve les offres qui te correspondent."
- duration: 4.5s
- transition_in: crossfade
- status: animated
- src: compositions/frames/04-tu-demandes.html
- type: feature_showcase
- persuasion: Show-don't-tell proof
- beat: curiosity + ease
- blueprint: prompt-type-submit-generate (Adapt — sub-shape C instant-result surface)
- asset_candidates: assets/chat-offers.png — real chat: the ask, Alice's reply and scored offer cards
- focal: assets/chat-offers.png
- roles: chat-offers = cutout (inside the floating phone card)
- sfx: whoosh-up (phone in), keyboard-typing, send-click, pop ×4 (cards)

narrativeRole: demo step 1 — one sentence in, a ranked list out.
keyMessage: une phrase suffit.

Screenshot regions (chat-offers.png, 1170×2532 px): header 0–230; user bubble ≈ y 390–590 (x 260–1110); Alice reply text ≈ y 610–900; offer card 1 ≈ y 950–1205; card 2 ≈ 1245–1500; card 3 ≈ 1540–1790; card 4 ≈ 1830–2090; composer ≈ 2290–2470.
Adapt: keep "the ask types live, the answer arrives progressively"; the surface is the real screenshot revealed region by region (masks), with the bubble's text rebuilt so it can type (cover the screenshot's bubble text with a bubble-coloured patch #EEEDEA-ish sampled from the bubble, type the rebuilt text on it).
Scene 1 (0.0–0.8s): the phone card rises from below into place (long-tail settle); only the header region shows (rest masked to the screen's `bg`); caption "Tu lui dis ce que tu cherches." per-word above the phone.
Scene 2 (0.8–2.0s): the user bubble appears and "Trouve-moi une alternance en marketing digital à Lyon" types inside it, caret trailing; a small press on completion (send).
Scene 3 (2.0–3.6s): Alice's reply region reveals (mask wipe top→down), then cards 1–4 reveal one by one (each its masked strip, slide-up ~24px + fade), each card's score catching a brief `primary` glow as it lands; the caption swaps to "Elle trouve les offres qui te correspondent." with "te correspondent" in `primary`.
Scene 4 (3.6–4.5s): hold on the complete list; subtle jitter only.

## Frame 5 — Elle travaille

- scene: The live mission card from the real app; a big counter runs to "1 284 offres passées en revue", then rows land and check off: CV adapté, lettre rédigée, candidature envoyée
- voiceover: "1 284 offres passées en revue. — CV adapté. — Lettre rédigée. — Candidature envoyée."
- duration: 5s
- transition_in: push-slide UP
- status: animated
- src: compositions/frames/05-elle-travaille.html
- type: feature_showcase
- persuasion: Statistical proof + show-don't-tell
- beat: awe + control
- blueprint: agent-progress-theater (Adapt — checklist sub-shape A)
- asset_candidates: assets/chat-top.png — real live mission card: offers reviewed, CV adapted, letter written, application sent
- focal: assets/chat-top.png
- roles: chat-top = cutout (same floating phone card, framed on the mission card)
- sfx: counter-ticks, check-pop ×3, success-chime

narrativeRole: demo step 2 — the machine visibly does the work the viewer hated in frame 2.
keyMessage: tout ce que tu faisais à la main, Alice le fait.

Screenshot regions (chat-top.png, 1170×2532 px): mission card ≈ y 1295–2255 (x 50–1120): header line ≈ 1320–1420; row "J'ai passé 1 284 offres…" ≈ 1440–1580; row "Retenue … Decathlon — 94 %" ≈ 1610–1750; row "CV adapté pour Decathlon…" ≈ 1775–1915; row "Lettre de motivation rédigée…" ≈ 1950–2010; row "Candidature envoyée à Decathlon…" ≈ 2040–2160.
Adapt: keep trigger → working → receipt with check-state flips; the receipt rows are the real rows (masked strips revealed in order); the counter and the check badges are rebuilt.
Scene 1 (0.0–1.6s): the phone shows chat-top.png positioned so the mission card fills the phone screen (scale the screenshot up ~1.25× inside the phone, framed on y ≈ 1250–2300), card header + first row visible; in the caption band a rebuilt counter counts 0 → "1 284" in `primary` Geist 700 (~150px, tabular-nums), with "offres passées en revue" in ink beneath (~48px).
Scene 2 (1.6–2.6s): row "CV adapté…" reveals (masked strip slide-up); a rebuilt `primary` check badge (Ø ~44px, white tick) pops over the row's bullet; the caption swaps to "CV adapté." (counter clears up).
Scene 3 (2.6–3.6s): row "Lettre… rédigée" reveals + check pops; caption "Lettre rédigée."
Scene 4 (3.6–5.0s): row "Candidature envoyée…" reveals + check pops with a soft `primary` glow bloom; caption "Candidature envoyée." with "envoyée" in `primary`; hold.

## Frame 6 — Envoyées

- scene: The real Candidatures screen; "Envoyée" badges pop one after another, score rings fill; a line slides in: "Pendant que tu vis ta vie."
- voiceover: "Tes candidatures partent. — Pendant que tu vis ta vie."
- duration: 4s
- transition_in: push-slide UP
- status: animated
- src: compositions/frames/06-envoyees.html
- type: benefit_highlight
- persuasion: Feature-to-benefit translation
- beat: relief + peace of mind
- blueprint: device-surface-showcase (Adapt — static-tour)
- asset_candidates: assets/candidatures.png — real Candidatures tab: sent applications, ready packs, score rings
- focal: assets/candidatures.png
- roles: candidatures = cutout (same floating phone card)
- sfx: swipe, pop ×2 (badges), soft-whoosh

narrativeRole: demo step 3 — the result, and what it gives back: time.
keyMessage: les candidatures partent sans toi.

Screenshot regions (candidatures.png, 1170×2532 px): header + title ≈ 0–420; filter pills ≈ 470–560; row Decathlon (score ring 94, badge "Envoyée") ≈ 610–960; row SEB (91, "Envoyée") ≈ 1000–1360; row Boiron (88, "Pack prêt") ≈ 1390–1690; row Cegid ≈ 1700–2000; row OL ≈ 2010–2300. "Envoyée" badges sit at ≈ x 1100–1240 (right edge), y ≈ 690 and 1075.
Adapt: keep the static tour (device holds, UI advances, headline swaps); one screen whose rows advance by masked reveals and badge pops.
Scene 1 (0.0–1.0s): inside the phone the Candidatures screen pulls up (old content pushes up, new pulls up); header + filters visible; caption "Tes candidatures partent." per-word above.
Scene 2 (1.0–2.4s): rows reveal top→down; on the two "Envoyée" rows a rebuilt `primary`-tinted "Envoyée" pill pops over the screenshot's badge, and an SVG ring sweeps around the 94 and 91 score rings.
Scene 3 (2.4–4.0s): the caption swaps (out-up / in-up) to "Pendant que tu vis ta vie." — "ta vie" in `primary`; hold.

## Frame 7 — Alice s'en charge

- scene: Staccato value barrage on the brand green: "Les offres." "Le CV." "La lettre." "L'envoi." "Les relances." flashing at center, resolving on "Alice s'en charge."
- voiceover: "Les offres. — Le CV. — La lettre. — L'envoi. — Les relances. — Alice s'en charge."
- duration: 3.5s
- transition_in: zoom-through
- status: animated
- src: compositions/frames/07-alice-s-en-charge.html
- type: benefit_highlight
- persuasion: Value stacking
- beat: power + excitement
- blueprint: kinetic-type-beats (Reproduce — Benefits variant, high tempo)
- asset_candidates:
- focal: (typography only)
- sfx: tick ×5 on the beat, impact-bright

narrativeRole: compress the whole promise into one breath before the ask.
keyMessage: tout le parcours, de l'offre à la relance.

Scene 1 (0.0–2.4s): full-bleed `primary` field; `bg`-coloured type at center (~44% height), ~170px Geist 700; "Les offres." · "Le CV." · "La lettre." · "L'envoi." · "Les relances." hard-cut in place every ~0.45s, each with its own micro-entrance (scale-down from oversized, motion-blur from left, letter-spacing collapse, rise from below, scale-down) — the swap is the beat.
Scene 2 (2.4–3.5s): "Alice s'en charge." lands on two lines (~150px), with the two eye rings (stroke in `bg` colour) dotting in above "Alice"; hold still.

## Frame 8 — alice-agent.fr

- scene: The eyes return and blink; the CTA pill "alice-agent.fr" condenses out of them and presses; "Gratuit pour commencer" settles beneath and holds
- voiceover: "Ta prochaine candidature, c'est Alice qui l'envoie. — alice-agent.fr — Gratuit pour commencer."
- duration: 4s
- transition_in: crossfade
- status: animated
- src: compositions/frames/08-cta.html
- type: cta
- persuasion: Risk reversal
- beat: motivation + urgency-to-act
- blueprint: cta-morph-press (Adapt)
- asset_candidates: assets/alice-eyes.svg — Alice logo
- focal: assets/alice-eyes.svg
- roles: alice-eyes = cutout (two rings, as in frame 3)
- sfx: pop, click, shimmer-tail

narrativeRole: the ask — where to go, and that it costs nothing to try.
keyMessage: va sur alice-agent.fr, c'est gratuit pour commencer.

Adapt: keep the same-center morph signature (the eyes condense into the CTA pill); no cursor — the pill presses itself (lockstep compression) on the beat.
Scene 1 (0.0–1.2s): `bg` field; the eyes (as frame 3) blink at ~34% height; "Ta prochaine candidature, c'est Alice qui l'envoie." builds word-staggered beneath in ink ~72px, max 3 lines.
Scene 2 (1.2–2.2s): the line clears; the eyes condense at the same center into a solid `primary` CTA pill "alice-agent.fr" (`bg`-coloured Geist 600, ~96px, pill padding generous, ~80% frame width) at ~46% height — shrink-fade ↔ scale-up sharing one origin; the eyes re-form small above the pill.
Scene 3 (2.2–2.8s): the pill presses (compress to ~0.96 + release) with one soft `primary` glow ring blooming outward.
Scene 4 (2.8–4.0s): "Gratuit pour commencer" fades up under the pill (ink at 60% opacity, ~52px); dead-still hold to the end.
