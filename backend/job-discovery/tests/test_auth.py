"""Vérification des jetons Supabase et gardes d'accès — sans base."""

import asyncio
import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from app import auth
from app.config import settings

SECRET = "test-secret-with-enough-length-for-hs256-0123456789"


def _token(**overrides) -> str:
    claims = {"sub": str(uuid4()), "aud": "authenticated", "exp": int(time.time()) + 600,
              "email": "Ada@Example.fr"}
    claims.update(overrides)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _request(token: str | None):
    headers = {"authorization": f"Bearer {token}"} if token else {}
    return SimpleNamespace(headers=headers, path_params={})


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    monkeypatch.setattr(settings, "supabase_url", "")


def _user(token):
    return asyncio.run(auth.get_user(_request(token)))


def test_jeton_valide():
    user = _user(_token())
    assert user and user.email == "ada@example.fr"


def test_sans_jeton_pas_d_utilisateur_et_connexion_requise():
    assert _user(None) is None
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth.require_user(None))
    assert e.value.status_code == 401


@pytest.mark.parametrize("token", [
    lambda: _token(exp=int(time.time()) - 10),
    lambda: _token(aud="anon"),
    lambda: jwt.encode({"sub": str(uuid4()), "aud": "authenticated",
                        "exp": int(time.time()) + 60}, "autre-secret-" * 4, algorithm="HS256"),
    lambda: _token(sub="pas-un-uuid"),
    lambda: "n.importe.quoi",
])
def test_jetons_refuses(token):
    with pytest.raises(HTTPException) as e:
        _user(token())
    assert e.value.status_code == 401


def test_sans_configuration_on_refuse(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    with pytest.raises(HTTPException) as e:
        _user(_token())
    assert e.value.status_code == 503
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth.require_user(None))
    assert e.value.status_code == 503


def test_mode_developpement(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", True)
    assert _user(None) == auth.DEV_USER


def test_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "boss@untaf.fr")
    with pytest.raises(HTTPException):
        asyncio.run(auth.require_admin(auth.AuthUser(uuid4(), "ada@example.fr")))
    asyncio.run(auth.require_admin(auth.AuthUser(uuid4(), "boss@untaf.fr")))


def test_garde_sans_candidat_dans_le_chemin_ne_bloque_pas():
    asyncio.run(auth.guard_candidate_path(_request(None), None, db=None))


def test_cles_asymetriques_via_jwks(monkeypatch):
    """Nouvelles clés Supabase : ES256, vérifiées contre le JWKS du projet."""
    from cryptography.hazmat.primitives.asymmetric import ec

    private = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(settings, "supabase_url", "https://projet.supabase.co")
    monkeypatch.setattr(auth, "_jwks_client", lambda: SimpleNamespace(
        get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=private.public_key()),
    ))
    claims = {"sub": str(uuid4()), "aud": "authenticated", "exp": int(time.time()) + 600}
    assert _user(jwt.encode(claims, private, algorithm="ES256"))

    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(HTTPException):
        _user(jwt.encode(claims, other, algorithm="ES256"))


def test_session_maison_signee_par_l_api(monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", "un-secret-maison-assez-long-pour-hs256-0123456789")
    token, _ = auth.issue_session("Ada@Example.fr")
    user = _user(token)
    assert user.email == "ada@example.fr"
    assert user.id == auth.user_id_for("ada@example.fr")  # stable, sans table d'utilisateurs


def test_session_maison_refusee_si_secret_change(monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", "secret-un-assez-long-pour-hs256-0123456789abcdef")
    token, _ = auth.issue_session("ada@example.fr")
    monkeypatch.setattr(settings, "auth_secret", "secret-deux-assez-long-pour-hs256-0123456789abcd")
    with pytest.raises(HTTPException):
        _user(token)


def test_cors_autorise_le_site_de_frontend_url(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://untaf.vercel.app/")
    monkeypatch.setattr(settings, "frontend_url", "https://alice-agent.fr/")
    assert settings.cors_origin_list == [
        "https://untaf.vercel.app", "https://alice-agent.fr", "https://www.alice-agent.fr",
    ]


def test_lien_de_connexion_vers_le_site_demandeur_si_frontend_url_reste_local(monkeypatch):
    from types import SimpleNamespace
    from app.api.auth_routes import _frontend_base

    monkeypatch.setattr(settings, "frontend_url", "http://localhost:3000")
    monkeypatch.setattr(settings, "cors_origins", "https://alice-agent.fr")
    req = SimpleNamespace(headers={"origin": "https://alice-agent.fr"})
    assert _frontend_base(req) == "https://alice-agent.fr"
    # Une origine inconnue ne détourne jamais le lien.
    req = SimpleNamespace(headers={"origin": "https://pirate.example"})
    assert _frontend_base(req) == "http://localhost:3000"
    # FRONTEND_URL renseigné : il fait foi.
    monkeypatch.setattr(settings, "frontend_url", "https://alice-agent.fr")
    assert _frontend_base(SimpleNamespace(headers={})) == "https://alice-agent.fr"
