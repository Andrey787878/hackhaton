import re
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.dto import (
    AttachRolePermissionDTO,
    AttachUserRoleDTO,
    LoginInputDTO,
    PermissionUpdateDTO,
    PermissionWriteDTO,
    RefreshInputDTO,
    RegisterInputDTO,
    RoleUpdateDTO,
    RoleWriteDTO,
)


USERNAME_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
BIRTHDAY_FORMAT_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_REGEX = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_username(value: str) -> str:
    if not USERNAME_REGEX.fullmatch(value):
        raise ValueError(
            "username: от 3 до 64 латинских букв, цифр, дефисов или подчёркиваний; "
            "первый символ — буква или цифра."
        )
    return value


def _validate_non_blank(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} не должен быть пустым.")
    return value


def _validate_required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} не должен быть пустым.")
    return normalized


def _validate_slug(value: str, field_name: str = "slug") -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} не должен быть пустым.")
    if not SLUG_REGEX.fullmatch(normalized):
        raise ValueError(
            f"{field_name} должен содержать только латинские буквы, цифры, дефис и подчёркивание."
        )
    return normalized


def _normalize_optional_description(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    return normalized


def _validate_password_complexity(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("password должен занимать не более 72 байт UTF-8.")
    if len(value) < 8:
        raise ValueError("password должен содержать минимум 8 символов.")
    if not any(char.isdigit() for char in value):
        raise ValueError("password должен содержать минимум одну цифру.")
    if not any(char.islower() for char in value):
        raise ValueError("password должен содержать минимум один символ в нижнем регистре.")
    if not any(char.isupper() for char in value):
        raise ValueError("password должен содержать минимум один символ в верхнем регистре.")
    if not any(not char.isalnum() for char in value):
        raise ValueError("password должен содержать минимум один специальный символ.")
    return value


def _validate_birthday(value: date | None) -> date | None:
    if value is not None and value > date.today():
        raise ValueError("birthday не может быть в будущем.")
    return value


# ==================== ЛР2: Авторизация ====================
class LoginRequest(BaseModel):
    """Логин"""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _validate_username(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_complexity(value)

    def to_dto(self) -> LoginInputDTO:
        return LoginInputDTO(
            username=self.username,
            password=self.password,
        )


class RegisterRequest(BaseModel):
    """Регистрация"""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    c_password: str = Field(..., min_length=8, max_length=128)
    birthday: date | None = None
    display_name: str | None = Field(default=None, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _validate_username(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_complexity(value)

    @field_validator("birthday", mode="before")
    @classmethod
    def validate_birthday_format(cls, value: Any) -> Any:
        if isinstance(value, str) and not BIRTHDAY_FORMAT_REGEX.fullmatch(value):
            raise ValueError("birthday должен быть в формате YYYY-MM-DD.")
        return value

    @field_validator("birthday")
    @classmethod
    def validate_birthday_age(cls, value: date | None) -> date | None:
        return _validate_birthday(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return _normalize_optional_description(value)

    @model_validator(mode="after")
    def validate_password_match(self) -> "RegisterRequest":
        if self.password != self.c_password:
            raise ValueError("c_password должен совпадать с password.")
        return self

    def to_dto(self) -> RegisterInputDTO:
        return RegisterInputDTO(
            username=self.username,
            email=self.email,
            password=self.password,
            birthday=self.birthday,
            display_name=self.display_name,
        )


class ProfileUpdateRequest(BaseModel):
    """Изменение только собственного имени и даты рождения."""

    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, max_length=128)
    birthday: date | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return _normalize_optional_description(value)

    @field_validator("birthday")
    @classmethod
    def validate_birthday(cls, value: date | None) -> date | None:
        return _validate_birthday(value)

    @model_validator(mode="after")
    def validate_not_empty(self) -> "ProfileUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Передайте display_name или birthday.")
        return self


class RefreshRequest(BaseModel):
    """Обновления пары токенов"""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1)

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, value: str) -> str:
        return _validate_non_blank(value, "refresh_token").strip()

    def to_dto(self) -> RefreshInputDTO:
        return RefreshInputDTO(refresh_token=self.refresh_token)


# ==================== ЛР3: RBAC ====================
class StoreRoleRequest(BaseModel):
    """Запрос на создание роли."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=128)
    slug: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_required_text(value, "name")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        return _validate_slug(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _normalize_optional_description(value)

    def to_dto(self) -> RoleWriteDTO:
        return RoleWriteDTO(
            name=self.name,
            slug=self.slug,
            description=self.description,
        )


class UpdateRoleRequest(BaseModel):
    """Запрос на обновление роли."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_required_text(value, "name")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_slug(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _normalize_optional_description(value)

    @model_validator(mode="after")
    def validate_not_empty_payload(self) -> "UpdateRoleRequest":
        if not self.model_fields_set:
            raise ValueError("Хотя бы одно поле для обновления должно быть передано.")
        return self

    def to_dto(self) -> RoleUpdateDTO:
        return RoleUpdateDTO(
            name=self.name,
            slug=self.slug,
            description=self.description,
            has_name="name" in self.model_fields_set,
            has_slug="slug" in self.model_fields_set,
            has_description="description" in self.model_fields_set,
        )


class StorePermissionRequest(BaseModel):
    """Запрос на создание разрешения."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=128)
    slug: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_required_text(value, "name")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        return _validate_slug(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _normalize_optional_description(value)

    def to_dto(self) -> PermissionWriteDTO:
        return PermissionWriteDTO(
            name=self.name,
            slug=self.slug,
            description=self.description,
        )


class UpdatePermissionRequest(BaseModel):
    """Запрос на обновление разрешения."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_required_text(value, "name")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_slug(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return _normalize_optional_description(value)

    @model_validator(mode="after")
    def validate_not_empty_payload(self) -> "UpdatePermissionRequest":
        if not self.model_fields_set:
            raise ValueError("Хотя бы одно поле для обновления должно быть передано.")
        return self

    def to_dto(self) -> PermissionUpdateDTO:
        return PermissionUpdateDTO(
            name=self.name,
            slug=self.slug,
            description=self.description,
            has_name="name" in self.model_fields_set,
            has_slug="slug" in self.model_fields_set,
            has_description="description" in self.model_fields_set,
        )


class AttachUserRoleRequest(BaseModel):
    """Запрос на назначение роли пользователю."""

    model_config = ConfigDict(extra="forbid")

    role_id: int = Field(..., ge=1)

    def to_dto(self) -> AttachUserRoleDTO:
        return AttachUserRoleDTO(role_id=self.role_id)


class AttachRolePermissionRequest(BaseModel):
    """Запрос на назначение разрешения роли."""

    model_config = ConfigDict(extra="forbid")

    permission_id: int = Field(..., ge=1)

    def to_dto(self) -> AttachRolePermissionDTO:
        return AttachRolePermissionDTO(permission_id=self.permission_id)
