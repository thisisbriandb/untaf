from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.agents.application.feasibility import apply_mode, assess, direct_first
from app.agents.discovery.werecruit import _channel, contract_of, parse_offer, parse_sitemap
from app.config import settings
from app.models.job_posting import ApplyChannel, ContractType, JobPosting

URL = "https://careers.werecruit.io/fr/motherson-aerospace/offres/referent-qualite-produit-process-7f9dc1"


def page(form=True, civility=True, questions=0):
    custom = "".join(f'<input name="question:{i:08d}-0000-0000-0000-000000000000" required>'
                     for i in range(questions))
    body = (f'''<form method="POST" id="form" name="form" action="{URL}" enctype="multipart/form-data">
<input type="radio" name="civility" value="1" {"required" if civility else ""}>
<input type="text" name="lastName" required><input type="file" name="Resume">
{custom}<input id="optin" name="optin" type="checkbox" required value="true">
<input name="__RequestVerificationToken" type="hidden" value="x" /></form>''') if form else ""
    return f'''<html><head>
<meta content="R&#xE9;f&#xE9;rent Qualit&#xE9; Produit Process F/H - CDI &#xE0; Serres-Castet | AD Industries Sheet Metal"
          property="og:title"/>
<meta name="dcterms.created"
              content="2026-10-16"/>
</head><body>
<h1 class="x">
    R&#xE9;f&#xE9;rent Qualit&#xE9; Produit Process F/H
</h1>
<p><span>
    Type de contrat :&nbsp;
</span>
    CDI
</p>
<div><h2 class="h4 description-subtitle">Description du poste</h2>
<p>Le <strong>R&eacute;f&eacute;rent</strong> est garant des exigences.</p><ul><li>Animer la qualit&eacute;</li></ul></div>
{body}</body></html>'''


def test_offre_lue():
    o = parse_offer(URL, page())
    assert (o.code, o.tenant) == ("7f9dc1", "motherson-aerospace")
    assert o.title == "Référent Qualité Produit Process F/H"
    assert o.company == "AD Industries Sheet Metal" and o.location == "Serres-Castet"
    assert o.contract == ContractType.CDI and o.posted.isoformat() == "2026-10-16"
    assert "Description du poste" in o.description and "• Animer la qualité" in o.description
    assert "<" not in o.description


def test_civilite_et_accord_au_candidat_seul():
    o = parse_offer(URL, page(questions=2))
    assert o.has_form
    assert o.questions == ["civilité", "accord de conservation des données", "2 question(s) de l'employeur"]
    channel, _, contact = _channel(o)
    # Jamais un envoi par Alice : l'extension remplit, le candidat coche et envoie.
    assert channel == ApplyChannel.WEB_FORM and contact["werecruit"]["tenant"] == "motherson-aerospace"
    job = SimpleNamespace(apply_channel=channel, contact_json=contact, apply_url=URL, source_url=URL)
    verdict = assess(job)
    assert not verdict.automatable and "civilité" in verdict.blockers[0]
    assert apply_mode(job) == "manual"


def test_sans_formulaire_lien_simple():
    o = parse_offer(URL, page(form=False))
    assert not o.has_form and _channel(o)[0] == ApplyChannel.EXTERNAL_LINK


def test_sitemap_recentes_sans_ecoles():
    xml = """<urlset>
<url><loc>https://careers.werecruit.io/fr/acme/offres/plieur-41a575</loc><lastmod>2026-10-16T12:59+00:00</lastmod></url>
<url><loc>https://careers.werecruit.io/fr/acme/offres/vieux-abc123</loc><lastmod>2019-10-01T10:00+00:00</lastmod></url>
<url><loc>https://careers.werecruit.io/fr/walter-learning/offres/assistant-rh-en-alternance-def456</loc><lastmod>2026-10-16T10:00+00:00</lastmod></url>
<url><loc>https://careers.werecruit.io/fr/acme</loc><lastmod>2026-10-16T10:00+00:00</lastmod></url>
</urlset>"""
    listed = parse_sitemap(xml, now=datetime(2026, 10, 17, tzinfo=UTC))
    assert list(listed) == ["41a575"]


def test_contrat():
    assert contract_of("Intérim", "Plieur") == ContractType.INTERIM
    assert contract_of("CDD", "Vendeur") == ContractType.CDD
    assert contract_of("CDI", "Commercial en alternance") == ContractType.ALTERNANCE
    assert contract_of("Indépendant", "Conseiller immobilier") == ContractType.FREELANCE


def test_alice_envoie_d_abord(monkeypatch):
    """Le tri SQL met devant ce qu'Alice envoie elle-même, avant le score."""
    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    sql = str(select(JobPosting.id).order_by(direct_first()).compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "'EMAIL'" in sql and "'TALEEZ_API'" in sql and "'RECRUITEE_API'" in sql
    assert "WEB_FORM" not in sql
    assert "extra_documents" in sql and "email" in sql


def test_pieces_manquantes_jamais_auto():
    job = SimpleNamespace(apply_channel=ApplyChannel.EXTERNAL_LINK, apply_url=None, source_url="https://x",
                          contact_json={"email": "rh@epsm.fr", "email_subject": "R1 - Cadre",
                                        "extra_documents": ["pièce d'identité"]})
    assert apply_mode(job) == "manual"
    verdict = assess(job)
    assert not verdict.automatable and "R1 - Cadre" in verdict.summary
