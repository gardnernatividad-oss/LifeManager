from pwdlib import PasswordHash as _PasswordHash

__all__ = ["hash_password", "verify_password"]

_password_hash = _PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    try:
        return _password_hash.verify(plain_password, hashed_password)
    except Exception:
        return False
