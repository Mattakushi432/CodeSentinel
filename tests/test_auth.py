from app.services.auth_service import generate_magic_token, verify_magic_token


def test_magic_token_roundtrip():
    token = generate_magic_token("test@example.com")
    assert token
    email = verify_magic_token(token)
    assert email == "test@example.com"


def test_magic_token_invalid():
    result = verify_magic_token("not-a-valid-token")
    assert result is None


def test_magic_token_tampered():
    token = generate_magic_token("test@example.com")
    tampered = token[:-5] + "XXXXX"
    result = verify_magic_token(tampered)
    assert result is None
