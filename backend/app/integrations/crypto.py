"""Authenticated encryption. Key is deployment-managed and never persisted here."""
from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings
from ..imports.models import ImportProblem


def cipher():
    key = get_settings().integration_encryption_key
    if key is None:
        raise ImportProblem("Gmail requires a server-managed encryption key", 503)
    try:
        return Fernet(key.get_secret_value().encode("ascii"))
    except (ValueError, UnicodeError):
        raise ImportProblem("Gmail encryption key is invalid", 503) from None


def encrypt(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt(value):
    try:
        return cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, UnicodeError, AttributeError):
        raise ImportProblem("Gmail credentials cannot be decrypted; restore the configured key or disconnect", 503) from None
