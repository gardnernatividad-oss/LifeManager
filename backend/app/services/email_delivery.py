from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import quote


@dataclass(frozen=True)
class VerificationEmail:
    recipient: str
    raw_token: str


class EmailDelivery(Protocol):
    def send_verification_email(self, message: VerificationEmail) -> None: ...


class DisabledEmailDelivery:
    """Safe default until an operational email provider is configured."""

    def send_verification_email(self, message: VerificationEmail) -> None:
        del message


@dataclass
class RecordingEmailDelivery:
    """Development/test adapter; never configured as the production default."""

    messages: list[VerificationEmail] = field(default_factory=list)

    def send_verification_email(self, message: VerificationEmail) -> None:
        self.messages.append(message)


def build_verification_url(*, frontend_base_url: str, raw_token: str) -> str:
    """Build the future frontend link without embedding identity information."""
    return (
        f"{frontend_base_url.rstrip('/')}/verificar-correo"
        f"?token={quote(raw_token, safe='')}"
    )


email_delivery: EmailDelivery = DisabledEmailDelivery()
