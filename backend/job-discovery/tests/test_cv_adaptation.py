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
