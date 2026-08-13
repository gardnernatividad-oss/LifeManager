import uuid

import pytest
from pydantic import ValidationError

from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.master_task import MasterTaskCreate, MasterTaskUpdate
from app.core.names import normalize_name


def test_category_name_is_cleaned_and_normalized_length_is_validated() -> None:
    assert CategoryCreate(name="  Trabajo   Personal ").name == "Trabajo Personal"
    with pytest.raises(ValidationError):
        CategoryCreate(name="   ")
    with pytest.raises(ValidationError):
        CategoryCreate(name="x" * 101)


def test_category_schemas_reject_obsolete_and_protected_fields() -> None:
    with pytest.raises(ValidationError):
        CategoryCreate.model_validate({"name": "Trabajo", "description": "obsolete"})
    with pytest.raises(ValidationError):
        CategoryUpdate.model_validate({"name": None})
    with pytest.raises(ValidationError):
        CategoryUpdate.model_validate({"workspace_id": str(uuid.uuid4())})


def test_master_task_schema_requires_clean_name_and_category() -> None:
    category_id = uuid.uuid4()
    schema = MasterTaskCreate(name="  Salir   a correr ", category_id=category_id)
    assert schema.name == "Salir a correr"
    assert schema.category_id == category_id
    with pytest.raises(ValidationError):
        MasterTaskCreate(name=" ", category_id=category_id)
    with pytest.raises(ValidationError):
        MasterTaskCreate(name="x" * 151, category_id=category_id)


def test_master_task_update_is_strict_and_rejects_explicit_nulls() -> None:
    assert MasterTaskUpdate(name="Leer").model_dump(exclude_unset=True) == {"name": "Leer"}
    with pytest.raises(ValidationError):
        MasterTaskUpdate.model_validate({"category_id": None})
    with pytest.raises(ValidationError):
        MasterTaskUpdate.model_validate({"planned_date": "2026-01-01"})


def test_normalization_preserves_accents_and_uses_unicode_nfc_casefold() -> None:
    accented = normalize_name(" TECNOLOGÍA ", max_length=100, field_label="Category")
    unaccented = normalize_name("Tecnologia", max_length=100, field_label="Category")
    decomposed = normalize_name("Tecnologi\u0301a", max_length=100, field_label="Category")
    assert accented == ("TECNOLOGÍA", "tecnología")
    assert accented[1] != unaccented[1]
    assert decomposed[1] == "tecnología"
