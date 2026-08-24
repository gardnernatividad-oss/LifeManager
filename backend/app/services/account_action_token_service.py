import hashlib
import re
import secrets


ACTION_TOKEN_BYTES = 32
ACTION_TOKEN_LENGTH = 43
_ACTION_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def generate_action_token() -> str:
    raw_token = secrets.token_urlsafe(ACTION_TOKEN_BYTES)
    if len(raw_token) != ACTION_TOKEN_LENGTH:
        raise RuntimeError("Unexpected action-token length")
    return raw_token


def digest_action_token(raw_token: str) -> bytes:
    return hashlib.sha256(raw_token.encode("ascii")).digest()


def is_well_formed_action_token(raw_token: str) -> bool:
    return _ACTION_TOKEN_PATTERN.fullmatch(raw_token) is not None

