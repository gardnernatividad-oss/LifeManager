import uuid

import pytest
from pydantic import ValidationError

from app.schemas.v2_project import ProjectCreate, ProjectUpdate


def test_create_cleans_fields_and_forbids_internal_values() -> None:
    value = ProjectCreate(category_id=uuid.uuid4(), name="  Proyecto   familiar ", description="  Nota  ")
    assert value.name == "Proyecto familiar" and value.description == "Nota"
    with pytest.raises(ValidationError):
        ProjectCreate.model_validate({"category_id": str(uuid.uuid4()), "name": "X", "workspace_id": str(uuid.uuid4()), "progress": 50})


def test_update_is_partial_strict_and_allows_description_clear() -> None:
    assert ProjectUpdate(description=None, lock_version=1).description is None
    with pytest.raises(ValidationError):
        ProjectUpdate(lock_version=1)
    with pytest.raises(ValidationError):
        ProjectUpdate.model_validate({"name": None, "lock_version": 1})
    with pytest.raises(ValidationError):
        ProjectUpdate.model_validate({"name": "X", "lock_version": 1, "completion_date": "2026-09-01", "can_edit": True})
