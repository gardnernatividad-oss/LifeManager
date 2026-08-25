import uuid

import pytest

from pydantic import ValidationError

from app.models.enums import WorkspaceKind, WorkspaceLifecycle
from app.schemas.v2_workspace import SharedWorkspaceCreate, WorkspaceRead, WorkspaceSummaryRead


def test_shared_workspace_create_cleans_unicode_name() -> None:
    value = SharedWorkspaceCreate(name="  Familia   Pérez  ")
    assert value.name == "Familia Pérez"


@pytest.mark.parametrize("name", ["", "   ", "Familia\nPérez", "A" * 151])
def test_shared_workspace_create_rejects_invalid_name(name: str) -> None:
    with pytest.raises(ValidationError):
        SharedWorkspaceCreate(name=name)


@pytest.mark.parametrize(
    "field",
    [
        "kind", "owner_user_id", "user_id", "status", "role",
        "global_role", "created_at", "updated_at", "lock_version",
        "members", "owner",
    ],
)
def test_shared_workspace_create_rejects_mass_assignment(field: str) -> None:
    with pytest.raises(ValidationError):
        SharedWorkspaceCreate.model_validate({"name": "Familia", field: "hostile"})


def test_workspace_read_is_allowlisted() -> None:
    result = WorkspaceRead(
        id=uuid.uuid4(),
        name="Familia",
        kind=WorkspaceKind.SHARED,
    )
    assert set(result.model_dump()) == {"id", "name", "kind"}


def test_workspace_summary_is_an_explicit_navigation_projection() -> None:
    result = WorkspaceSummaryRead(
        id=uuid.uuid4(), name="Personal", kind=WorkspaceKind.PERSONAL,
        lifecycle=WorkspaceLifecycle.ACTIVE, visible_role="Propietario",
        can_manage=False, can_delete=False, timezone="America/Lima",
    )
    assert set(result.model_dump()) == {
        "id", "name", "kind", "lifecycle", "visible_role",
        "can_manage", "can_delete", "timezone",
    }
    with pytest.raises(ValidationError):
        WorkspaceSummaryRead.model_validate({**result.model_dump(), "global_role": "GLOBAL_ADMIN"})
