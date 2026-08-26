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
from app.schemas.v2_catalog import (
    CatalogItemCreate,
    CatalogItemListResponse,
    CatalogItemRead,
    CatalogItemUpdate,
    CatalogLifecycleUpdate,
    CatalogSelectorOption,
    CategoryCreate,
    CategoryListResponse,
    CategoryRead,
    CategoryUpdate,
)
from app.schemas.v2_task import TaskCreate, TaskListResponse, TaskRead, TaskUpdate, TaskVersionRequest

__all__ = [
    "CatalogItemCreate",
    "CatalogItemListResponse",
    "CatalogItemRead",
    "CatalogItemUpdate",
    "CatalogLifecycleUpdate",
    "CatalogSelectorOption",
    "CategoryCreate",
    "CategoryListResponse",
    "CategoryRead",
    "CategoryUpdate",
    "TaskCreate",
    "TaskListResponse",
    "TaskRead",
    "TaskUpdate",
    "TaskVersionRequest",
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
