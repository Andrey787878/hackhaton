from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ==================== ЛР2: Авторизация ====================
class LoginInputDTO(BaseModel):
    """Входные данные для логина."""

    model_config = ConfigDict(frozen=True)

    username: str
    password: str


class RegisterInputDTO(BaseModel):
    """Входные данные для регистрации."""

    model_config = ConfigDict(frozen=True)

    username: str
    email: str
    password: str
    birthday: date | None = None
    display_name: str | None = None


class RefreshInputDTO(BaseModel):
    """Входные данные для обновления токенов."""

    model_config = ConfigDict(frozen=True)

    refresh_token: str


# ==================== ЛР3: RBAC ====================
class RoleWriteDTO(BaseModel):
    """Входные данные для создания/обновления роли."""

    model_config = ConfigDict(frozen=True)

    name: str
    slug: str
    description: str | None


class RoleUpdateDTO(BaseModel):
    """Входные данные для частичного обновления роли."""

    model_config = ConfigDict(frozen=True)

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    has_name: bool = False
    has_slug: bool = False
    has_description: bool = False


class PermissionWriteDTO(BaseModel):
    """Входные данные для создания/обновления разрешения."""

    model_config = ConfigDict(frozen=True)

    name: str
    slug: str
    description: str | None


class PermissionUpdateDTO(BaseModel):
    """Входные данные для частичного обновления разрешения."""

    model_config = ConfigDict(frozen=True)

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    has_name: bool = False
    has_slug: bool = False
    has_description: bool = False


class AttachUserRoleDTO(BaseModel):
    """Входные данные для назначения роли пользователю."""

    model_config = ConfigDict(frozen=True)

    role_id: int


class AttachRolePermissionDTO(BaseModel):
    """Входные данные для назначения разрешения роли."""

    model_config = ConfigDict(frozen=True)

    permission_id: int


class RoleDTO(BaseModel):
    """Публичные данные роли."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    slug: str
    description: str | None
    created_at: datetime
    created_by: int
    deleted_at: datetime | None
    deleted_by: int | None


class RoleCollectionDTO(BaseModel):
    """Коллекция ролей."""

    model_config = ConfigDict(frozen=True)

    items: list[RoleDTO]
    total: int = Field(ge=0)


class PermissionDTO(BaseModel):
    """Публичные данные разрешения."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    slug: str
    description: str | None
    created_at: datetime
    created_by: int
    deleted_at: datetime | None
    deleted_by: int | None


class PermissionCollectionDTO(BaseModel):
    """Коллекция разрешений."""

    model_config = ConfigDict(frozen=True)

    items: list[PermissionDTO]
    total: int = Field(ge=0)


# ==================== ЛР2: Авторизация (расширено ролями ЛР3) ====================
class UserDTO(BaseModel):
    """Публичные данные пользователя."""

    model_config = ConfigDict(frozen=True)

    id: int
    username: str
    email: str
    birthday: date | None = None
    display_name: str | None = None
    roles: list[RoleDTO] = Field(default_factory=list)


class AuthSuccessDTO(BaseModel):
    """Успешная авторизации."""

    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    user: UserDTO


class TokenMetaDTO(BaseModel):
    """Метаданные одной сессии."""

    model_config = ConfigDict(frozen=True)

    id: int
    created_at: datetime
    last_used_at: datetime | None
    access_expires_at: datetime
    refresh_expires_at: datetime
    ip: str | None
    user_agent: str | None
    revoked_at: datetime | None
    revoked_reason: str | None


class TokenListDTO(BaseModel):
    """Список сессий пользователя."""

    model_config = ConfigDict(frozen=True)

    items: list[TokenMetaDTO]


class MessageResponseDTO(BaseModel):
    """Сервисный ответ с результатом операции."""

    model_config = ConfigDict(frozen=True)

    message: str


class LogoutAllResponseDTO(BaseModel):
    """Выход везде."""

    model_config = ConfigDict(frozen=True)

    message: str
    revoked_count: int
