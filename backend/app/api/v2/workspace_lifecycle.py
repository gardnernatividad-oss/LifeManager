import uuid

from fastapi import APIRouter, Response, status

from app.api.v2.dependencies import SessionDependency, UsableAccount, WorkspaceOwner
from app.api.v2.errors import V2APIError
from app.schemas.v2_workspace_lifecycle import (
    OwnershipTransferRequest,
    WorkspaceLifecycleRead,
)
from app.services.v2_workspace_lifecycle import (
    WorkspaceLifecycleConflictError,
    WorkspaceLifecycleNotFoundError,
    WorkspaceLifecyclePermissionError,
    deactivate_shared_workspace,
    get_workspace_lifecycle,
    hard_delete_shared_workspace,
    reactivate_shared_workspace,
    resolve_owned_shared_workspace,
    transfer_workspace_ownership,
)


router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["V2 Workspace Lifecycle"])


def _raise_domain_error(error: ValueError) -> None:
    if isinstance(error, WorkspaceLifecycleNotFoundError):
        raise V2APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="WORKSPACE_NOT_FOUND",
            message="No se encontró el espacio de trabajo.",
        ) from error
    if isinstance(error, WorkspaceLifecyclePermissionError):
        raise V2APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="WORKSPACE_OWNER_REQUIRED",
            message="Se requiere ser propietario del espacio de trabajo.",
        ) from error
    raise V2APIError(
        status_code=status.HTTP_409_CONFLICT,
        code="WORKSPACE_LIFECYCLE_CONFLICT",
        message="El espacio de trabajo no está disponible para esta acción.",
    ) from error


def _read(db: SessionDependency, access) -> WorkspaceLifecycleRead:
    workspace, can_delete = get_workspace_lifecycle(db, access=access)
    return WorkspaceLifecycleRead(
        id=workspace.id,
        name=workspace.name,
        kind=workspace.kind,
        lifecycle=workspace.lifecycle,
        deactivated_at=workspace.deactivated_at,
        can_delete=can_delete,
    )


@router.get("/lifecycle", response_model=WorkspaceLifecycleRead)
def read_lifecycle(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_account: UsableAccount,
) -> WorkspaceLifecycleRead:
    try:
        access = resolve_owned_shared_workspace(
            db, account=current_account, workspace_id=workspace_id
        )
    except WorkspaceLifecycleNotFoundError as error:
        _raise_domain_error(error)
    return _read(db, access)


@router.post("/transfer-ownership", response_model=WorkspaceLifecycleRead)
def transfer_ownership(
    workspace_id: uuid.UUID,
    transfer_in: OwnershipTransferRequest,
    db: SessionDependency,
    owner_access: WorkspaceOwner,
) -> WorkspaceLifecycleRead:
    del workspace_id
    try:
        transfer_workspace_ownership(
            db,
            owner_access=owner_access,
            target_user_id=transfer_in.target_user_id,
        )
        db.commit()
        db.refresh(owner_access.workspace)
    except (
        WorkspaceLifecycleConflictError,
        WorkspaceLifecycleNotFoundError,
        WorkspaceLifecyclePermissionError,
    ) as error:
        db.rollback()
        _raise_domain_error(error)
    except Exception:
        db.rollback()
        raise
    return _read(db, owner_access)


@router.post("/deactivate", response_model=WorkspaceLifecycleRead)
def deactivate_workspace(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    owner_access: WorkspaceOwner,
) -> WorkspaceLifecycleRead:
    del workspace_id
    try:
        deactivate_shared_workspace(db, owner_access=owner_access)
        db.commit()
        db.refresh(owner_access.workspace)
    except (WorkspaceLifecycleConflictError, WorkspaceLifecyclePermissionError) as error:
        db.rollback()
        _raise_domain_error(error)
    except Exception:
        db.rollback()
        raise
    return _read(db, owner_access)


@router.post("/reactivate", response_model=WorkspaceLifecycleRead)
def reactivate_workspace(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_account: UsableAccount,
) -> WorkspaceLifecycleRead:
    try:
        access = resolve_owned_shared_workspace(
            db, account=current_account, workspace_id=workspace_id
        )
        reactivate_shared_workspace(db, owner_access=access)
        db.commit()
        db.refresh(access.workspace)
    except (
        WorkspaceLifecycleConflictError,
        WorkspaceLifecycleNotFoundError,
        WorkspaceLifecyclePermissionError,
    ) as error:
        db.rollback()
        _raise_domain_error(error)
    except Exception:
        db.rollback()
        raise
    return _read(db, access)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: uuid.UUID,
    db: SessionDependency,
    current_account: UsableAccount,
) -> Response:
    try:
        access = resolve_owned_shared_workspace(
            db, account=current_account, workspace_id=workspace_id
        )
        hard_delete_shared_workspace(db, owner_access=access)
        db.commit()
    except (
        WorkspaceLifecycleConflictError,
        WorkspaceLifecycleNotFoundError,
        WorkspaceLifecyclePermissionError,
    ) as error:
        db.rollback()
        _raise_domain_error(error)
    except Exception:
        db.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
