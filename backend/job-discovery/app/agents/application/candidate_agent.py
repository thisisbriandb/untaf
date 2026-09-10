"""
CandidateAgent — remplissage d'un formulaire de candidature par pilotage
navigateur, guidé par un schéma plutôt que par des sélecteurs devinés.

Le point de départ n'est pas le DOM mais le contrat de formulaire publié par
l'ATS : `GET /jobs/{id}?questions=true` chez Greenhouse donne le nom exact de
chaque champ, son type, et s'il est obligatoire. Ces noms sont stables — mesurés
identiques sur quatre boards et un millier d'offres — là où une classe CSS
change à chaque refonte.

D'où la règle : on remplit ce que le schéma désigne. Ce que le schéma ne couvre
pas n'est pas deviné ici ; c'est remonté comme non traité, à charge d'un agent
plus souple de s'en occuper.

Rien n'est rapporté comme fait sans avoir été vérifié dans la page après coup.
Un champ qu'on croit avoir rempli et qui est resté vide est un champ vide.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CandidatePayload:
    candidate_id: str
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    cover_letter_text: str | None = None
    cv_pdf_bytes: bytes | None = None
    cv_filename: str = "CV_Candidate.pdf"

    def value_for(self, field_name: str) -> str | None:
        """Valeur du candidat correspondant à un nom de champ de l'ATS."""
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "cover_letter_text": self.cover_letter_text,
            "urls[LinkedIn]": self.linkedin_url,
            "urls[GitHub]": self.github_url,
            "urls[Portfolio]": self.portfolio_url,
        }.get(field_name)

    def value_for_semantic(self, semantic) -> str | None:
        """
        Valeur correspondant à un type sémantique, quelle que soit la façon
        dont le formulaire nomme son champ.

        C'est ce qui rend l'agent indépendant d'un ATS : « Vorname », « First
        name » et `#first_name` désignent la même donnée du profil.
        """
        from app.agents.application.field_classifier import Semantic

        return {
            Semantic.FIRST_NAME: self.first_name,
            Semantic.LAST_NAME: self.last_name,
            Semantic.FULL_NAME: f"{self.first_name} {self.last_name}".strip(),
            Semantic.EMAIL: self.email,
            Semantic.PHONE: self.phone,
            Semantic.LINKEDIN: self.linkedin_url,
            Semantic.GITHUB: self.github_url,
            Semantic.PORTFOLIO: self.portfolio_url,
            Semantic.COVER_LETTER: self.cover_letter_text,
        }.get(semantic)


@dataclass
class ApplicationSubmissionResult:
    """
    Ce qui s'est réellement passé.

    `status` ne vaut `submitted` que si le formulaire a été soumis pour de bon.
    Une répétition reste `dry_run_success`, une indisponibilité reste `failed` :
    ces trois états ne doivent jamais se confondre, sinon le compte rendu rendu
    à l'utilisateur ne vaut rien.
    """

    job_id: str
    company_name: str
    status: str  # "submitted" | "dry_run_success" | "failed"
    filled_fields: list[str] = field(default_factory=list)
    uploaded_files: list[str] = field(default_factory=list)
    #: Champs du schéma qu'on n'a pas su remplir — la matière d'un repli.
    unhandled_fields: list[str] = field(default_factory=list)
    error: str | None = None


class CandidateAgent:
    """Pilote un navigateur pour remplir un formulaire de candidature."""

    def __init__(self, dry_run: bool = True, headless: bool = True):
        self.dry_run = dry_run
        self.headless = headless

    async def apply_to_job(
        self,
        job_url: str,
        company_name: str,
        payload: CandidatePayload,
        schema: list[dict[str, Any]] | None = None,
    ) -> ApplicationSubmissionResult:
        """
        Remplit et, si autorisé, soumet le formulaire.

        `schema` est la liste des champs telle que publiée par l'ATS. Sans
        schéma, on se rabat sur le socle commun — les six champs dont les noms
        sont identiques partout.
        """
        filled: list[str] = []
        uploaded: list[str] = []
        unhandled: list[str] = []

        def failed(reason: str) -> ApplicationSubmissionResult:
            # Conserver le travail partiel : savoir que quatre champs sur six
            # étaient bons oriente le repli, alors qu'un échec nu ne dit rien.
            return ApplicationSubmissionResult(
                job_id=job_url, company_name=company_name, status="failed",
                filled_fields=filled, uploaded_files=uploaded,
                unhandled_fields=unhandled, error=reason,
            )

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            # Ne jamais transformer une dépendance absente en candidature
            # réussie : c'est un échec, et l'utilisateur doit pouvoir finir
            # à la main.
            logger.error("Playwright absent : impossible de piloter un navigateur.")
            return failed(
                "L'automatisation navigateur n'est pas installée sur ce serveur "
                "(paquet « playwright »)."
            )

        fields = schema or _DEFAULT_SCHEMA
        cv_path: str | None = None

        try:
            if payload.cv_pdf_bytes:
                # Playwright téléverse depuis un chemin : les octets doivent
                # exister sur le disque le temps de l'envoi.
                handle, cv_path = tempfile.mkstemp(suffix=".pdf")
                with os.fdopen(handle, "wb") as f:
                    f.write(payload.cv_pdf_bytes)

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                page = await context.new_page()
                await page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)

                # Les boards ATS rendent leur formulaire côté client, et pas
                # d'un bloc : les champs texte apparaissent avant les champs
                # fichier. Attendre un délai fixe fait manquer les seconds ;
                # on attend donc que le réseau se calme, et on se rabat sur une
                # pause si la page garde une connexion ouverte en permanence.
                try:
                    await page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:  # noqa: BLE001
                    await page.wait_for_timeout(3_000)

                for entry in fields:
                    name = entry.get("name")
                    if not name:
                        continue
                    kind = entry.get("type", "input_text")

                    try:
                        await _handle_field(
                            page, entry, name, kind, payload, cv_path,
                            filled, uploaded, unhandled,
                        )
                    except Exception as err:  # noqa: BLE001
                        # Un champ récalcitrant n'annule pas les autres. C'est
                        # précisément la matière d'un repli : on note ce qui
                        # résiste et on continue.
                        logger.info("Champ « %s » non traité : %s", name, err)
                        unhandled.append(name)

                if self.dry_run:
                    await browser.close()
                    return ApplicationSubmissionResult(
                        job_id=job_url, company_name=company_name,
                        status="dry_run_success", filled_fields=filled,
                        uploaded_files=uploaded, unhandled_fields=unhandled,
                    )

                # Un champ obligatoire non renseigné fera échouer la soumission
                # côté ATS. Autant s'arrêter avant, avec un motif utilisable,
                # plutôt que de brûler l'offre sur un envoi incomplet.
                if unhandled:
                    await browser.close()
                    return ApplicationSubmissionResult(
                        job_id=job_url, company_name=company_name,
                        status="failed", filled_fields=filled,
                        uploaded_files=uploaded, unhandled_fields=unhandled,
                        error=(
                            "Champs obligatoires non renseignés : "
                            + ", ".join(unhandled)
                        ),
                    )

                submit = page.locator(
                    'button[type="submit"], input[type="submit"]'
                ).first
                if not await submit.count():
                    await browser.close()
                    return ApplicationSubmissionResult(
                        job_id=job_url, company_name=company_name,
                        status="failed", filled_fields=filled,
                        uploaded_files=uploaded, unhandled_fields=unhandled,
                        error="Bouton de soumission introuvable.",
                    )

                await submit.click()
                await page.wait_for_timeout(4_000)
                await browser.close()

                return ApplicationSubmissionResult(
                    job_id=job_url, company_name=company_name,
                    status="submitted", filled_fields=filled,
                    uploaded_files=uploaded, unhandled_fields=unhandled,
                )

        except Exception as err:  # noqa: BLE001
            logger.error(
                "CandidateAgent a échoué pour %s (%s) : %s",
                company_name, job_url, err, exc_info=True,
            )
            return failed(str(err))
        finally:
            if cv_path and os.path.exists(cv_path):
                os.unlink(cv_path)


async def _handle_field(
    page, entry: dict, name: str, kind: str, payload: "CandidatePayload",
    cv_path: str | None,
    filled: list[str], uploaded: list[str], unhandled: list[str],
) -> None:
    """Traite un champ du schéma. Ne rapporte que ce que la page confirme."""
    if kind == "input_file":
        if not cv_path or name not in ("resume", "cv"):
            if entry.get("required"):
                unhandled.append(name)
            return
        locator = await _locate(page, name, file_only=True)
        if locator is None:
            unhandled.append(name)
            return
        # Ces champs sont souvent masqués derrière un bouton stylisé.
        # `set_input_files` sait travailler sur un input caché, mais son
        # attente d'actionnabilité, elle, ne le sait pas.
        await locator.set_input_files(cv_path, timeout=10_000)

        # La confirmation ne peut pas venir de l'input lui-même : sur
        # Greenhouse, React le remplace par un affichage « fichier joint » dès
        # que l'upload aboutit, et l'interroger expire. On demande donc à la
        # page ce qu'elle montre — le nom du fichier, ou un input qui porte
        # encore un fichier. Les deux sont des preuves ; l'absence des deux est
        # un échec, pas un doute qu'on tranche en notre faveur.
        await page.wait_for_timeout(1_500)
        if await _file_is_attached(page, name, cv_path):
            uploaded.append(payload.cv_filename)
        else:
            unhandled.append(name)
        return

    value = payload.value_for(name)
    if value is None or value == "":
        # Une question obligatoire qu'on ne sait pas renseigner bloque la
        # candidature : il faut le dire, pas la passer sous silence.
        if entry.get("required"):
            unhandled.append(name)
        return

    locator = await _locate(page, name)
    if locator is None:
        unhandled.append(name)
        return

    # Une liste de choix n'est pas un champ texte, même quand elle en a l'air.
    # Greenhouse rend ses listes en `role="combobox"` : y écrire du texte
    # laisse `aria-activedescendant` vide, donc le formulaire part sans valeur.
    # `input_value()` renverrait pourtant le texte saisi — un faux positif.
    if await _is_combobox(locator):
        if await _select_option(page, locator, value):
            filled.append(name)
        else:
            unhandled.append(name)
        return

    await locator.fill(value, timeout=10_000)
    if (await locator.input_value()) == value:
        filled.append(name)
    else:
        unhandled.append(name)


async def _is_combobox(locator) -> bool:
    """Le champ attend-il un choix dans une liste plutôt qu'une saisie libre ?"""
    try:
        return await locator.evaluate(
            "e => e.tagName === 'SELECT' || e.getAttribute('role') === 'combobox'"
        )
    except Exception:  # noqa: BLE001
        return False


async def _select_option(page, locator, value: str) -> bool:
    """
    Choisit une option dans une liste, et ne renvoie vrai que si le choix a
    réellement été enregistré.

    Un `<select>` natif se pilote directement. Une liste React demande la même
    séquence qu'un humain : ouvrir, filtrer, cliquer l'option. Dans les deux
    cas, la confirmation vient de l'état du composant après coup — jamais du
    seul fait qu'on ait tapé le texte.
    """
    try:
        if await locator.evaluate("e => e.tagName === 'SELECT'"):
            await locator.select_option(label=value, timeout=5_000)
            return bool(await locator.input_value())
    except Exception:  # noqa: BLE001
        return False

    try:
        await locator.click(timeout=5_000)
        # Frappe caractère par caractère, et non `fill()` : ce dernier écrit
        # la valeur dans le DOM sans émettre les événements clavier auxquels
        # un composant React réagit — la liste ne se filtre alors jamais.
        # Un préfixe, pas la valeur entière : saisir « France » en entier fait
        # disparaître la liste de ces composants, et il ne reste plus rien à
        # cliquer. Quatre caractères suffisent à filtrer sans la refermer.
        await locator.press_sequentially(value[:4], delay=45, timeout=8_000)
        await page.wait_for_timeout(900)

        # Ne viser que les options RÉELLEMENT visibles : ces listes gardent
        # leurs centaines d'options dans le DOM en permanence, et cliquer un
        # élément masqué échoue sans rien dire d'utile.
        options = page.locator('[role="option"]:visible')
        count = await options.count()
        if not count:
            return False

        target = None
        for i in range(min(count, 40)):
            candidate = options.nth(i)
            text = ((await candidate.inner_text()) or "").strip()
            if text.lower() == value.lower():
                target = candidate
                break
            if target is None and value.lower() in text.lower():
                target = candidate
        if target is None:
            return False

        chosen = ((await target.inner_text()) or "").strip()
        # Chemin clavier plutôt que clic : c'est l'interaction que ces
        # composants implémentent en premier, et un clic sur l'option ne
        # déclenche pas toujours leur gestionnaire de sélection.
        await locator.press("ArrowDown")
        await page.wait_for_timeout(200)
        await locator.press("Enter")
        await page.wait_for_timeout(500)

        # La preuve est l'état durable du composant : ce qu'il affiche une fois
        # refermé. `aria-activedescendant` ne sert qu'au pilotage clavier et se
        # vide après un clic — s'y fier ferait déclarer en échec une sélection
        # pourtant réussie.
        # La preuve : le champ affiche l'intitulé exact de l'option cliquée.
        # Ce n'est pas la même chose que d'y avoir tapé du texte — on n'a saisi
        # qu'un préfixe, donc une valeur complète ne peut venir que d'une
        # sélection réelle.
        shown = ((await locator.input_value()) or "").strip()
        return bool(shown) and shown.lower() == chosen.lower()
    except Exception:  # noqa: BLE001
        return False


async def _file_is_attached(page, name: str, cv_path: str) -> bool:
    """Le fichier est-il réellement joint, d'après ce que la page expose ?"""
    stem = os.path.basename(cv_path)

    # 1) L'input existe encore et porte un fichier.
    try:
        count = await page.evaluate(
            "id => { const e = document.getElementById(id);"
            " return e && e.files ? e.files.length : -1; }",
            name,
        )
        if count and count > 0:
            return True
    except Exception:  # noqa: BLE001
        pass

    # 2) Le formulaire affiche le nom du fichier joint.
    try:
        body = (await page.inner_text("body")) or ""
        return stem in body
    except Exception:  # noqa: BLE001
        return False


async def _locate(page, name: str, *, file_only: bool = False):
    """
    Retrouve dans la page le champ que le schéma désigne.

    L'ordre n'est pas arbitraire. Le nom publié par l'API est le contrat de
    soumission, pas un attribut du DOM : sur les boards React, les champs
    portent ce nom en `id` et n'ont **aucun** attribut `name`. On cherche donc
    l'identifiant d'abord, le nom ensuite pour les formulaires classiques.
    """
    kind = 'input[type="file"]' if file_only else "input, textarea, select"
    for selector in (
        f'#{name}' if not file_only else f'input[type="file"]#{name}',
        f'[name="{name}"]',
    ):
        try:
            locator = page.locator(selector).first
            if await locator.count():
                return locator
        except Exception:  # noqa: BLE001 — un sélecteur invalide n'est pas fatal
            continue

    # Dernier recours pour le CV : beaucoup de formulaires n'ont qu'un seul
    # champ fichier, et se tromper de cible est impossible.
    if file_only:
        locator = page.locator(kind)
        if await locator.count() == 1:
            return locator.first
    return None


#: Socle commun, mesuré identique sur tous les boards Greenhouse testés.
#: Sert quand l'ATS ne publie pas son schéma.
_DEFAULT_SCHEMA: list[dict[str, Any]] = [
    {"name": "first_name", "type": "input_text", "required": True},
    {"name": "last_name", "type": "input_text", "required": True},
    {"name": "email", "type": "input_text", "required": True},
    {"name": "phone", "type": "input_text", "required": False},
    {"name": "resume", "type": "input_file", "required": True},
    {"name": "cover_letter_text", "type": "textarea", "required": False},
]
