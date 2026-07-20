from fastapi import APIRouter, HTTPException, status

from app.api.v1.workspaces import SessionDependency
from app.schemas.user import UserCreate, UserRead
from app.services.user import register_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_in: UserCreate,
    db: SessionDependency,
) -> UserRead:
    try:
        user = register_user(db, user_in=user_in)
    except ValueError as error:
        if str(error) != "Email already registered":
            raise
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from error

    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)
