import uuid

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.category_service import (
    CategoryInUseError,
    CategoryNameConflictError,
    CategoryNotFoundError,
    create_category,
    delete_category,
    list_categories,
    update_category,
)


def _db() -> MagicMock:
    return MagicMock(spec=Session)


def test_create_category_cleans_and_normalizes_name_without_committing() -> None:
    db = _db()
    db.scalar.return_value = None
    workspace_id = uuid.uuid4()

    category = create_category(
        db,
        workspace_id=workspace_id,
        category_in=CategoryCreate(name="  TECNOLOGÍA  "),
    )

    assert category.workspace_id == workspace_id
    assert category.name == "TECNOLOGÍA"
    assert category.normalized_name == "tecnología"
    db.add.assert_called_once_with(category)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_category_normalization_detects_case_and_spacing_duplicates() -> None:
    db = _db()
    db.scalar.return_value = uuid.uuid4()
    with pytest.raises(CategoryNameConflictError):
        create_category(
            db,
            workspace_id=uuid.uuid4(),
            category_in=CategoryCreate(name=" trabajo   personal "),
        )
    db.add.assert_not_called()


def test_category_unique_race_is_translated_but_unrelated_integrity_error_is_not() -> None:
    db = _db()
    db.scalar.return_value = None
    original = MagicMock()
    original.diag.constraint_name = "uq_categories_workspace_id_normalized_name"
    db.flush.side_effect = IntegrityError("insert", {}, original)
    with pytest.raises(CategoryNameConflictError):
        create_category(db, workspace_id=uuid.uuid4(), category_in=CategoryCreate(name="Trabajo"))

    original.diag.constraint_name = "some_other_constraint"
    with pytest.raises(IntegrityError):
        create_category(db, workspace_id=uuid.uuid4(), category_in=CategoryCreate(name="Otro"))


def test_list_categories_is_scoped_ordered_and_paginated() -> None:
    db = _db()
    workspace_id = uuid.uuid4()
    rows = [Category(id=uuid.uuid4(), workspace_id=workspace_id, name="A", normalized_name="a")]
    db.scalar.return_value = 26
    db.scalars.return_value.all.return_value = rows

    items, total = list_categories(db, workspace_id=workspace_id, page=2, page_size=25)

    assert items == rows
    assert total == 26
    statement = db.scalars.call_args.args[0]
    assert statement._offset_clause.value == 25
    assert statement._limit_clause.value == 25
    assert workspace_id in statement.compile().params.values()
    db.commit.assert_not_called()


def test_update_unused_category_and_delete_unused_category() -> None:
    workspace_id = uuid.uuid4()
    category = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Trabajo", normalized_name="trabajo"
    )
    update_db = _db()
    update_db.scalar.side_effect = [category, False, None]
    result = update_category(
        update_db,
        workspace_id=workspace_id,
        category_id=category.id,
        category_in=CategoryUpdate(name="  Trabajo   Personal "),
    )
    assert result.name == "Trabajo Personal"
    assert result.normalized_name == "trabajo personal"
    category_lookup = update_db.scalar.call_args_list[0].args[0]
    assert category_lookup._for_update_arg is not None
    update_db.flush.assert_called_once_with()

    delete_db = _db()
    delete_db.scalar.side_effect = [category, False]
    delete_category(delete_db, workspace_id=workspace_id, category_id=category.id)
    delete_db.delete.assert_called_once_with(category)
    delete_db.flush.assert_called_once_with()


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_used_category_is_immutable(operation: str) -> None:
    workspace_id = uuid.uuid4()
    category = Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Trabajo", normalized_name="trabajo"
    )
    db = _db()
    db.scalar.side_effect = [category, True]
    with pytest.raises(CategoryInUseError):
        if operation == "update":
            update_category(
                db,
                workspace_id=workspace_id,
                category_id=category.id,
                category_in=CategoryUpdate(name="Nuevo"),
            )
        else:
            delete_category(db, workspace_id=workspace_id, category_id=category.id)
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_category_from_another_workspace_is_not_exposed() -> None:
    db = _db()
    db.scalar.return_value = None
    with pytest.raises(CategoryNotFoundError):
        update_category(
            db,
            workspace_id=uuid.uuid4(),
            category_id=uuid.uuid4(),
            category_in=CategoryUpdate(name="Nuevo"),
        )
    statement = db.scalar.call_args.args[0]
    assert len(statement.compile().params) == 2
