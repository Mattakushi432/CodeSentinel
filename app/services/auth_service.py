import bcrypt

_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    if len(password.encode()) > _MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must not exceed {_MAX_PASSWORD_BYTES} characters")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
