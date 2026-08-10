"""
Hachage des mots de passe.

Argon2id — recommandation OWASP actuelle pour les nouvelles applications.
Contrairement à bcrypt, pas de troncature silencieuse à 72 octets.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHash):
        return False
