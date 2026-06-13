from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key)


def generate_magic_token(email: str) -> str:
    return _serializer().dumps(email, salt="magic-link")


def verify_magic_token(token: str) -> str | None:
    """Returns email if valid, None if expired/invalid."""
    settings = get_settings()
    try:
        email = _serializer().loads(token, salt="magic-link", max_age=settings.magic_link_expiry)
        return email
    except (SignatureExpired, BadSignature):
        return None
