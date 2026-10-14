from app.agents.discovery.inrae import contract_of, parse_offer, parse_sitemap
from app.models.job_posting import ContractType

PAGE = """<html><body><nav>apprentissage stage</nav>
<a href="mailto: ?subject=Partage Stage">partager</a>
<h1 class="Hero-title">Stage M2 : Modélisation des sols</h1>
<div>91120 Palaiseau</div>
<h2>Présentation INRAE</h2><p>L'institut…</p>
<h2>Environnement de travail, missions et activités</h2><p>Vous serez accueilli(e)…</p>
<a href="mailto:Florent.Levavasseur@inrae.fr ;marie.curie@inrae.fr">J'envoie mon CV et ma lettre de motivation</a>
<div>Référence de l'offre</div>
<dt>Contrat :</dt><dd>Stage</dd>
<dt>Durée :</dt><dd>6 mois</dd>
<dt>N° de l'offre :</dt><dd>OT-30700</dd>
<dt>Date limite : </dt><dd>15/11/2026</dd>
<p>Haut de page</p><footer><a href="mailto:webmaster@inrae.fr">x</a></footer>
</body></html>"""


def test_parse_offer():
    o = parse_offer("https://jobs.inrae.fr/ot-30700", PAGE)
    assert o.title == "Stage M2 : Modélisation des sols"
    assert o.location == "91120 Palaiseau"
    assert o.contract == ContractType.STAGE
    assert o.emails == ["florent.levavasseur@inrae.fr", "marie.curie@inrae.fr"]  # ni partage, ni pied de page
    assert o.ref == "OT-30700" and str(o.deadline) == "2026-11-15"
    assert o.description.startswith("Environnement de travail") and "Présentation" not in o.description


def test_contract_labels():
    assert contract_of("Mission temporaire", "Stage Master 2 Microbiologie") == ContractType.STAGE
    assert contract_of("Mission temporaire", "Ingénieur-e bioinformatique") == ContractType.CDD
    assert contract_of("Thèse", "Thèse en science du sol") == ContractType.CDD
    assert contract_of("Apprentissage", "Technicien de laboratoire") == ContractType.ALTERNANCE


def test_sitemap_keeps_only_offers():
    xml = """<urlset>
    <url><loc>https://jobs.inrae.fr/ot-30700</loc><lastmod>2026-10-13T14:03Z</lastmod></url>
    <url><loc>https://jobs.inrae.fr/concours/charge-recherche</loc></url>
    <url><loc>https://jobs.inrae.fr/actualites/rapport</loc></url></urlset>"""
    assert list(parse_sitemap(xml)) == ["https://jobs.inrae.fr/ot-30700"]


def test_location_from_full_address():
    page = PAGE.replace("<div>91120 Palaiseau</div>", "<div>24 Chemin Borde Rouge 31320 Toulouse Auzeville</div>")
    assert parse_offer("https://jobs.inrae.fr/ot-1", page).location == "31320 Toulouse Auzeville"


def test_location_odd_formats():
    for raw, want in (("Aubière 63170", "63170 Aubière"), ("35 RENNES", "35 RENNES"), ("35000", "35000")):
        page = PAGE.replace("<div>91120 Palaiseau</div>", f"<div>{raw}</div>")
        assert parse_offer("https://jobs.inrae.fr/ot-1", page).location == want
