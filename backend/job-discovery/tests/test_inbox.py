import base64
import hashlib
import hmac
import time
import uuid

from app.agents import inbox
from app.agents.inbox import (
    Candidacy, Incoming, best_match, classify_by_rules, html_to_text, incoming_from_generic,
    new_token, next_status, token_from, verify_svix,
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
    assert msg.attachments == ["fiche.pdf"]
    assert msg.to[0] == "camille.martin.k7f2q@reponses.alice-agent.fr"
    assert incoming_from_generic({"raw": "pas du base64 !!", "to": "a@b.c"}) is None
