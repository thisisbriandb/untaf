"""Adapter un CV met en avant, ne retire rien."""

from types import SimpleNamespace

from app.agents.application.cv_completeness import missing_sections, order_skills_for_job


def test_ordre_des_competences_sans_perte():
    skills = ["Excel", "Python", "Docker", "SQL"]
    ordered = order_skills_for_job(skills, ["SQL", "python"], "Stack : Docker et Kubernetes")
    assert ordered[:2] == ["Python", "SQL"]  # demandées par l'offre, ordre du candidat gardé
    assert ordered[2] == "Docker"             # citée dans l'annonce
    assert sorted(ordered) == sorted(skills)  # rien n'est retiré


def test_sections_manquantes_nommees():
    c = SimpleNamespace(cv_content={"experiences": [{"jobTitle": "Dev"}]}, skills=[], resume_raw="")
    assert missing_sections(c) == ["education", "languages", "skills", "summary"]
    full = SimpleNamespace(
        cv_content={"experiences": [1], "education": [1], "languages": [1], "summary": "x"},
        skills=["Python"], resume_raw=None,
    )
    assert missing_sections(full) == []


def test_renotation_ne_supprime_pas_un_dossier_prepare():
    from app.agents.discovery.tasks import _protected
    from app.models.application import Application, ApplicationStatus

    assert _protected(Application(status=ApplicationStatus.MATCHED,
                                  metadata_json={"cover_letter": {"body": "x"}}))
    assert _protected(Application(status=ApplicationStatus.APPLIED, metadata_json=None))
    assert not _protected(Application(status=ApplicationStatus.PENDING, metadata_json={"match": {}}))


def test_un_telechargement_qui_plante_renvoie_un_message_clair(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from app.api import apply

    sent = {}

    async def fake_incident(kind, candidate_id, detail, context=None, notify_user=True):
        sent.update(kind=kind, context=context)

    monkeypatch.setattr("app.agents.incidents.report_incident", fake_incident)

    @apply._guard_download("test")
    async def boom(candidate_id=None, job_id=None):
        raise RuntimeError("typst a explosé")

    try:
        asyncio.run(boom(candidate_id="c", job_id="j"))
    except HTTPException as e:
        assert e.status_code == 500 and "L'équipe est prévenue" in e.detail
    assert sent["kind"] == "pack_failed" and "typst a explosé" in sent["context"]["erreur"]


def test_cv_lu_depuis_un_pdf_se_met_en_page():
    """Dates libres, bornes manquantes, puces en objets : le rendu ne casse plus."""
    from types import SimpleNamespace
    import pytest
    from app.agents.application import cv_resolver as r

    if not r.HAS_ENGINE:
        pytest.skip("cv-engine absent")
    cand = SimpleNamespace(
        cv_design={"mode": "original"}, resume_file=b"%PDF", resume_filename="cv.pdf",
        headline="Dev", full_name="Test Candidat", skills=["C#", "SQL"], email="t@ex.fr",
        phone="06", linkedin_url=None,
        cv_content={
            "experiences": [
                {"company": "A", "jobTitle": "Dev", "startDate": "Septembre 2022", "endDate": "Aujourd'hui"},
                {"company": "B", "jobTitle": "Stage", "startDate": "09/2021", "highlights": [{"text": "API"}]},
                {"company": "C", "jobTitle": "Job", "startDate": "??", "endDate": "06/2020"},
            ],
            "education": [{"institution": "IUT", "degree": "BUT", "startYear": "Sept 2019", "endYear": "en cours"}],
        },
    )
    pdf, _, origin = r.resolve_cv(cand, {"headline": "Dev C#", "summary": "s"})
    assert origin == "tailored" and pdf


def test_dates_normalisees():
    from app.agents.application.cv_resolver import _date
    assert _date("09/2022") == "2022-09"
    assert _date("Septembre 2022") == "2022-09"
    assert _date("Sept. 2020") == "2020-09"
    assert _date("en cours") == "present"
    assert _date(2021) == "2021"
    assert _date("n'importe quoi") == ""
