import uuid

from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy.orm import Session

from app.api.v2.dependencies import (
    require_active_workspace_membership,
    require_workspace_owner,
)
from app.api.v2.errors import V2APIError
from app.models import User, Workspace, WorkspaceMember
from app.models.enums import AccountStatus, MembershipStatus, WorkspaceKind
from app.services.v2_workspace import (
    WorkspaceAccess,
    WorkspaceAccessNotFoundError,
)


def _access(*, owner: bool) -> WorkspaceAccess:
    account_id = uuid.uuid4()
    owner_id = account_id if owner else uuid.uuid4()
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Familia",
        kind=WorkspaceKind.SHARED,
        owner_user_id=owner_id,
    )
    membership = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=account_id,
        status=MembershipStatus.ACTIVE,
    )
    return WorkspaceAccess(workspace, membership)


def test_dependency_maps_hidden_workspace_to_404() -> None:
    db = MagicMock(spec=Session)
    account = User(
        id=uuid.uuid4(),
        email="member@example.com",
        hashed_password="hash",
        first_name="Ana",
        last_name="Pérez",
        account_status=AccountStatus.ACTIVE,
    )
    with patch(
        "app.api.v2.dependencies.resolve_active_workspace_access",
        side_effect=WorkspaceAccessNotFoundError("Workspace not found"),
    ):
        with pytest.raises(V2APIError) as captured:
            require_active_workspace_membership(uuid.uuid4(), db, account)

    assert captured.value.status_code == 404
    assert captured.value.code == "WORKSPACE_NOT_FOUND"


def test_owner_dependency_derives_authority_server_side() -> None:
    assert require_workspace_owner(_access(owner=True)).is_owner

    with pytest.raises(V2APIError) as captured:
        require_workspace_owner(_access(owner=False))
    assert captured.value.status_code == 403
    assert captured.value.code == "WORKSPACE_OWNER_REQUIRED"
