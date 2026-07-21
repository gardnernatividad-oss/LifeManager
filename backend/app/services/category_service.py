import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.workspace import get_workspace_membership


class CategoryNotFoundError(LookupError):
    pass


class CategoryPermissionError(PermissionError):
    pass


class CategoryNameConflictError(ValueError):
    pass


def normalize_category_name(name: str) -> tuple[str, str]:
    cleaned_name = unicodedata.normalize("NFC", " ".join(name.split()))
    if not cleaned_name:
        raise ValueError("Category name cannot be blank")

    normalized_name = unicodedata.normalize("NFC", cleaned_name.casefold())
    if len(cleaned_name) > 100 or len(normalized_name) > 100:
        raise ValueError("Category name must not exceed 100 characters")
    return cleaned_name, normalized_name


def _require_membership(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
) -> WorkspaceMember:
    membership = get_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if membership is None:
        raise CategoryPermissionError("Workspace access denied")
    return membership


def _get_scoped_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
) -> Category:
    statement = select(Category).where(
        Category.id == category_id,
        Category.workspace_id == workspace_id,
    )
    category = db.scalar(statement)
    if category is None:
        raise CategoryNotFoundError("Category not found")
    return category


def _name_exists(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    normalized_name: str,
    exclude_category_id: uuid.UUID | None = None,
) -> bool:
    statement = select(Category.id).where(
        Category.workspace_id == workspace_id,
        Category.normalized_name == normalized_name,
    )
    if exclude_category_id is not None:
        statement = statement.where(Category.id != exclude_category_id)
    return db.scalar(statement) is not None


def _flush_or_raise_name_conflict(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as error:
        diagnostic = getattr(error.orig, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        if constraint_name != "uq_categories_workspace_id_normalized_name":
            raise
        raise CategoryNameConflictError("Category name already exists") from error


def create_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    category_in: CategoryCreate,
) -> Category:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    name, normalized_name = normalize_category_name(category_in.name)
    if _name_exists(
        db,
        workspace_id=workspace_id,
        normalized_name=normalized_name,
    ):
        raise CategoryNameConflictError("Category name already exists")

    category = Category(
        workspace_id=workspace_id,
        name=name,
        normalized_name=normalized_name,
        description=category_in.description,
        is_active=True,
    )
    db.add(category)
    _flush_or_raise_name_conflict(db)
    return category


def list_categories(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    current_user: User,
    active: bool | None = None,
) -> list[Category]:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    statement = select(Category).where(Category.workspace_id == workspace_id)
    if active is not None:
        statement = statement.where(Category.is_active.is_(active))
    statement = statement.order_by(
        Category.normalized_name,
        Category.name,
        Category.id,
    )
    return list(db.scalars(statement).all())


def get_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    current_user: User,
) -> Category:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    return _get_scoped_category(
        db,
        workspace_id=workspace_id,
        category_id=category_id,
    )


def update_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    current_user: User,
    category_in: CategoryUpdate,
) -> Category:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    category = _get_scoped_category(
        db,
        workspace_id=workspace_id,
        category_id=category_id,
    )
    changes = category_in.model_dump(exclude_unset=True)
    if "name" in changes:
        name, normalized_name = normalize_category_name(changes["name"])
        if normalized_name != category.normalized_name and _name_exists(
            db,
            workspace_id=workspace_id,
            normalized_name=normalized_name,
            exclude_category_id=category.id,
        ):
            raise CategoryNameConflictError("Category name already exists")
        category.name = name
        category.normalized_name = normalized_name
    if "description" in changes:
        category.description = changes["description"]

    _flush_or_raise_name_conflict(db)
    return category


def activate_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    current_user: User,
) -> Category:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    category = _get_scoped_category(
        db,
        workspace_id=workspace_id,
        category_id=category_id,
    )
    if not category.is_active:
        category.is_active = True
        db.flush()
    return category


def deactivate_category(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    current_user: User,
) -> Category:
    _require_membership(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    category = _get_scoped_category(
        db,
        workspace_id=workspace_id,
        category_id=category_id,
    )
    if category.is_active:
        category.is_active = False
        db.flush()
    return category
