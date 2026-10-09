"""Écoles et CFA qui publient des « offres » d'alternance pour remplir leurs promotions."""

from datetime import datetime, timezone

import pytest

from app.agents.discovery.labonnealternance import to_scraped_job
from app.agents.discovery.matching import evaluate_match
from app.agents.discovery.signals import training_org_evidence
from app.models.candidate import Candidate
from app.models.job_posting import JobPosting
from app.schemas.matching import MatchingCriteria


def _candidate() -> Candidate:
    c = Candidate(full_name="Léa Petit", email="lea@example.com", headline="Commerciale",
                  skills=[], experience_years=0.0, preferred_locations=["Lyon"],
                  preferred_remote_policies=[], preferred_contract_types=[], matching_criteria=None)
    c.matching_criteria = MatchingCriteria(contract_types=["alternance"]).model_dump()
    return c


def _job(title, description="", employer=None):
    return JobPosting(title=title, location="Lyon", description_raw=description, tech_stack=[],
                      first_seen_at=datetime.now(timezone.utc),
                      description_parsed={"contract_type": "alternance", **({"employer": employer} if employer else {})})


PITCH = ("Rejoins notre école ! Formation gratuite et rémunérée, nous te trouvons une entreprise "
         "partenaire. Admissions ouvertes, rentrée de septembre.")


@pytest.mark.parametrize("name,text,employer,level", [
    ("ISCOD", PITCH, None, "strong"),                                     # phrases seules, nombreuses
    ("Studi", "Alternance commerciale", {"naf": "85.59B"}, "weak"),        # un seul indice
    ("MBway Lyon", "Alternance — frais de scolarité pris en charge", {"naf": "8542Z"}, "strong"),
    ("École de Commerce de Lyon", "Assistant RH en alternance dans nos services", None, "weak"),
    ("Institut Pasteur", "Technicien de laboratoire en alternance", None, None),
    ("Acme SAS", "Développeur en alternance, équipe produit", {"sector_code": "62"}, None),
])
def test_evidence(name, text, employer, level):
    assert training_org_evidence(name, text, employer)[0] == level


def test_school_offer_is_rejected_with_reason():
    res = evaluate_match(_candidate(), _job("Commercial en alternance", PITCH), company_name="ISCOD")
    assert not res.accepted
    assert res.rejections[0].startswith("organisme de formation :")


def test_single_clue_is_kept_and_flagged():
    res = evaluate_match(_candidate(), _job("Chargé de communication en alternance",
                                            "Au sein du service communication de l'école."),
                         company_name="École de Commerce de Lyon")
    assert not any(r.startswith("organisme de formation") for r in res.rejections)
    assert res.signals.get("training_org")


def test_school_hiring_a_teacher_is_not_touched():
    """Un CDI de formateur dans un CFA est un vrai poste : le filtre ne vise que l'alternance."""
    job = JobPosting(title="Formateur commerce H/F", location="Lyon", description_raw=PITCH,
                     tech_stack=[], first_seen_at=datetime.now(timezone.utc),
                     description_parsed={"contract_type": "cdi"})
    c = _candidate()
    c.matching_criteria = MatchingCriteria().model_dump()
    res = evaluate_match(c, job, company_name="CFA Lyon")
    assert not any(r.startswith("organisme de formation") for r in res.rejections)


def test_lba_keeps_employer_naf():
    job = to_scraped_job({
        "identifier": {"id": "1"}, "apply": {"recipient_id": "r1", "url": "https://x"},
        "offer": {"title": "Vendeur"}, "contract": {},
        "workplace": {"name": "Ecole X", "siret": "12345678900011",
                      "domain": {"naf": {"code": "85.59A", "label": "Formation continue d'adultes"}}},
    })
    assert job.extra["parsed"]["employer"]["naf"] == "85.59A"
