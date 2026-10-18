import asyncio
import json
from types import SimpleNamespace

import httpx

from app.agents.application import email_sender
from app.agents.discovery import csp
from app.agents.discovery.csp import _channel, _mailto, contract_of, parse_listing, parse_offer
from app.config import settings
from app.models.job_posting import ApplyChannel, ContractType

URL = ("https://choisirleservicepublic.gouv.fr/offre-emploi/"
       "cadre-cordonnateur-de-pole-reference-2026-2389572/")


def page(*, button: str, nature="Emploi ouvert aux titulaires et aux contractuels",
         extra="", deadline="26/10/2026"):
    ld = {
        "@context": "https://schema.org/", "@type": "JobPosting",
        "title": "CADRE CORDONNATEUR DE POLE - Pôle Psychiatrie (PEA) ",
        "addressLocality": "Guadeloupe (971), France",
        "jobLocation": {"@type": "Place", "address": {"addressLocality": "Pointe-à-Pitre (971), France"}},
        "hiringOrganization": "EPSM de La Guadeloupe ",
        "Description": "\nPlacé sous l’autorité du Directeur des soins.<br>Contrat à durée déterminée.",
        "skills": "\nSAVOIRS : management",
        "datePosted": "16/10/2026",
    }
    return f"""<html><head>
<script type="application/ld+json">{{"@type":"WebSite"}}</script>
<script type="application/ld+json">
    {json.dumps(ld)}</script></head><body>
<ul><li><span class="sr-only">Nature de l’emploi</span> {nature}</li></ul>
<div class="fr-col-12 buttons-wrapper">{button}
<p>Date limite de candidature : {deadline}</p>
</div>
<a href="mailto:?subject=2026-2389572 - CADRE&amp;body=partage">Partager</a>
<h2>Informations complémentaires</h2><p>{extra}</p>
</body></html>"""


MAIL_BUTTON = ('<a data-at-click-exempt=\'{"click" : "Postuler par mail"}\' '
               'href="mailto:recrutement@epsm-guadeloupe.fr?subject=2026-2389572 - CADRE CORDONNATEUR '
               'DE POLE - Pôle Psychiatrie (PEA) " class="fr-btn"><span>Postuler par mail</span></a>')
SITE_BUTTON = ('<a href="https://recrutement.education.gouv.fr/recrutement/offreemploi/a1DIV00000DTgXR">'
               'Postuler sur le site employeur</a>')
ACCOUNT_BUTTON = '<button class="fr-btn" data-open="modal-login" id="btn-postuler">Postuler</button>'


def test_offre_par_mail():
    o = parse_offer(URL, page(button=MAIL_BUTTON))
    assert o.reference == "2026-2389572"
    assert o.title == "CADRE CORDONNATEUR DE POLE - Pôle Psychiatrie (PEA)"
    assert o.employer == "EPSM de La Guadeloupe" and o.location == "Pointe-à-Pitre (971)"
    assert o.posted.isoformat() == "2026-10-16" and o.deadline.isoformat() == "2026-10-26"
    assert "Directeur des soins" in o.description and "<" not in o.description
    assert o.email == "recrutement@epsm-guadeloupe.fr"
    assert o.email_subject == "2026-2389572 - CADRE CORDONNATEUR DE POLE - Pôle Psychiatrie (PEA)"
    channel, _, contact = _channel(o)
    assert channel == ApplyChannel.EMAIL
    assert contact["email"] == o.email and contact["email_subject"] == o.email_subject


def test_le_lien_de_partage_n_est_pas_une_adresse():
    o = parse_offer(URL, page(button=SITE_BUTTON))
    assert o.email is None
    assert o.employer_url.startswith("https://recrutement.education.gouv.fr/")
    channel, _, contact = _channel(o)
    assert channel == ApplyChannel.EXTERNAL_LINK and contact["apply_url"] == o.employer_url


def test_compte_sur_le_site_le_candidat_termine():
    o = parse_offer(URL, page(button=ACCOUNT_BUTTON))
    channel, _, contact = _channel(o)
    assert channel == ApplyChannel.EXTERNAL_LINK and contact["apply_url"] == URL


def test_reservee_aux_fonctionnaires_ecartee():
    assert parse_offer(URL, page(button=MAIL_BUTTON, nature="Emploi ouvert uniquement aux titulaires")) is None


def test_pieces_qu_alice_n_a_pas():
    extra = ("Le dossier de candidature devra comporter : - CV - Lettre de motivation - "
             "copie de la pi&egrave;ce d'identit&eacute; - copie du dipl&ocirc;me - 3 derniers CREP")
    o = parse_offer(URL, page(button=MAIL_BUTTON, extra=extra))
    assert set(o.extra_documents) >= {"pièce d'identité", "diplôme", "comptes rendus d'entretien professionnel"}
    assert not parse_offer(URL, page(button=MAIL_BUTTON, extra="un casier judiciaire compatible")).extra_documents
    channel, _, contact = _channel(o)
    # Pas d'envoi incomplet : le candidat ajoute ses pièces et envoie lui-même.
    assert channel == ApplyChannel.EXTERNAL_LINK
    assert contact["email"] == o.email and contact["extra_documents"]


def test_mailto_adresse_invalide_ou_multiple():
    assert _mailto("mailto:https://carrieres.pix.org/jobs/1?subject=X")[0] is None
    assert _mailto("mailto:rh@justice.gouv.fr ?subject=R%C3%A9f 12")[0] == "rh@justice.gouv.fr"
    assert _mailto("mailto:rh@justice.gouv.fr ?subject=R%C3%A9f 12")[1] == "Réf 12"
    assert _mailto("mailto:bad, a@intradef.gouv.fr; b@intradef.gouv.fr")[0] == "a@intradef.gouv.fr"


def test_liste_des_offres():
    html = (f'<a href="{URL}">a</a><a href="{URL}">doublon</a>'
            '<a href="https://choisirleservicepublic.gouv.fr/nos-offres/page/2/">suite</a>'
            '<a href="https://choisirleservicepublic.gouv.fr/offre-emploi/x-reference-MINT_BA075ACA-127739">b</a>')
    assert parse_listing(html) == [
        URL, "https://choisirleservicepublic.gouv.fr/offre-emploi/x-reference-MINT_BA075ACA-127739/",
    ]


def test_contrat():
    assert contract_of("Apprenti(e) gestionnaire RH", "") == ContractType.ALTERNANCE
    assert contract_of("Stage juriste", "") == ContractType.STAGE
    assert contract_of("Infirmier", "Emploi ouvert uniquement aux contractuels") == ContractType.CDD
    assert contract_of("Infirmier", "Recrutement en CDI") == ContractType.CDI
    assert contract_of("Infirmier", "") == ContractType.UNKNOWN


def test_offre_retiree():
    def handler(request):
        if "retiree" in str(request.url):
            return httpx.Response(302, headers={"location": "https://choisirleservicepublic.gouv.fr/offre-depubliee/"})
        return httpx.Response(200, text="ok")

    async def run(url):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as c:
            return await csp.still_online(url, client=c)

    assert asyncio.run(run("https://choisirleservicepublic.gouv.fr/offre-emploi/retiree/")) is False
    assert asyncio.run(run(URL)) is True


def test_objet_impose_prioritaire_sur_la_lettre(monkeypatch):
    sent = {}

    async def fake_resend(mail):
        sent["mail"] = mail
        return {"ok": True, "real": True, "provider": "resend", "id": "abc"}

    from app.agents.notifications import mailer
    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    monkeypatch.setattr(mailer, "_via_resend", fake_resend)
    asyncio.run(email_sender.send_application_email(
        to_email="rh@epsm.fr", candidate=SimpleNamespace(full_name="Camille Martin", email="c@ex.fr"),
        letter={"subject": "Candidature cadre", "body": "Bonjour"},
        job_title="Cadre", company_name="EPSM", resume=b"%PDF", resume_name="CV.pdf",
        subject="2026-2389572 - CADRE",
    ))
    assert sent["mail"].subject == "2026-2389572 - CADRE"
