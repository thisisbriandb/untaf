import asyncio

import httpx

from app.agents.inbox import Incoming, wants_optout
from app.agents.spontaneous import contacts, directory
from app.agents.spontaneous.contacts import best_contact, extract_emails, name_matches, registrable
from app.api.optout import _sign


HOME = """<html><head><title>Acme Logiciels — éditeur lyonnais</title>
<meta name="description" content="Acme édite des logiciels de gestion pour les PME."></head>
<body><p>Acme Logiciels conçoit des outils pour 2 000 PME.</p>
<a href="/nous-rejoindre">Nous rejoindre</a> <a href="/blog">Blog</a>
<a href="https://twitter.com/acme">Twitter</a>
<footer>contact@acme-logiciels.fr · dpo@acme-logiciels.fr · agence@autre-site.fr</footer></body></html>"""
JOIN = """<html><body><h1>Rejoignez-nous</h1>
<p>Envoyez votre candidature à recrutement [at] acme-logiciels [dot] fr</p>
<a href="mailto:jean.dupont@acme-logiciels.fr">Jean</a></body></html>"""


def test_only_published_addresses_of_the_company_domain():
    emails = extract_emails(HOME + JOIN, "www.acme-logiciels.fr")
    assert "recrutement@acme-logiciels.fr" in emails       # forme masquée relue
    assert "contact@acme-logiciels.fr" in emails
    assert "dpo@acme-logiciels.fr" not in emails           # jamais le DPO
    assert "agence@autre-site.fr" not in emails            # autre domaine


def test_recruiting_address_preferred_and_personal_ones_refused():
    c = best_contact([("contact@acme.fr", "u1"), ("recrutement@acme.fr", "u2")])
    assert c.email == "recrutement@acme.fr" and c.kind == "recrutement"
    assert best_contact([("contact@acme.fr", "u")]).kind == "general"
    assert best_contact([("jean.dupont@acme.fr", "u")]) is None


def test_site_must_carry_the_company_name():
    assert name_matches("ACME LOGICIELS SAS", "Acme Logiciels — éditeur")
    assert not name_matches("Boulangerie Martin SARL", "Bienvenue chez Dupont")
    assert registrable("jobs.acme.co.uk") == "acme.co.uk" and registrable("www.acme.fr") == "acme.fr"


def _client(routes):
    def handler(request: httpx.Request):
        for prefix, (status, body, ctype) in routes.items():
            if str(request.url).startswith(prefix):
                return httpx.Response(status, text=body if isinstance(body, str) else None,
                                      json=None if isinstance(body, str) else body,
                                      headers={"content-type": ctype})
        return httpx.Response(404, text="", headers={"content-type": "text/html"})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_scan_site_finds_the_recruiting_address_and_summary():
    client = _client({
        "https://www.acme-logiciels.fr/robots.txt": (200, "User-agent: *\nDisallow: /admin", "text/plain"),
        "https://www.acme-logiciels.fr/nous-rejoindre": (200, JOIN, "text/html"),
        "https://www.acme-logiciels.fr": (200, HOME, "text/html"),
    })
    found = asyncio.run(contacts.scan_site("https://www.acme-logiciels.fr", "ACME LOGICIELS", client))
    assert found and found.contact.email == "recrutement@acme-logiciels.fr"
    assert found.contact.source_url.endswith("/nous-rejoindre")
    assert "logiciels de gestion" in found.summary


def test_scan_site_rejects_a_site_that_is_not_the_company():
    client = _client({"https://www.autre.fr": (200, "<title>Autre chose</title>", "text/html")})
    assert asyncio.run(contacts.scan_site("https://www.autre.fr", "ACME LOGICIELS", client)) is None


def test_directory_targets_by_sector_and_department():
    client = _client({
        directory.GEO: (200, {"features": [{"properties": {"context": "69, Rhône, Auvergne-Rhône-Alpes"}}]}, "application/json"),
        directory.API: (200, {"results": [
            {"siren": "123456789", "nom_complet": "ACME LOGICIELS", "activite_principale": "62.01Z",
             "tranche_effectif_salarie": "12", "siege": {"libelle_commune": "LYON", "departement": "69"}},
            {"siren": "", "nom_complet": "SANS SIREN"},
        ]}, "application/json"),
    })
    targets = asyncio.run(directory.find_targets(["software"], ["Lyon"], client=client))
    assert [t.siren for t in targets] == ["123456789"] and targets[0].department == "69"
    assert asyncio.run(directory.find_targets(["inconnu"], ["Lyon"], client=client)) == []


def test_optout_link_is_signed_and_stop_replies_are_understood():
    assert _sign("Jobs@Acme.fr") == _sign("jobs@acme.fr") != _sign("other@acme.fr")
    stop = Incoming("x", "rh@acme.fr", ["a@b.c"], "Re: Candidature spontanée", "STOP merci")
    keep = Incoming("y", "rh@acme.fr", ["a@b.c"], "Re: Candidature", "Bonjour, échangeons jeudi ?")
    assert wants_optout(stop) and not wants_optout(keep)


def test_user_agent_is_ascii():
    # Un accent dans un en-tête HTTP fait échouer toutes les visites de sites.
    contacts.USER_AGENT.encode("ascii")


def test_optout_link_uses_railway_domain_when_not_configured(monkeypatch):
    from app.api import optout
    monkeypatch.setattr(optout.settings, "public_api_url", "")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "untaf-production.up.railway.app")
    assert optout.optout_link("Jobs@Acme.fr").startswith(
        "https://untaf-production.up.railway.app/api/optout?e=jobs%40acme.fr&t=")
    monkeypatch.setattr(optout.settings, "public_api_url", "api.alice-agent.fr/")
    assert optout.public_base() == "https://api.alice-agent.fr"
    monkeypatch.setattr(optout.settings, "public_api_url", "")
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN")
    assert optout.optout_link("jobs@acme.fr") is None
