import uuid

from datetime import datetime, timezone

import pytest

from pydantic import ValidationError

from app.models.enums import InvitationStatus
from app.schemas.v2_workspace_invitation import (
    WorkspaceInvitationCreate,
    WorkspaceInvitationRead,
)


def test_create_normalizes_email_and_forbids_privileged_fields() -> None:
    assert WorkspaceInvitationCreate(email=" USER@Example.COM ").email == "user@example.com"
    with pytest.raises(ValidationError):
        WorkspaceInvitationCreate(email="user@example.com", status="ACCEPTED")


def test_read_contract_exposes_no_token_or_user_internals() -> None:
    value = WorkspaceInvitationRead(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        workspace_name="Familia",
        recipient_email="user@example.com",
        status=InvitationStatus.PENDING,
        expires_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    assert set(value.model_dump()) == {
        "id", "workspace_id", "workspace_name", "recipient_email",
        "status", "expires_at", "created_at",
    }

