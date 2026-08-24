"""Authoritative LifeManager V2 schema exports.

Legacy V1 schema modules remain in the repository as transition references but
are intentionally not imported from the package root.
"""

from app.schemas.v2_identity import (
    AdminAccountSummary,
    AdminRegistrationList,
    EmailVerificationRequest,
    EmailVerificationResendRequest,
    EmailVerificationResponse,
    PasswordRecoveryRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    RegistrationRequestCreate,
    RegistrationRequestAcknowledgement,
    RejectAccountRequest,
)

__all__ = [
    "AdminAccountSummary",
    "AdminRegistrationList",
    "EmailVerificationRequest",
    "EmailVerificationResendRequest",
    "EmailVerificationResponse",
    "PasswordRecoveryRequest",
    "PasswordResetRequest",
    "PasswordResetResponse",
    "RegistrationRequestCreate",
    "RegistrationRequestAcknowledgement",
    "RejectAccountRequest",
]
