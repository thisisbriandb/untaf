"""Une lettre ne part pas avec des affirmations que le parcours ne prouve pas."""

import asyncio
import json

from app.agents.discovery import fact_check
from app.agents.discovery.cover_letter import _strip_headings
from app.agents.discovery.fact_check import checked, unknown_numbers

FACTS = """PARCOURS
- Data analyst (stage) — Leroy Merlin (2026-01 → 2026-06)
    · Tableaux de bord Power BI de suivi des ventes pour 12 magasins
    · Automatisation d'un reporting hebdomadaire en Python (pandas), 4 h gagnées par semaine"""

GOOD = ("Chez Leroy Merlin, j'ai construit des tableaux de bord Power BI de suivi des ventes pour 12 "
        "magasins et automatisé un reporting hebdomadaire en Python, avec 4 h gagnées par semaine. "
        "Ces réalisations répondent directement aux missions décrites dans votre annonce.")
BAD = GOOD + " Ces tableaux de bord ont été adoptés par les managers de 30 magasins."


def test_nombre_absent_des_donnees():
    assert unknown_numbers(GOOD, FACTS) == []
    assert unknown_numbers(BAD, FACTS) == ["30"]


def _fake_generate(replies, seen):
    async def generate(prompt, **kwargs):
        seen.append(prompt)
        return json.dumps(replies.pop(0))
    return generate


def test_lettre_prouvee_inchangee(monkeypatch):
    seen = []
    monkeypatch.setattr(fact_check.llm, "generate", _fake_generate([{"unsupported": []}], seen))
    body, doubts = asyncio.run(checked(GOOD, FACTS))
    assert body == GOOD and doubts == [] and len(seen) == 1


def test_passage_non_prouve_reecrit_puis_relu(monkeypatch):
    seen = []
    replies = [
        {"unsupported": [{"quote": "ont été adoptés par les managers", "why": "non dit"}]},
        {"body": GOOD},
        {"unsupported": []},
    ]
    monkeypatch.setattr(fact_check.llm, "generate", _fake_generate(replies, seen))
    body, doubts = asyncio.run(checked(BAD, FACTS))
    assert body == GOOD and doubts == []
    # La consigne de correction cite le passage et le nombre douteux.
    assert "adoptés par les managers" in seen[1] and "« 30 »" in seen[1]


def test_doute_restant_rendu_a_l_appelant(monkeypatch):
    replies = [
        {"unsupported": [{"quote": "adoptés par les managers", "why": "non dit"}]},
        {"body": BAD},
        {"unsupported": [{"quote": "adoptés par les managers", "why": "non dit"}]},
    ]
    monkeypatch.setattr(fact_check.llm, "generate", _fake_generate(replies, []))
    _, doubts = asyncio.run(checked(BAD, FACTS))
    assert "adoptés par les managers" in doubts


def test_citation_inventee_par_le_relecteur_ignoree(monkeypatch):
    replies = [{"unsupported": [{"quote": "je suis passionnée de voile", "why": "?"}]}]
    monkeypatch.setattr(fact_check.llm, "generate", _fake_generate(replies, []))
    body, doubts = asyncio.run(checked(GOOD, FACTS))
    assert body == GOOD and doubts == []


def test_relecture_en_panne_signalee(monkeypatch):
    async def down(*a, **k):
        raise RuntimeError("quota")
    monkeypatch.setattr(fact_check.llm, "generate", down)
    body, doubts = asyncio.run(checked(GOOD, FACTS))
    assert body == GOOD and doubts == ["relecture des faits impossible"]


def test_titres_en_gras_retires():
    assert _strip_headings("**Accroche**\n\nBonjour.\n\n**Correspondances avec le poste**\n- a") == "Bonjour.\n\n- a"
    assert _strip_headings("Un **mot** en gras reste.") == "Un **mot** en gras reste."
