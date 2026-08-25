import uuid

import pytest

from pydantic import ValidationError

from app.schemas.v2_catalog import CategoryCreate, CategoryUpdate, CatalogItemCreate


def test_catalog_names_are_unicode_normalized_and_whitespace_collapsed() -> None:
    assert CategoryCreate(name="  TECNOLOGI\u0301A   Personal ").name == "TECNOLOGÍA Personal"


@pytest.mark.parametrize("name", ["", "   ", "Control\x00name"])
def test_catalog_rejects_blank_and_control_names(name: str) -> None:
    with pytest.raises(ValidationError):
        CategoryCreate(name=name)


def test_catalog_dtos_forbid_scope_and_internal_mass_assignment() -> None:
    with pytest.raises(ValidationError):
        CategoryCreate(name="Personal", workspace_id=uuid.uuid4(), normalized_name="personal")
    with pytest.raises(ValidationError):
        CatalogItemCreate(name="Leer", category_id=uuid.uuid4(), is_active=False)


def test_update_requires_explicit_expected_version_and_rejects_null_name() -> None:
    with pytest.raises(ValidationError):
        CategoryUpdate(name="Casa")
    with pytest.raises(ValidationError):
        CategoryUpdate(name=None, lock_version=1)
