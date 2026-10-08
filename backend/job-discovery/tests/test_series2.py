"""Audit série 2 : séniorité, métier déduit, nom manquant, CV scanné."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.agents.application.dispatcher import Hold, pre_send_check
from app.agents.application.email_sender import _plain_text
from app.agents.application.identity import real_name
from app.agents.discovery.matching import evaluate_match
from app.agents.discovery.signals import detect_job_family
from app.models.candidate import Candidate
from app.models.dispatch import DispatchStatus
from app.models.job_posting import JobPosting
from app.schemas.matching import MatchingCriteria


def _candidate(**kw) -> Candidate:
    base = dict(
        full_name="Camille Martin", email="camille@example.com",
        headline="Responsable logistique", skills=[], experience_years=10.0,
        preferred_locations=["Lyon"], preferred_remote_policies=[], preferred_contract_types=[],
        matching_criteria=None,
    )
    base.update(kw)
    return Candidate(**base)


def _job(title: str, **kw) -> JobPosting:
    base = dict(
        title=title, location="Lyon", description_raw="", tech_stack=[],
        first_seen_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    return JobPosting(**base)


# ── Séniorité ──────────────────────────────────────────────────────────────

def test_experienced_candidate_targeting_alternance_is_not_rejected():
    c = _candidate(preferred_contract_types=["alternance"])
    res = evaluate_match(c, _job("Assistant logistique en alternance"), parsed={}, company_name="")
    assert res.accepted, res.rejections
    assert res.signals["candidate_seniority"] == "intern"


def test_junior_offer_is_penalised_not_rejected_for_a_lead():
    c = _candidate()
    junior = evaluate_match(c, _job("Assistant logistique junior"), parsed={}, company_name="")
    assert junior.accepted, junior.rejections
    assert junior.breakdown["seniority"]["ratio"] < 1.0


def test_reconversion_ignores_past_seniority():
    c = _candidate(matching_criteria={"job_families": ["education"]})
    res = evaluate_match(c, _job("Professeur des écoles junior"), parsed={}, company_name="")
    assert res.accepted, res.rejections
    assert res.signals["reconversion"] is True
    assert res.breakdown["seniority"]["ratio"] == 1.0


def test_offer_far_too_senior_is_still_rejected():
    c = _candidate(experience_years=0.5)
    res = evaluate_match(c, _job("Head of Logistics"), parsed={}, company_name="")
    assert not res.accepted


# ── Famille de métier ──────────────────────────────────────────────────────

def test_inferred_family_scores_but_does_not_filter():
    c = _candidate()
    criteria = MatchingCriteria.resolve(c)
    assert criteria.job_families == ["ops"] and criteria.job_families_inferred
    res = evaluate_match(c, _job("Infirmier de bloc"), parsed={}, company_name="")
    assert res.accepted, res.rejections
    assert res.breakdown["family"]["ratio"] == 0.0


def test_chosen_family_still_filters():
    c = _candidate(matching_criteria={"job_families": ["ops"]})
    criteria = MatchingCriteria.resolve(c)
    assert not criteria.job_families_inferred
    res = evaluate_match(c, _job("Infirmier de bloc"), parsed={}, company_name="")
    assert not res.accepted


def test_new_families_are_detected():
    assert detect_job_family("Conducteur de travaux BTP") == "construction"
    assert detect_job_family("Formateur bureautique") == "education"
    assert detect_job_family("Ingénieur transformateur électrique") != "education"


def test_new_families_have_naf_codes_and_labels():
    from app.agents.spontaneous import FAMILY_LABELS
    from app.agents.spontaneous.directory import NAF_BY_FAMILY
    for family in ("construction", "education"):
        assert family in FAMILY_LABELS and NAF_BY_FAMILY[family]


# ── Nom du candidat ────────────────────────────────────────────────────────

def test_placeholder_name_is_not_a_name():
    assert real_name(SimpleNamespace(full_name="Candidat")) is None
    assert real_name(SimpleNamespace(full_name="  ")) is None
    assert real_name(SimpleNamespace(full_name="Camille Martin")) == "Camille Martin"


def test_email_never_signed_with_placeholder():
    cand = SimpleNamespace(full_name="Candidat")
    body = _plain_text({"body": "Bonjour", "signature_name": "Candidat"}, cand, "Dev", "Acme")
    assert "Candidat" not in body
    body = _plain_text(None, cand, "Dev", "Acme")
    assert "Candidat" not in body


class _Result:
    def first(self):
        return None


class _Session:
    def __init__(self, candidate):
        self.candidate = candidate

    async def execute(self, *_a, **_k):
        return _Result()

    async def get(self, _model, _id):
        return self.candidate


def test_send_is_held_without_a_name():
    dispatch = SimpleNamespace(id=1, application_id=2, candidate_id=3, destination="rh@acme.fr")
    hold = asyncio.run(pre_send_check(_Session(SimpleNamespace(full_name="Candidat")), dispatch, None))
    assert isinstance(hold, Hold) and hold.status == DispatchStatus.AWAITING_APPROVAL
    assert "nom" in hold.reason


# ── CV scanné ──────────────────────────────────────────────────────────────

def test_scanned_cv_invents_nothing(monkeypatch):
    from app.agents.discovery import resume_parser

    monkeypatch.setattr(resume_parser, "extract_text_from_pdf", lambda _b: "")
    parsed = asyncio.run(resume_parser.parse_resume(b"%PDF-", "scan.pdf"))
    assert parsed.text_detected is False
    assert parsed.headline is None and parsed.skills == [] and parsed.full_name is None
