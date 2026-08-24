from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import quote


@dataclass(frozen=True)
class VerificationEmail:
    recipient: str
    raw_token: str


@dataclass(frozen=True)
class PasswordResetEmail:
    recipient: str
    raw_token: str


class EmailDelivery(Protocol):
    def send_verification_email(self, message: VerificationEmail) -> None: ...

    def send_password_reset_email(self, message: PasswordResetEmail) -> None: ...


class DisabledEmailDelivery:
    """Safe default until an operational email provider is configured."""

    def send_verification_email(self, message: VerificationEmail) -> None:
        del message

    def send_password_reset_email(self, message: PasswordResetEmail) -> None:
        del message


@dataclass
class RecordingEmailDelivery:
    """Development/test adapter; never configured as the production default."""

    messages: list[VerificationEmail | PasswordResetEmail] = field(default_factory=list)

    def send_verification_email(self, message: VerificationEmail) -> None:
        self.messages.append(message)

    def send_password_reset_email(self, message: PasswordResetEmail) -> None:
        self.messages.append(message)


def build_verification_url(*, frontend_base_url: str, raw_token: str) -> str:
    """Build the future frontend link without embedding identity information."""
    return (
        f"{frontend_base_url.rstrip('/')}/verificar-correo"
        f"?token={quote(raw_token, safe='')}"
    )


def build_password_reset_url(*, frontend_base_url: str, raw_token: str) -> str:
    """Build the future reset link without embedding account information."""
    return (
        f"{frontend_base_url.rstrip('/')}/restablecer-contrasena"
        f"?token={quote(raw_token, safe='')}"
    )


email_delivery: EmailDelivery = DisabledEmailDelivery()
