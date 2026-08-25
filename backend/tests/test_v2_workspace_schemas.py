import uuid

import pytest

from pydantic import ValidationError

from app.models.enums import WorkspaceKind
from app.schemas.v2_workspace import SharedWorkspaceCreate, WorkspaceRead


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
