from app.services.auth_service import hash_password, verify_password


def test_hash_password_returns_string():
    hashed = hash_password("mysecretpassword")
    assert isinstance(hashed, str)
    assert len(hashed) > 20


def test_verify_password_correct():
    hashed = hash_password("correct-password")
    assert verify_password("correct-password", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False


def test_hash_is_not_plaintext():
    password = "mysecretpassword"
    hashed = hash_password(password)
    assert password not in hashed


def test_two_hashes_differ():
    hashed1 = hash_password("same-password")
    hashed2 = hash_password("same-password")
    assert hashed1 != hashed2
