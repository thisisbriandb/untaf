"""Une alternante comptable recevait comptabilité, CRM, secrétariat médical… à 73-84 %."""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.agents.application.feasibility import same_offer_key, unique_offers
from app.agents.discovery.matching import CONTEXT_ONLY_CAP, evaluate_match
from app.agents.discovery.signals import (
    detect_job_family,
    school_spread_clues,
    training_org_evidence,
)
from app.models.candidate import Candidate
from app.models.job_posting import JobPosting


def _candidate(**kw) -> Candidate:
    base = dict(
        full_name="Camille Martin", email="camille@example.com", headline="Comptable", skills=[],
        experience_years=None, preferred_locations=["Paris"], preferred_remote_policies=["onsite"],
        preferred_contract_types=["alternance"], matching_criteria=None,
    )
    base.update(kw)
    return Candidate(**base)


def _job(title: str, **kw) -> JobPosting:
    base = dict(title=title, location="75000 Paris", description_raw="", tech_stack=[],
                first_seen_at=datetime.now(UTC))
    base.update(kw)
    return JobPosting(**base)


def _match(c, title, company="Agatha"):
    return evaluate_match(c, _job(title), parsed={}, company_name=company)


def test_secretariat_and_crm_are_recognised_families():
    assert detect_job_family("Assistant administratif (H/F) - Alternance") == "admin"
    assert detect_job_family("Secrétaire Médicale (H/F) - Alternance") == "admin"
    assert detect_job_family("Alternance - Chef.fe de projet CRM et fidélisation") == "marketing"
    # « administratif et comptable » reste de la comptabilité
    assert detect_job_family("Assistant administratif et comptable") == "finance"


def test_accountant_does_not_get_unrelated_jobs():
    c = _candidate()
    assert _match(c, "Comptable junior (H/F) - Alternance").accepted
    for title in ("Alternance - Chef.fe de projet CRM et fidélisation",
                  "Secrétaire Médicale (H/F) - Alternance"):
        res = _match(c, title)
        assert not res.accepted, (title, res.score)


def test_unidentifiable_offer_needs_a_link_with_the_profile():
    c = _candidate(headline="Chargée de communication")
    # métier non classable, aucun mot commun : écartée
    assert not _match(c, "Alternance - Coordinateur(trice) de dispositifs").accepted
    # métier non classable mais même mot de métier que le profil : gardée
    c2 = _candidate(headline="Coordinatrice événementielle")
    assert _match(c2, "Alternance - Coordinateur(trice) événementiel").accepted


def test_profile_without_job_or_skills_cannot_reach_a_confident_score():
    c = _candidate(headline="Étudiant")
    res = _match(c, "Assistant administratif (H/F) - Alternance")
    assert res.accepted
    assert res.score <= CONTEXT_ONLY_CAP and res.signals.get("context_only")


def test_ief2i_style_schools_are_recognised():
    assert training_org_evidence("IEF2I Education", "", None)[0] == "strong"
    assert training_org_evidence("Groupe Education Avenir", "", {"naf": "85.42Z"})[0] == "strong"
    # un éditeur scolaire est un vrai employeur
    assert training_org_evidence("Hachette Éducation", "", {"naf": "58.11Z"})[0] is None
    res = _match(_candidate(), "Comptable junior (H/F) - Alternance", company="IEF2I Education")
    assert not res.accepted


def test_same_offer_from_two_sources_is_shown_once():
    assert same_offer_key("Assistant administratif (H/F) - Alternance", "IEF2I Education") == \
        same_offer_key("Assistant Administratif - alternance", "IEF2I  Éducation")
    def job(title):
        return SimpleNamespace(title=title)

    rows = [(1, job("Comptable (H/F)"), "Agatha"), (2, job("Comptable"), "Agatha"),
            (3, job("Comptable"), "Autre")]
    assert [r[0] for r in unique_offers(rows)] == [1, 3]


def test_db_schools_are_recognised():
    for name in ("AUREIS FORMATION", "INATEC Business School", "CFA ALTERLINE", "ISEAH FORMATION",
                 "DIGITALYS FORMATION", "MY DIGITAL CAMPUS", "Diderot Education"):
        assert training_org_evidence(name, "", None)[0] == "strong", name


def test_employer_recruiting_apprentices_in_many_trades_is_a_school():
    titles = ["Comptable (H/F) - Alternance", "Secrétaire Médicale - Alternance",
              "Développeur web en alternance", "Commercial B2B - Alternance"]
    postings = [(t, "Groupe Avenir", "alternance") for t in titles]
    postings += [("Comptable - Alternance", "Agatha", "alternance"),
                 ("Commercial - Alternance", "Agatha", "alternance")]
    # un grand groupe qui publie surtout des CDI n'est pas une école
    postings += [(t.replace("Alternance", "CDI").replace("en alternance", "CDI"), "Orange", "cdi")
                 for t in titles * 2]
    postings += [(t, "Orange", "alternance") for t in titles]
    clues = school_spread_clues(postings)
    assert set(clues) == {"groupe avenir"}
    assert training_org_evidence("Groupe Avenir", "", None)[0] is None
    assert training_org_evidence("Groupe Avenir", "", None, clues["groupe avenir"])[0] == "strong"
    res = evaluate_match(_candidate(), _job("Comptable (H/F) - Alternance"), parsed={},
                         company_name="Groupe Avenir", school_clue=clues["groupe avenir"])
    assert not res.accepted


class _Rows:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row

    def all(self):
        return []


class _SchoolSession:
    def __init__(self, job):
        self.job = job

    async def execute(self, stmt, *_a, **_k):
        sql = str(stmt)
        if "companies.name" in sql and "application_dispatches" not in sql:
            return _Rows((self.job, "ief2i.fr", "IEF2I Education"))
        return _Rows(None)

    async def get(self, _model, _id):
        return SimpleNamespace(full_name="Camille Martin", signature_image=b"x")


def test_school_offer_is_never_sent_without_approval():
    import asyncio

    from app.agents.application.dispatcher import pre_send_check
    from app.models.dispatch import DispatchStatus

    job = _job("Comptable - Alternance", description_parsed={})
    app = SimpleNamespace(status=None, job_posting_id=1, metadata_json={})
    dispatch = SimpleNamespace(id=1, application_id=2, candidate_id=3, destination="x",
                               channel=None, approved_at=None)
    hold = asyncio.run(pre_send_check(_SchoolSession(job), dispatch, app))
    assert hold and hold.status == DispatchStatus.AWAITING_APPROVAL and "école" in hold.reason
