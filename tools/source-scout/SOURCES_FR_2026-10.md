# French job / alternance sources: where Alice can discover and apply (Oct 2026)

Checked on 2026-10-17 from the dev container. What was checked for each source: robots.txt
(fetched with the AliceBot UA), Content-Signal, X-Robots-Tag, terms or legal notice
(a keyword grep plus a reading of the matching clauses), public feeds and APIs, and the
apply flow on one real offer.

The apply flow was opened in headless Chromium using a throwaway script (not kept in the
repo), which works like `tools/agent-bench/probe.mjs` but never fills a field. Every non-GET request was
aborted, with two exceptions:
- the Talentsoft "Je postule" ASP.NET postback, which only navigates to the form;
- Ashby's read-only GraphQL query, which loads the form.

No form was submitted, no account was created, and no captcha or bot wall was bypassed.
When a site returned 403, a challenge page or a 429, I recorded it and stopped.

Legend:
- **GO**: Alice can apply on its own (email, or a form with no password and no captcha seen).
- **extension-only**: the candidate's own browser and click (because of a captcha, an
  account or SSO).
- **exclude**: the terms, Content-Signal or robots.txt forbid it, or the site blocks access.

## Ranked table

| # | Source | Type | Volume FR (seen) | Discovery allowed? | Apply without password? | Captcha | Verdict | Reason |
|---|---|---|---|---|---|---|---|---|
| 1 | **Choisir le service public** (choisirleservicepublic.gouv.fr) | public platform | ~54,300 offers (listing page) | **Yes.** Robots allows offer pages, there is a sitemap index, and the site says "textes sous licence etalab-2.0" | **Yes, for part of the offers:** "Postuler par mail" is a `mailto:` link to the recruiter. Others say "Postuler sur le site employeur" | none | **GO** | Open licence, plus email apply on 3 of the 6 offers sampled. The site's own account is not needed for mail offers |
| 2 | **Werecruit** (careers.werecruit.io) | ATS | 20,306 offer URLs in the sitemap, 7,831 with lastmod Oct 2026 | Yes: `Allow: /` and a sitemap. No restrictive clause in the legal notice | Yes: inline form (civilité, nom, prénom, e-mail, tél, CV) that posts multipart to the offer URL | none seen | **GO** | Biggest ATS-side open pool found |
| 3 | **Taleez** | ATS | 12,006 URLs in `sitemap-job.xml` | Yes (`#Allow AI crawlers`; only `/api/` and `/pics/applys/` are disallowed) | Yes | none | **GO (already integrated)** | Kept for reference |
| 4 | **Jobaffinity** (HelloWork's ATS) | ATS | n/a (no global feed found) | Partial: robots blocks only Bytespider. No sitemap; offers are found from employer pages that link to `jobaffinity.fr/apply/<id>` | Yes. Earlier probe marked it "rejouable": CV goes to `/newcandidate/upload_async`, then a multipart POST with `x-requested-with` | none | **GO (apply)** | HelloWork's CGU covers hellowork.com, not jobaffinity.fr. Discovery has to come from other legitimate sources |
| 5 | **Personio** (`*.jobs.personio.com`) | ATS | moderate (mostly DACH; FR tenants exist) | Yes: `Allow: /` and a public XML feed at `https://{slug}.jobs.personio.com/xml?language=fr` | Yes. Fields: Prénom, Nom, E-mail*, Téléphone, Disponible à partir du*, Rémunération, CV | none seen | **GO** | |
| 6 | **Breezy HR** (`*.breezy.hr`) | ATS | small to moderate (FR scale-ups such as Betclic) | Yes: robots blocks only asset folders. Public JSON at `https://{slug}.breezy.hr/json` | Yes: form at `/p/<id>/apply`, with a CV upload and a privacy checkbox. Some tenants add a Ziggeo video step | none seen | **GO** | |
| 7 | **Cegid Talentsoft** (`*-career.talent-soft.com` and custom domains) | ATS | hundreds of FR tenants. CEA alone: 799 offers; Pasteur 22; KPMG (BE) 86 | Yes: robots.txt is empty and there is a public RSS feed at `/handlers/offerRss.ashx?LCID=1036`. No clause found in Framatome's legal notice | **Depends on the tenant.** Email-only, then an account is created automatically: Framatome, KPMG (BE). Email **and password** required: CEA, Institut Pasteur | none | **GO for email-only tenants**, extension-only for the rest | A per-tenant flag is needed. I could not find Bpifrance or Vinci Energies on talent-soft.com (guessed hosts do not resolve) |
| 8 | **DigitalRecruiters** (Cegid; custom domains such as nosoffres.burgerking.fr, recrutement.cnes.fr) | ATS | large FR base (no global count) | Yes: `Allow: /`, `Crawl-delay: 10` | Yes: "Postuler" opens a GDPR consent step, then "Importez votre CV / Remplir manuellement / LinkedIn". No account | none seen, though I stopped before the field-filling step | **GO (browser)** | No global feed found. Tenants have to be discovered one by one |
| 9 | **Flatchr** (careers.flatchr.io) | ATS | n/a | Robots blocks only some named bots. No public offer feed (the sitemap only lists the marketing site) | Yes: form at `/vacancy/<id>/apply/` with CV and cover letter | none seen | **GO (apply)**, discovery limited | |
| 10 | **Beetween** (`*.nous-recrutons.fr`) | ATS | n/a | Yes: WordPress robots and a sitemap | The form has a **captcha**. But offers posted to job boards carry an email relay `job-ref-…@emploi.beetween.com` (seen on Choisir le service public) | captcha on the form | **GO via email relay only**, form = extension | Use the relay address only when a legitimate source (CSP, France Travail) publishes it |
| 11 | France Travail API / La bonne alternance | public | very large | Yes (official API) | n/a | n/a | **GO (already integrated)** | 1jeune1solution republishes the same data. Use the APIs, not 1j1s, whose CGU forbids robots |
| 12 | Ashby | ATS | FR boards exist (Alan: 89 of 125 offers in France) | Yes, through the public `api.ashbyhq.com/posting-api/job-board/{slug}` (scraper already exists) | Form without password (Name, Email, Phone, Resume, questions) | none seen | **extension-only (apply)**, GO discovery | The form loads and submits through `jobs.ashbyhq.com/api/…`, which **robots.txt disallows** |
| 13 | Greenhouse | ATS | e.g. Doctolib 62 FR, Mirakl 27 FR | Yes: `boards-api.greenhouse.io` is public (scraper exists) and robots allows | No password | **reCAPTCHA Enterprise** on the form | **extension-only** | |
| 14 | Lever | ATS | e.g. Qonto 32 FR, Swile 16 FR | Yes: `api.lever.co/v0/postings/{slug}` (scraper exists), robots `Allow: /` | No password | **hCaptcha** on `/apply` | **extension-only** | |
| 15 | SmartRecruiters | ATS | e.g. Ubisoft 42 FR, URGO 18 FR | Mixed: the Posting API (`api.smartrecruiters.com/v1/companies/{id}/postings`) is public and documented, but **robots.txt on api.smartrecruiters.com says `Disallow: /`** | "Je suis intéressé(e)" goes to `oneclick-ui` | **DataDome captcha interstitial** | **extension-only** | |
| 16 | Workday (`*.myworkdayjobs.com`) | ATS | big companies (Sanofi: 6 "alternance" hits) | Yes: robots allows `/{site}/`, there is a `siteMap.xml`, and the cxs JSON search endpoint works | **No:** step 1 of 5 is "Créer un compte" (e-mail, mot de passe, confirmation), checked on Sanofi | none seen | **extension-only** | |
| 17 | JOIN (join.com) | ATS | n/a | Sitemaps are listed, but `sitemap-jobs-index.xml` returned 403. Terms forbid "data mining" (company side) | Email authentication step | captcha (earlier probe) | **extension-only** | |
| 18 | Softy (`*.softy.pro`) | ATS | small (Inserm, MSA) | robots `Allow: /` for `*`, but **blocks GPTBot, ChatGPT-User, Claude-Web, anthropic-ai, CCBot…** | CV upload, no account | none seen | **extension-only** | Explicit anti-AI-agent signal, so no automated collection |
| 19 | SAP SuccessFactors | ATS | big companies | jobs.sap.com: robots `Allow: /`, but the homepage returned **403 / challenge** | **not verified.** I found no FR tenant to test; usually account + password | n/a | **extension-only (presumed)** | Unverified |
| 20 | Workable | ATS | n/a | **429 / Cloudflare 1015** from this egress, even for robots.txt | not verified | n/a | **unknown (blocked here)** | A scraper already exists; recheck from production egress |
| 21 | Teamtailor | ATS | n/a | **Content-Signal: search=no, ai-train=no, ai-input=no** | form | – | **exclude** | Confirmed on swile.teamtailor.com |
| 22 | Service civique (service-civique.gouv.fr) | public | many missions | Robots allows everything, sitemap exists, CGU has no anti-robot clause. The legal notice asks for permission before reproducing content | **No:** "JE POSTULE" leads to login or account creation with a password | none | **extension-only** | Discovery for matching is probably fine; ask the Agence about reuse |
| 23 | StudentJob | platform | n/a | robots disallows `/vacancies*` and `/candidat*` (offers are under `/offre/`) | **No:** email and password login on the offer page (with a honeypot field) | none | **extension-only** | |
| 24 | Meteojob | platform | n/a | robots disallows `/postuler/…`, `/jobs/apply/auto-signup` and `/candidate-application/…`. CGU not found | Email field, then an account is created automatically | **Cloudflare Turnstile** | **extension-only / exclude** | |
| 25 | JobTeaser | platform | large (school-linked) | robots disallows `*/apply_to_extern_url` | School account / SSO (known; not opened in a browser) | – | **extension-only** | |
| 26 | Welcome to the Jungle (and Otta, which now redirects to app.welcometothejungle.com/login) | platform | very large | robots ok, but **CGU forbids "tout logiciel, script, robot … y compris … les extensions et modules de navigateur … pour procéder à une extraction automatisée de données (« scraping »)"** | account | – | **exclude** | Even an extension is risky |
| 27 | HelloWork / RegionsJob | platform | very large | robots disallows `/fr-fr/offres/postuler`, `/emplois/candidature.html`, `/api/`. **CGU: "systèmes automatisés … considérés comme des utilisateurs non légitimes"; scraping "strictement interdite"** | account | – | **exclude** | |
| 28 | Jobijoba (HelloWork group) | aggregator | large | Same CGU wording as HelloWork | – | – | **exclude** | |
| 29 | Cadremploi / Keljob (now emploi.lefigaro.fr) | platform | large | **CGU forbids automated collection "notamment par l'utilisation de robots … dans le but de nourrir … l'intelligence artificielle"** | account | – | **exclude** | |
| 30 | L'Etudiant jobs-stages | platform | n/a | **CGU: "harvesting, web scraping … interdits" + `TDM-RESERVATION: 1`** | – | – | **exclude** | |
| 31 | Jobs That Make Sense (jobs.makesense.org) | platform | n/a | **CGU forbids "utiliser un robot, notamment d'exploration (spider)… sauf autorisation expresse"** | – | – | **exclude** (ask for a partnership) | |
| 32 | Walt (walt.community) | platform | CFA posts | Legal notice: "ne peut … réutiliser, céder ou exploiter … tout ou partie des éléments" | Walt account | – | **exclude** | |
| 33 | StaffMe, Side | staffing apps | n/a | CGU: "s'interdit de procéder à toute extraction du contenu … à des fins de recrutement" | app account | – | **exclude** | |
| 34 | iQuesta | platform (stages) | n/a | Charter forbids "extractions automatisées … (« scraping »)" | – | – | **exclude** | |
| 35 | Free-Work | platform (IT) | n/a | CGU forbids substantial extraction | account | – | **exclude** | |
| 36 | 1jeune1solution | public aggregator | – | CGU forbids robots and spiders | – | – | **exclude**: use the France Travail and LBA APIs | |
| 37 | Indeed | platform | – | **403 challenge**; robots disallows `/job/`, `/applystart`, `/emplois/` | – | – | **exclude** | |
| 38 | LinkedIn | platform | – | robots `Disallow: /` for `*` and for every AI bot | – | – | **exclude** | |
| 39 | Glassdoor | platform | – | 403 challenge, AI bots blocked | – | – | **exclude** | |
| 40 | APEC, Monster, Diplomeo, MyJobGlasses | platforms | – | **403 / challenge** to the AliceBot UA (APEC and Monster show a bot wall) | – | – | **blocked**, not evaded | |
| 41 | Qapa (Adecco) | staffing app | – | robots ok, sitemap | app account | – | **extension-only** | Not inspected in depth |
| 42 | talent.io | platform | – | TLS or tunnel failure from this egress | – | – | **unknown** | Unverified |
| 43 | Kelio (Bodet) | HR suite | – | No public career-site product found | – | – | **n/a** | |

## How Alice would integrate the GO sources

**1. Choisir le service public.** Discovery: walk `sitemapindex.xml` (offer URLs have the form
`/offre-emploi/<slug>-reference-<REF>/`, and 404s redirect to `/offre-depubliee/`). Parse each
offer page. The licence is Etalab 2.0, so credit the source. Apply: when the page has
`data-at-click … "Postuler par mail"`, read the `href="mailto:<addr>?subject=<REF> - <titre>"`
and send through Alice's `email_sender` with that subject. "Postuler sur le site employeur"
offers go to the ATS router (they often lead to Beetween, Talentsoft or DigitalRecruiters).
Before scaling, check whether data.gouv.fr has a bulk export (not checked).

**2. Werecruit.** Discovery: `careers.werecruit.io/sitemap.xml`, filtered on `/offres/` and a
recent `lastmod`. Apply: a single multipart POST to the offer URL. Fields seen: civilité, nom,
prénom, e-mail, téléphone, disponibilité, attentes salariales, CV (required), plus hidden
fields such as `isEmploye…`. Run `probe.mjs` once to capture the exact field names and any
CSRF token before replaying the request.

**3. Jobaffinity.** Apply in two calls: `POST /newcandidate/upload_async` (the CV), then a
multipart POST to `jobaffinity.fr/apply/<id>` with `x-requested-with: XMLHttpRequest`.
Required: CV, civilité, nom, prénom, email, and the GDPR acknowledgement. Discovery comes only
from employer career pages, France Travail or CSP links that point at jobaffinity.

**4. Personio.** Discovery: `GET https://{slug}.jobs.personio.com/xml?language=fr` (positions
with office, employmentType and schedule). Apply: browser form at `/job/<id>/apply`. Required:
e-mail and availability date; CV optional. Capture the submit request with the probe (in the
earlier run, submit did not fire because required fields were missing).

**5. Breezy.** Discovery: `GET https://{slug}.breezy.hr/json`. Apply: form at `/p/<id>/apply`
with name, email, phone, CV, privacy consent, and an optional video question (Ziggeo). The CV
is uploaded separately before the final POST.

**6. Cegid Talentsoft (only tenants with email-only apply).** Discovery: RSS at
`https://<tenant>/handlers/offerRss.ashx?LCID=1036` (items link to `detailoffre.aspx?idOffre=…`).
Apply: "Je postule à cette offre" (postback) leads to `/my-account/log-in.aspx?ReturnUrl=…`.
On email-only tenants the page asks only "Email address", then the CV and profile form. The
platform then **creates an account in the candidate's name** and emails them credentials, so
the candidate must consent to this explicitly. Detect the tenant mode by checking whether the
ReturnUrl page has `CreationControl_txtNouveauMotDePasse`: if present, the tenant needs a
password and goes to extension-only (CEA, Pasteur); if absent, it is email-only (Framatome,
KPMG). Pages run on ASP.NET WebForms with VIEWSTATE, so drive them in a browser rather than
replaying requests.

**7. DigitalRecruiters.** Apply in a browser: "Postuler" opens `/fr/consent?jobAdId=…`, then
the GDPR checkbox, then "Remplir le CV manuellement" or "Importez votre CV". Respect
`Crawl-delay: 10`. Tenants are found from CSP and France Travail "site employeur" links (the
`/fr/annonce/<id>-<slug>` pattern).

**8. Flatchr.** Apply in a browser at `careers.flatchr.io/vacancy/<id>/apply/` (CV, cover
letter, links; react-select widgets). No feed, so offers come from employer links.

## What I could not verify

- SuccessFactors apply flow: no FR tenant found, and jobs.sap.com is behind a challenge.
- Workable: Cloudflare 1015 rate limit from this egress.
- talent.io: the connection failed.
- Bpifrance and Vinci Energies Talentsoft tenants: the hosts were not found.
- JobTeaser apply flow: taken from known behaviour, not opened in a browser.
- Meteojob CGU: the page was not found.
- Final-step captchas: the form-level absence of a captcha (Personio, Breezy, Werecruit,
  DigitalRecruiters, Flatchr, Ashby) was seen **before submit only**. An invisible
  captcha that fires at submit cannot be ruled out without submitting, and I did not submit.
- FR volumes for most ATS vendors: these are per tenant and I did not total them.
- La bonne alternance apply API: the OpenAPI document path returned 404, so this is unverified.
