"""Authoritative LifeManager V2 schema exports.

Legacy V1 schema modules remain in the repository as transition references but
are intentionally not imported from the package root.
"""

from app.schemas.v2_identity import (
    AdminAccountSummary,
    AdminRegistrationList,
    RegistrationRequestCreate,
    RegistrationRequestAcknowledgement,
    RejectAccountRequest,
)

__all__ = [
    "AdminAccountSummary",
    "AdminRegistrationList",
    "RegistrationRequestCreate",
    "RegistrationRequestAcknowledgement",
    "RejectAccountRequest",
]
