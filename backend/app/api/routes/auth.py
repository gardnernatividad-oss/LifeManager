from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, SessionDependency
from app.core.tokens import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.user import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    register_user,
    update_user_profile,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me", response_model=UserRead)
def get_authenticated_user(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
def update_authenticated_user(
    user_in: UserUpdate,
    db: SessionDependency,
    current_user: CurrentUser,
) -> UserRead:
    try:
        user = update_user_profile(db, user=current_user, user_in=user_in)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise
    return UserRead.model_validate(user)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    db: SessionDependency,
) -> UserRead:
    try:
        user = register_user(db, user_in=user_in)
        db.commit()
        db.refresh(user)
    except EmailAlreadyRegisteredError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from error
    except Exception:
        db.rollback()
        raise
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    db: SessionDependency,
) -> TokenResponse:
    user = authenticate_user(
        db,
        email=credentials.email,
        password=credentials.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=access_token)
