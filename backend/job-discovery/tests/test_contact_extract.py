"""Extraction des coordonnées de candidature dans un texte libre."""

from app.agents.discovery.contact_extract import (
    find_apply_email,
    find_apply_url,
    is_valid_email,
)


def test_consigne_france_travail_sans_adresse():
    text = "Pour postuler, utiliser le lien suivant : https://candidat.francetravail.fr/offres/123"
    assert find_apply_email(text) is None
    # Le portail authentifié n'est pas un formulaire employeur.
    assert find_apply_url(text) is None


def test_adresse_dans_une_consigne():
    assert find_apply_email("Envoyer CV et lettre à rh@acme.fr.") == "rh@acme.fr"


def test_boites_de_plateforme_et_automatiques_refusees():
    for address in (
        "ne-pas-repondre@francetravail.fr", "noreply@acme.fr",
        "contact@pole-emploi.fr", "logo@2x.png",
    ):
        assert not is_valid_email(address), address


def test_preference_pour_la_boite_de_candidature():
    text = (
        "Pour toute question sur le site : webmaster@acme.fr. "
        "Candidatures (CV + lettre de motivation) : recrutement@acme.fr"
    )
    assert find_apply_email(text) == "recrutement@acme.fr"


def test_description_exige_un_contexte_de_candidature():
    assert find_apply_email("Notre blog : redaction@acme.fr", min_score=2) is None
    assert find_apply_email("Envoyez votre CV à jobs@acme.fr", min_score=2) == "jobs@acme.fr"


def test_lien_employeur_conserve():
    text = "Postulez ici : https://acme.fr/carrieres/42, merci."
    assert find_apply_url(text) == "https://acme.fr/carrieres/42"


def test_offre_france_travail_avec_adresse_cachee():
    from app.agents.discovery.france_travail import to_scraped_job

    job = to_scraped_job({
        "id": "123ABC",
        "intitule": "Développeur Python",
        "description": "Rejoignez-nous.",
        "contact": {"courriel": "Merci d'adresser votre CV à jobs@acme.fr"},
    })
    assert job.extra["contact"]["email"] == "jobs@acme.fr"
