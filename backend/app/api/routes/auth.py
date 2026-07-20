from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import SessionDependency
from app.core.tokens import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.user import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


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
