from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth_service import AuthService
from app.db import get_db
from app.models import AuthSession, Permission, PermissionRole, Role, User, UserRole
from app.rbac_service import RbacService
from app.schemas import RegisterRequest
from app.token_service import (
    AccessTokenPayload,
    TokenDecodeError,
    TokenHeaderError,
    TokenService,
)


@dataclass(frozen=True)
class CurrentUserContext:
    user_id: int
    access_jti: str
    session_id: int
    payload: AccessTokenPayload


class PermissionDeniedError(Exception):
    """Исключение отказа в доступе по RBAC-permission."""

    def __init__(self, permission_slug: str) -> None:
        self.permission_slug = permission_slug
        super().__init__(f"Access denied. Required permission: {permission_slug}")


_HTTP_BEARER = HTTPBearer(auto_error=False)


def get_token_service() -> TokenService:
    return TokenService()


def get_auth_service(
    db: Session = Depends(get_db),
    token_service: TokenService = Depends(get_token_service),
) -> AuthService:
    return AuthService(db=db, token_service=token_service)


def get_rbac_service(db: Session = Depends(get_db)) -> RbacService:
    """Создаёт RBAC-сервис в рамках текущей DB-сессии запроса."""
    return RbacService(db=db)


def validate_register_request_unique(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> RegisterRequest:
    """Проверяет уникальность username/email до вызова сервиса регистрации."""
    username = payload.username.strip()
    email = payload.email.strip()
    errors: list[dict[str, object]] = []

    try:
        username_exists = (
            db.scalar(select(User.id).where(func.lower(User.username) == username.lower())) is not None
        )
        if username_exists:
            errors.append(
                {
                    "type": "value_error",
                    "loc": ["body", "username"],
                    "msg": "username уже используется.",
                    "input": payload.username,
                }
            )

        email_exists = (
            db.scalar(select(User.id).where(func.lower(User.email) == email.lower())) is not None
        )
        if email_exists:
            errors.append(
                {
                    "type": "value_error",
                    "loc": ["body", "email"],
                    "msg": "email уже используется.",
                    "input": payload.email,
                }
            )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка доступа к данным. Повторите попытку позже.",
        ) from exc

    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=errors)

    return payload


def ensure_guest_only(
    request: Request,
    token_service: TokenService = Depends(get_token_service),
    db: Session = Depends(get_db),
) -> None:
    authorization = request.headers.get("Authorization")
    if authorization is None or not authorization.strip():
        return

    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return

    try:
        header = token_service.parse_jwt_header(token.strip())
        token_service.validate_jwt_header(header)
        payload = token_service.decode_access_token(token.strip())
    except (TokenHeaderError, TokenDecodeError):
        return

    try:
        session = db.scalar(select(AuthSession).where(AuthSession.access_jti == payload.jti))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка доступа к данным. Повторите попытку позже.",
        ) from exc
    if session is None or session.user_id != payload.sub:
        return

    now = datetime.now(timezone.utc)
    if session.revoked_at is not None or session.refresh_expires_at <= now:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Маршрут доступен только неавторизованным пользователям.",
    )


def _extract_bearer_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    """Извлекает Bearer token из security credentials."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Отсутствует заголовок Authorization.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.scheme.lower() != "bearer" or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ожидается формат Authorization: Bearer <token>.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials.strip()


def get_current_access_payload(
    credentials: HTTPAuthorizationCredentials | None = Security(_HTTP_BEARER),
    token_service: TokenService = Depends(get_token_service),
) -> AccessTokenPayload:
    """Проверяет Bearer access token и возвращает декодированный payload."""
    token = _extract_bearer_token(credentials)

    try:
        header = token_service.parse_jwt_header(token)
        token_service.validate_jwt_header(header)
        return token_service.decode_access_token(token)
    except (TokenHeaderError, TokenDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user_context(
    payload: AccessTokenPayload = Depends(get_current_access_payload),
    db: Session = Depends(get_db),
) -> CurrentUserContext:
    """Проверяет server-side состояние сессии и возвращает контекст пользователя."""
    try:
        session = db.scalar(select(AuthSession).where(AuthSession.access_jti == payload.jti))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка доступа к данным. Повторите попытку позже.",
        ) from exc
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия для access token не найдена.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if session.user_id != payload.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token не соответствует пользователю сессии.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Текущая сессия отозвана.",
        )

    now = datetime.now(timezone.utc)
    if session.refresh_expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Сессия истекла.",
        )

    return CurrentUserContext(
        user_id=session.user_id,
        access_jti=session.access_jti,
        session_id=session.id,
        payload=payload,
    )


def require_permission(permission_slug: str):
    """Фабрика dependency для проверки RBAC-permission по slug."""

    def _dependency(
        context: CurrentUserContext = Depends(get_current_user_context),
        db: Session = Depends(get_db),
    ) -> None:
        stmt = (
            select(Permission.id)
            .join(PermissionRole, PermissionRole.permission_id == Permission.id)
            .join(Role, Role.id == PermissionRole.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == context.user_id,
                UserRole.deleted_at.is_(None),
                Role.deleted_at.is_(None),
                PermissionRole.deleted_at.is_(None),
                Permission.deleted_at.is_(None),
                func.lower(Permission.slug) == permission_slug.lower(),
            )
            .limit(1)
        )

        try:
            has_permission = db.scalar(stmt) is not None
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Временная ошибка доступа к данным. Повторите попытку позже.",
            ) from exc

        if not has_permission:
            raise PermissionDeniedError(permission_slug=permission_slug)

    return _dependency
