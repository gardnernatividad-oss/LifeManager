import json

from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest
from urllib.request import urlopen

from app.core.config import settings


TURNSTILE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class AntiBotVerificationFailed(Exception):
    pass


class AntiBotProviderUnavailable(Exception):
    pass


class AntiBotVerifier(Protocol):
    def verify(self, *, token: str, remote_ip: str) -> None: ...


@dataclass(frozen=True)
class CloudflareTurnstileVerifier:
    secret_key: str
    timeout_seconds: float = 5.0

    def verify(self, *, token: str, remote_ip: str) -> None:
        payload = urlencode(
            {
                "secret": self.secret_key,
                "response": token,
                "remoteip": remote_ip,
            }
        ).encode("ascii")
        request = URLRequest(
            TURNSTILE_SITEVERIFY_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                parsed = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            raise AntiBotProviderUnavailable from error

        if not isinstance(parsed, dict) or not isinstance(parsed.get("success"), bool):
            raise AntiBotProviderUnavailable
        if parsed["success"] is not True:
            raise AntiBotVerificationFailed
        for optional_text in ("hostname", "action", "challenge_ts"):
            if optional_text in parsed and not isinstance(parsed[optional_text], str):
                raise AntiBotProviderUnavailable


def configured_anti_bot_verifier() -> AntiBotVerifier | None:
    if not settings.TURNSTILE_ENABLED:
        return None
    if not settings.TURNSTILE_SECRET_KEY:
        raise AntiBotProviderUnavailable
    return CloudflareTurnstileVerifier(
        secret_key=settings.TURNSTILE_SECRET_KEY,
        timeout_seconds=settings.TURNSTILE_TIMEOUT_SECONDS,
    )


def verify_anti_bot_token(
    *,
    token: str | None,
    remote_ip: str,
    verifier: AntiBotVerifier | None = None,
) -> None:
    selected = verifier if verifier is not None else configured_anti_bot_verifier()
    if selected is None:
        return
    if token is None or not token.strip():
        raise AntiBotVerificationFailed
    selected.verify(token=token, remote_ip=remote_ip)
