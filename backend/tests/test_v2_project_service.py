import uuid

from unittest.mock import MagicMock, call

import pytest

from app.models import Category, Project, ProjectLeaderHistory, User, Workspace, WorkspaceMember
from app.models.enums import WorkspaceKind
from app.schemas.v2_project import ProjectCreate, ProjectUpdate
from app.services.v2_project import ProjectConflictError, create_project, deactivate_project, reactivate_project, update_project
from app.services.v2_workspace import WorkspaceAccess


def access(kind: WorkspaceKind = WorkspaceKind.SHARED) -> tuple[WorkspaceAccess, User]:
    actor = User(id=uuid.uuid4(), email="actor@test.local", first_name="Ana", last_name="Uno")
    workspace = Workspace(id=uuid.uuid4(), owner_user_id=actor.id, kind=kind, name="Casa")
    return WorkspaceAccess(workspace, WorkspaceMember(workspace_id=workspace.id, user_id=actor.id)), actor


def test_create_derives_workspace_creator_and_personal_leader() -> None:
    scope, actor = access(WorkspaceKind.PERSONAL)
    category = Category(id=uuid.uuid4(), workspace_id=scope.workspace.id, name="Casa", is_active=True)
    db = MagicMock()
    db.scalar.return_value = category
    db.execute.return_value.one_or_none.return_value = (actor, scope.membership)
    project = create_project(db, access=scope, actor=actor, project_in=ProjectCreate(category_id=category.id, leader_user_id=uuid.uuid4(), name="Mudanza"))
    assert project.workspace_id == scope.workspace.id and project.created_by_user_id == actor.id
    assert project.leader_user_id == actor.id and project.is_active is True
    assert isinstance(db.add.call_args_list[-1].args[0], ProjectLeaderHistory)
    db.flush.assert_has_calls([call(), call()]); db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_update_changes_leader_with_history_and_optimistic_version() -> None:
    scope, actor = access()
    target = User(id=uuid.uuid4(), email="target@test.local")
    project = Project(id=uuid.uuid4(), workspace_id=scope.workspace.id, category_id=uuid.uuid4(), leader_user_id=actor.id, name="Mudanza", created_by_user_id=actor.id, lock_version=3)
    db = MagicMock()
    db.scalar.return_value = project
    db.execute.return_value.one_or_none.return_value = (target, WorkspaceMember(workspace_id=scope.workspace.id, user_id=target.id))
    updated = update_project(db, access=scope, actor=actor, project_id=project.id, project_in=ProjectUpdate(leader_user_id=target.id, description="Nueva", lock_version=3))
    assert updated.leader_user_id == target.id and updated.description == "Nueva" and updated.lock_version == 4
    assert isinstance(db.add.call_args.args[0], ProjectLeaderHistory)
    db.commit.assert_not_called(); db.rollback.assert_not_called()


def test_lifecycle_is_separate_and_versioned() -> None:
    scope, actor = access()
    project = Project(id=uuid.uuid4(), workspace_id=scope.workspace.id, category_id=uuid.uuid4(), leader_user_id=actor.id, name="Mudanza", created_by_user_id=actor.id, is_active=True, lock_version=2)
    db = MagicMock(); db.scalar.return_value = project
    assert deactivate_project(db, access=scope, project_id=project.id, expected_version=2).is_active is False
    assert project.lock_version == 3
    assert reactivate_project(db, access=scope, project_id=project.id, expected_version=3).is_active is True
    with pytest.raises(ProjectConflictError):
        reactivate_project(db, access=scope, project_id=project.id, expected_version=4)
