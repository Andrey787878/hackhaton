from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError

from app.auth_service import (
    AuthService,
    AuthPersistenceError,
    AuthServiceError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenCompromisedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.dependencies import (
    CurrentUserContext,
    ensure_guest_only,
    get_auth_service,
    get_current_user_context,
    validate_register_request_unique,
)
from app.dto import (
    AuthSuccessDTO,
    LogoutAllResponseDTO,
    MessageResponseDTO,
    TokenListDTO,
    UserDTO,
)
from app.schemas import LoginRequest, ProfileUpdateRequest, RefreshRequest, RegisterRequest
from app.token_service import TokenServiceError


router = APIRouter(prefix="/auth", tags=["auth"])
_ResultT = TypeVar("_ResultT")


def _raise_http_for_auth_error(
    error: AuthServiceError | TokenServiceError | ValueError | SQLAlchemyError,
) -> NoReturn:
    """Преобразует доменные исключения auth-сервисов в HTTPException."""
    if isinstance(error, UserAlreadyExistsError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    if isinstance(error, InvalidCredentialsError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))
    if isinstance(error, InvalidRefreshTokenError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))
    if isinstance(error, RefreshTokenCompromisedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, AuthPersistenceError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка сохранения данных. Повторите попытку позже.",
        )
    if isinstance(error, SQLAlchemyError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка доступа к данным. Повторите попытку позже.",
        )
    if isinstance(error, UserNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, TokenServiceError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))
    if isinstance(error, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
    if isinstance(error, AuthServiceError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Внутренняя ошибка авторизации.",
    ) from error


def _call_auth(fn: Callable[[], _ResultT]) -> _ResultT:
    """Выполняет auth-операцию и преобразует доменные ошибки в HTTPException."""
    try:
        return fn()
    except (AuthServiceError, TokenServiceError, ValueError, SQLAlchemyError) as exc:
        _raise_http_for_auth_error(exc)


@router.post(
    "/register",
    response_model=UserDTO,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ensure_guest_only)],
)
def register(
    payload: RegisterRequest = Depends(validate_register_request_unique),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserDTO:
    """Регистрирует нового пользователя."""
    return _call_auth(lambda: auth_service.register_user(payload.to_dto()))


@router.post("/login", response_model=AuthSuccessDTO, status_code=status.HTTP_200_OK)
def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSuccessDTO:
    """Аутентифицирует пользователя и выдает access/refresh токены."""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    data = payload.to_dto()
    return _call_auth(
        lambda: auth_service.login_user(
            username=data.username,
            password=data.password,
            ip=ip,
            user_agent=user_agent,
        )
    )


@router.get("/me", response_model=UserDTO, status_code=status.HTTP_200_OK)
def me(
    context: CurrentUserContext = Depends(get_current_user_context),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserDTO:
    """Возвращает данные текущего авторизованного пользователя."""
    return _call_auth(lambda: auth_service.get_current_user(context.user_id))


@router.patch("/me", response_model=UserDTO)
def update_me(
    payload: ProfileUpdateRequest,
    context: CurrentUserContext = Depends(get_current_user_context),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserDTO:
    """Изменить свой профиль. Роли, логин и email через этот метод не меняются."""
    return _call_auth(lambda: auth_service.update_profile(
        context.user_id, payload.model_dump(exclude_unset=True),
    ))


@router.post("/out", response_model=MessageResponseDTO, status_code=status.HTTP_200_OK)
def out(
    context: CurrentUserContext = Depends(get_current_user_context),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponseDTO:
    """Отзывает текущую server-side сессию пользователя."""
    revoked = _call_auth(
        lambda: auth_service.logout_current_session(
            user_id=context.user_id,
            access_jti=context.access_jti,
        )
    )

    if revoked:
        return MessageResponseDTO(message="Текущая сессия отозвана.")
    return MessageResponseDTO(message="Сессия уже была неактивна.")


@router.get("/tokens", response_model=TokenListDTO, status_code=status.HTTP_200_OK)
def tokens(
    context: CurrentUserContext = Depends(get_current_user_context),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenListDTO:
    """Возвращает список активных server-side сессий пользователя."""
    return _call_auth(lambda: auth_service.list_active_sessions(context.user_id))


@router.post("/out_all", response_model=LogoutAllResponseDTO, status_code=status.HTTP_200_OK)
def out_all(
    context: CurrentUserContext = Depends(get_current_user_context),
    auth_service: AuthService = Depends(get_auth_service),
) -> LogoutAllResponseDTO:
    """Отзывает все активные сессии текущего пользователя."""
    revoked_count = _call_auth(lambda: auth_service.logout_all_sessions(context.user_id))

    return LogoutAllResponseDTO(
        message="Все активные сессии пользователя отозваны.",
        revoked_count=revoked_count,
    )


@router.post("/refresh", response_model=AuthSuccessDTO, status_code=status.HTTP_200_OK)
def refresh(
    payload: RefreshRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSuccessDTO:
    """Выполняет refresh-rotation и выдает новую пару токенов."""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    data = payload.to_dto()
    return _call_auth(
        lambda: auth_service.refresh_tokens(
            raw_refresh_token=data.refresh_token,
            ip=ip,
            user_agent=user_agent,
        )
    )
