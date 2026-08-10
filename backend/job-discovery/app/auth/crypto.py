"""
Chiffrement réversible des identifiants SMTP de chaque candidat.

À ne pas confondre avec `security.py` : un mot de passe de connexion est
haché (jamais retrouvable), un mot de passe d'application Gmail doit être
déchiffré pour se connecter réellement au serveur SMTP — Fernet (AES 128,
authentifié) est le choix standard pour ce cas précis.

La clé vit dans `CREDENTIALS_ENCRYPTION_KEY` (.env), jamais en base : la
perdre rend tous les identifiants stockés définitivement illisibles, la
divulguer permet de tous les déchiffrer. Elle ne doit jamais être commitée.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_fernet: Fernet | None = None


def _client() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.credentials_encryption_key:
            raise RuntimeError(
                "CREDENTIALS_ENCRYPTION_KEY absente — impossible de chiffrer/"
                "déchiffrer des identifiants. Générer une clé avec "
                "`python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\"`."
            )
        _fernet = Fernet(settings.credentials_encryption_key.encode())
    return _fernet


def encrypt(plaintext: str) -> str:
    return _client().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str | None:
    try:
        return _client().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None
