import uuid

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, MasterTask
from app.schemas.master_task import MasterTaskCreate, MasterTaskUpdate
from app.services.master_task_service import (
    MasterTaskCategoryNotFoundError,
    MasterTaskInUseError,
    MasterTaskNameConflictError,
    MasterTaskNotFoundError,
    create_master_task,
    delete_master_task,
    list_master_tasks,
    update_master_task,
)


def _db() -> MagicMock:
    return MagicMock(spec=Session)


def _category(workspace_id: uuid.UUID) -> Category:
    return Category(
        id=uuid.uuid4(), workspace_id=workspace_id, name="Salud", normalized_name="salud"
    )


def _master_task(workspace_id: uuid.UUID, category: Category) -> MasterTask:
    return MasterTask(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        category_id=category.id,
        category=category,
        name="Salir a correr",
        normalized_name="salir a correr",
    )


def test_create_master_task_uses_scoped_category_and_normalized_name() -> None:
    db = _db()
    workspace_id = uuid.uuid4()
    category = _category(workspace_id)
    db.scalar.side_effect = [category, None]
    result = create_master_task(
        db,
        workspace_id=workspace_id,
        master_task_in=MasterTaskCreate(name="  SALIR   A CORRER ", category_id=category.id),
    )
    assert result.workspace_id == workspace_id
    assert result.category is category
    assert result.name == "SALIR A CORRER"
    assert result.normalized_name == "salir a correr"
    db.add.assert_called_once_with(result)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()


def test_create_rejects_foreign_or_missing_category() -> None:
    db = _db()
    db.scalar.return_value = None
    with pytest.raises(MasterTaskCategoryNotFoundError):
        create_master_task(
            db,
            workspace_id=uuid.uuid4(),
            master_task_in=MasterTaskCreate(name="Leer", category_id=uuid.uuid4()),
        )
    db.add.assert_not_called()


def test_master_task_duplicate_and_unique_race_are_conflicts() -> None:
    workspace_id = uuid.uuid4()
    category = _category(workspace_id)
    db = _db()
    db.scalar.side_effect = [category, uuid.uuid4()]
    with pytest.raises(MasterTaskNameConflictError):
        create_master_task(
            db,
            workspace_id=workspace_id,
            master_task_in=MasterTaskCreate(name="Leer", category_id=category.id),
        )

    race_db = _db()
    race_db.scalar.side_effect = [category, None]
    original = MagicMock()
    original.diag.constraint_name = "uq_master_tasks_workspace_id_normalized_name"
    race_db.flush.side_effect = IntegrityError("insert", {}, original)
    with pytest.raises(MasterTaskNameConflictError):
        create_master_task(
            race_db,
            workspace_id=workspace_id,
            master_task_in=MasterTaskCreate(name="Leer", category_id=category.id),
        )


def test_list_master_tasks_filters_category_and_returns_eager_category() -> None:
    db = _db()
    workspace_id = uuid.uuid4()
    category = _category(workspace_id)
    row = _master_task(workspace_id, category)
    db.scalar.side_effect = [category, 1]
    db.scalars.return_value.all.return_value = [row]
    items, total = list_master_tasks(
        db,
        workspace_id=workspace_id,
        page=1,
        page_size=25,
        category_id=category.id,
    )
    assert items == [row]
    assert total == 1
    statement = db.scalars.call_args.args[0]
    parameters = statement.compile().params.values()
    assert workspace_id in parameters
    assert category.id in parameters


def test_update_unused_master_task_name_and_category() -> None:
    workspace_id = uuid.uuid4()
    old_category = _category(workspace_id)
    new_category = _category(workspace_id)
    master_task = _master_task(workspace_id, old_category)
    db = _db()
    db.scalar.side_effect = [master_task, False, None, new_category]
    result = update_master_task(
        db,
        workspace_id=workspace_id,
        master_task_id=master_task.id,
        master_task_in=MasterTaskUpdate(name="  Leer  ", category_id=new_category.id),
    )
    assert result.name == "Leer"
    assert result.normalized_name == "leer"
    assert result.category is new_category
    assert result.category_id == new_category.id
    master_lookup = db.scalar.call_args_list[0].args[0]
    category_lookup = db.scalar.call_args_list[3].args[0]
    assert master_lookup._for_update_arg is not None
    assert category_lookup._for_update_arg is not None
    db.flush.assert_called_once_with()


@pytest.mark.parametrize("changes", [{"name": "Nuevo"}, {"category_id": uuid.uuid4()}])
def test_used_master_task_rejects_name_or_category_change(changes: dict[str, object]) -> None:
    workspace_id = uuid.uuid4()
    category = _category(workspace_id)
    master_task = _master_task(workspace_id, category)
    db = _db()
    db.scalar.side_effect = [master_task, True]
    with pytest.raises(MasterTaskInUseError):
        update_master_task(
            db,
            workspace_id=workspace_id,
            master_task_id=master_task.id,
            master_task_in=MasterTaskUpdate.model_validate(changes),
        )
    db.flush.assert_not_called()


def test_delete_unused_and_reject_delete_used_master_task() -> None:
    workspace_id = uuid.uuid4()
    category = _category(workspace_id)
    master_task = _master_task(workspace_id, category)
    db = _db()
    db.scalar.side_effect = [master_task, False]
    delete_master_task(db, workspace_id=workspace_id, master_task_id=master_task.id)
    db.delete.assert_called_once_with(master_task)
    db.flush.assert_called_once_with()

    used_db = _db()
    used_db.scalar.side_effect = [master_task, True]
    with pytest.raises(MasterTaskInUseError):
        delete_master_task(used_db, workspace_id=workspace_id, master_task_id=master_task.id)


def test_master_task_from_another_workspace_is_not_exposed() -> None:
    db = _db()
    db.scalar.return_value = None
    with pytest.raises(MasterTaskNotFoundError):
        delete_master_task(db, workspace_id=uuid.uuid4(), master_task_id=uuid.uuid4())
