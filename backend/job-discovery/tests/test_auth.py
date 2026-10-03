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
