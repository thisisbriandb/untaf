import base64
import hashlib
import hmac
import time
import uuid

from app.agents import inbox
from app.agents.inbox import (
    Candidacy, Incoming, Piece, Reading, auto_status, best_match, cap_attachments, classify_by_rules,
    html_to_text, incoming_from_generic, new_token, next_status, read_message, token_from, verify_svix,
)
from app.models.application import ApplicationStatus as S


def test_token_is_readable_and_random():
    a, b = new_token("Camille Éléonore Martin"), new_token("Camille Éléonore Martin")
    assert a.startswith("camille.eleonore.martin.") and a != b
    assert new_token("").startswith("candidat.")


def test_token_from_only_our_domain(monkeypatch):
    monkeypatch.setattr(inbox.settings, "inbound_domain", "reponses.alice-agent.fr")
    assert token_from(["rh@acme.fr", "Camille <Camille.Martin.k7f2q@Reponses.Alice-Agent.fr>"]) == "camille.martin.k7f2q"
    assert token_from(["camille.martin.k7f2q+x@reponses.alice-agent.fr"]) == "camille.martin.k7f2q"
    assert token_from(["camille@autre.fr"]) is None


def _sign(secret_raw: bytes, msg_id: str, ts: str, body: bytes) -> str:
    sig = base64.b64encode(hmac.new(secret_raw, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest())
    return f"v1,{sig.decode()}"


def test_svix_signature():
    raw = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(raw).decode()
    ts = str(int(time.time()))
    body = b'{"type":"email.received"}'
    good = _sign(raw, "msg_1", ts, body)
    assert verify_svix(secret, "msg_1", ts, body, f"v1,AAAA {good}")
    assert not verify_svix(secret, "msg_1", ts, body + b" ", good)
    assert not verify_svix(secret, "msg_1", str(int(time.time()) - 3600), body, good)
    assert not verify_svix("", "msg_1", ts, body, good)


def test_rules():
    assert classify_by_rules("Votre candidature", "Malheureusement nous ne pouvons pas donner suite.") == "rejection"
    assert classify_by_rules("Entretien", "Pourriez-vous nous indiquer vos disponibilités pour un entretien ?") == "interview"
    assert classify_by_rules("Merci", "Nous avons bien reçu votre candidature.") == "acknowledgement"
    assert classify_by_rules("Test", "Merci de compléter ce test technique.") == "request"
    assert classify_by_rules("Bonjour", "Rien de particulier.") == "other"


def _c(company, domain, title, status=S.APPLIED):
    return Candidacy(uuid.uuid4(), company, domain, title, status)


def test_match_by_sender_domain_and_text():
    doctolib = _c("DOCTOLIB", "doctolib.com", "Développeuse Python")
    alan = _c("Alan", "alan.com", "Data Engineer")
    msg = Incoming("x", "Julie <julie@rh.doctolib.fr>", ["t@r.fr"], "Votre candidature", "Bonjour Camille…")
    best, sure = best_match([alan, doctolib], msg)
    assert best is doctolib and sure

    # Depuis un ATS : le nom de l'entreprise et le poste dans le texte.
    msg = Incoming("y", "no-reply@greenhouse.io", ["t@r.fr"], "Alan — Data Engineer", "Merci pour ta candidature chez Alan.")
    best, _ = best_match([doctolib, alan], msg)
    assert best is alan

    msg = Incoming("z", "x@gmail.com", ["t@r.fr"], "Bonjour", "Une question.")
    assert best_match([doctolib, alan], msg) == (None, False)


def test_status_never_goes_backwards():
    assert next_status(S.APPLIED, "interview") == S.INTERVIEW
    assert next_status(S.OFFER, "interview") is None
    assert next_status(S.INTERVIEW, "rejection") == S.REJECTED
    assert next_status(S.REJECTED, "rejection") is None
    assert next_status(S.APPLIED, "acknowledgement") is None


def test_generic_payload_and_html():
    msg = incoming_from_generic({"from": "RH <rh@acme.fr>", "to": "camille.x@r.fr",
                                 "subject": "Entretien", "html": "<p>Bonjour&nbsp;Camille</p><p>À bientôt</p>"})
    assert msg.from_email == "rh@acme.fr" and msg.from_name == "RH"
    assert msg.text.startswith("Bonjour") and "À bientôt" in msg.text
    assert incoming_from_generic({"from": "", "to": "a@b.c"}) is None
    assert html_to_text("<style>x{}</style>a<br>b") == "a\nb"


def test_raw_mime_from_cloudflare_worker():
    raw = (
        "From: =?utf-8?q?H=C3=A9l=C3=A8ne?= <helene@blablacar.fr>\r\n"
        "To: Recrutement <jobs@blablacar.fr>\r\n"
        "Subject: =?utf-8?q?Entretien_=E2=80=94_Ing=C3=A9nieure?=\r\n"
        "Message-ID: <abc@blablacar.fr>\r\n"
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/mixed; boundary="b"\r\n\r\n'
        "--b\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: 8bit\r\n\r\n"
        "Bonjour Camille, êtes-vous disponible jeudi ?\r\n"
        "--b\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename=\"fiche.pdf\"\r\n"
        "Content-Transfer-Encoding: base64\r\n\r\nJVBERi0=\r\n--b--\r\n"
    ).encode()
    msg = incoming_from_generic({
        "raw": base64.b64encode(raw).decode(),
        "from": "bounce@blablacar.fr",
        "to": "camille.martin.k7f2q@reponses.alice-agent.fr",  # enveloppe : copie cachée
    })
    assert msg.from_email == "helene@blablacar.fr" and msg.from_name == "Hélène"
    assert msg.subject == "Entretien — Ingénieure"
    assert msg.text.startswith("Bonjour Camille, êtes-vous disponible")
    assert msg.provider_id == "relay:<abc@blablacar.fr>"
    assert [(p.filename, p.mime, p.content) for p in msg.attachments] == [("fiche.pdf", "application/pdf", b"%PDF-")]
    assert msg.to[0] == "camille.martin.k7f2q@reponses.alice-agent.fr"
    assert incoming_from_generic({"raw": "pas du base64 !!", "to": "a@b.c"}) is None


# ── Rattachement incertain : aucun statut ne bouge ─────────────────────────


def _reading(kind, by_rules=False):
    r = Reading(kind=kind, summary="…")
    r._by_rules = by_rules
    return r


def test_two_jobs_same_company_is_not_sure():
    a = _c("Doctolib", "doctolib.com", "Développeuse Python")
    b = _c("Doctolib", "doctolib.com", "Product Manager")
    msg = Incoming("x", "rh@doctolib.com", ["t@r.fr"], "Votre candidature", "Malheureusement…")
    best, sure = best_match([a, b], msg)
    assert best in (a, b) and not sure
    # L'intitulé du poste les départage : sûr.
    msg = Incoming("y", "rh@doctolib.com", ["t@r.fr"], "Candidature Développeuse Python", "Malheureusement…")
    assert best_match([a, b], msg) == (a, True)


def test_exact_contact_address_is_sure():
    a = _c("Cabinet Martin", "", "Comptable")
    a.contact = "Recrutement@cabinet-martin.fr"
    b = _c("Autre", "", "Comptable")
    msg = Incoming("x", "recrutement@cabinet-martin.fr", ["t@r.fr"], "Re: candidature", "Bonjour")
    assert best_match([a, b], msg) == (a, True)


def test_name_in_text_is_only_a_suggestion():
    alan = _c("Alan", "alan.com", "Data Engineer")
    other = _c("Doctolib", "doctolib.com", "Data Engineer")
    msg = Incoming("y", "no-reply@greenhouse.io", ["t@r.fr"], "Alan — Data Engineer", "Malheureusement chez Alan…")
    best, sure = best_match([other, alan], msg)
    assert best is alan and not sure


def test_uncertain_match_changes_no_status():
    assert auto_status(S.APPLIED, _reading("rejection"), sure=False) is None
    assert auto_status(S.INTERVIEW, _reading("offer"), sure=False) is None


def test_confident_match_changes_status():
    assert auto_status(S.APPLIED, _reading("rejection"), sure=True) == S.REJECTED
    assert auto_status(S.APPLIED, _reading("interview"), sure=True) == S.INTERVIEW


def test_without_ai_no_status_changes(monkeypatch):
    async def down(*a, **k):
        raise RuntimeError("modèle indisponible")

    monkeypatch.setattr("app.llm.generate", down)
    import asyncio

    msg = Incoming("x", "rh@acme.fr", ["t@r.fr"], "Jeudi", "Malheureusement je ne suis pas dispo jeudi.")
    reading = asyncio.run(read_message(msg, [], None))
    assert reading.by_rules and reading.kind == "rejection"
    assert auto_status(S.APPLIED, reading, sure=True) is None


# ── Pièces jointes ─────────────────────────────────────────────────────────


def _multipart(parts: list[tuple[str, str, bytes]], inline_logo: bool = False) -> bytes:
    out = (
        "From: RH <rh@acme.fr>\r\nTo: camille.x@reponses.alice-agent.fr\r\nSubject: Offre\r\n"
        'MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary="b"\r\n\r\n'
        "--b\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nVoici notre proposition.\r\n"
    )
    for name, mime, data in parts:
        out += (f'--b\r\nContent-Type: {mime}\r\nContent-Disposition: attachment; filename="{name}"\r\n'
                f"Content-Transfer-Encoding: base64\r\n\r\n{base64.b64encode(data).decode()}\r\n")
    if inline_logo:
        out += ("--b\r\nContent-Type: image/png\r\nContent-ID: <logo>\r\nContent-Disposition: inline\r\n"
                f"Content-Transfer-Encoding: base64\r\n\r\n{base64.b64encode(b'png').decode()}\r\n")
    return (out + "--b--\r\n").encode()


def test_attachments_parsed_and_capped(monkeypatch):
    monkeypatch.setattr(inbox, "MAX_ATTACHMENT", 1000)
    monkeypatch.setattr(inbox, "MAX_ATTACHMENTS_TOTAL", 1500)
    raw = _multipart([
        ("offre.pdf", "application/pdf", b"%PDF" + b"a" * 796),   # 800 o : gardée
        ("test.zip", "application/zip", b"z" * 1200),             # > 1000 : trop lourde
        ("annexe.pdf", "application/pdf", b"b" * 800),            # dépasse le total : écartée
        ("note.txt", "text/plain", b"ok"),                        # tient encore
    ], inline_logo=True)
    msg = incoming_from_generic({"raw": base64.b64encode(raw).decode(), "to": "camille.x@reponses.alice-agent.fr"})
    assert [p.filename for p in msg.attachments] == ["offre.pdf", "test.zip", "annexe.pdf", "note.txt"]
    assert [p.filename for p in msg.kept] == ["offre.pdf", "note.txt"]
    assert msg.kept[0].content.startswith(b"%PDF") and msg.kept[0].mime == "application/pdf"
    assert [(p.filename, p.size) for p in msg.skipped] == [("test.zip", 1200), ("annexe.pdf", 800)]


def test_cap_counts_and_keeps_names():
    pieces = cap_attachments([Piece("a.pdf", content=b"x")] * 25 + [Piece("lien-mort.pdf", size=50)])
    assert len(pieces) == 26
    assert sum(p.content is not None for p in pieces) == inbox.MAX_ATTACHMENTS_COUNT
    assert pieces[-1].content is None and pieces[-1].size == 50


def test_generic_payload_with_base64_attachment():
    msg = incoming_from_generic({
        "from": "rh@acme.fr", "to": "camille.x@r.fr", "subject": "Test", "text": "Ci-joint",
        "attachments": [{"filename": "test.pdf", "content_type": "application/pdf",
                         "content": base64.b64encode(b"%PDF-1").decode()}, "ancien-format.doc"],
    })
    assert msg.kept[0].content == b"%PDF-1"
    assert msg.skipped[0].filename == "ancien-format.doc"


def test_forward_carries_attachments_then_retries_without(monkeypatch):
    import asyncio

    from app.agents.notifications import mailer
    from app.models.inbound_email import InboundEmail

    sent = []

    async def fake_send(mail):
        sent.append(mail)
        if mail.attachments:
            return {"ok": False, "real": False, "error": "type refusé"}
        return {"ok": True, "real": True}

    async def no_incident(*a, **k):
        return None

    monkeypatch.setattr(mailer, "send_mail", fake_send)
    monkeypatch.setattr("app.agents.incidents.report_incident", no_incident)
    record = InboundEmail(id=uuid.uuid4(), candidate_id=uuid.uuid4(), from_email="rh@acme.fr", from_name="RH",
                          subject="Offre", text="Voici.", kind="offer", summary="Acme te fait une offre.")
    pieces = [Piece("offre.pdf", "application/pdf", b"%PDF", 4), Piece("gros.zip", size=30_000_000)]
    assert asyncio.run(inbox.forward(record, "camille@gmail.com", "Camille", "Acme", None, pieces=pieces))
    assert [a.filename for a in sent[0].attachments] == ["offre.pdf"]
    assert not sent[1].attachments and "gros.zip" in sent[1].text and "offre.pdf" in sent[1].text
