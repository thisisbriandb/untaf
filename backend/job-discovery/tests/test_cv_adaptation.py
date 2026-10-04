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
