import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet | None:
    key = get_settings().encryption_key
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        logger.warning("Invalid ENCRYPTION_KEY — access tokens will be stored plaintext")
        return None


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token. Returns ciphertext prefixed with 'enc:' or plaintext if no key."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    return "enc:" + f.encrypt(plaintext.encode()).decode()


def decrypt_token(stored: str) -> str:
    """Decrypt a token. Handles both encrypted ('enc:' prefix) and legacy plaintext."""
    if not stored:
        return stored
    if not stored.startswith("enc:"):
        return stored  # legacy plaintext
    f = _get_fernet()
    if f is None:
        logger.warning("ENCRYPTION_KEY not set but found encrypted token — cannot decrypt")
        return ""
    try:
        return f.decrypt(stored[4:].encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt token — key mismatch or corrupted data")
        return ""
