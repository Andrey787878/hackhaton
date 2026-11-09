from functools import lru_cache
from typing import Any, Literal

from sqlalchemy import URL

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


HS256_MIN_SECRET_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    postgres_db: str = Field(default="app", alias="POSTGRES_DB")
    postgres_user: str = Field(default="app", alias="POSTGRES_USER")
    postgres_password: str = Field(default="app", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="db", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT", ge=1)

    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8080, alias="APP_PORT", ge=1)

    jwt_secret: str = Field(
        ...,
        alias="JWT_SECRET",
        min_length=32,
    )
    jwt_algorithm: Literal["HS256"] = Field(
        default="HS256",
        alias="JWT_ALGORITHM",
    )
    refresh_token_pepper: str | None = Field(
        default=None,
        alias="REFRESH_TOKEN_PEPPER",
    )

    access_token_ttl_minutes: int = Field(
        default=15,
        alias="ACCESS_TOKEN_TTL_MINUTES",
        ge=1,
    )
    refresh_token_ttl_minutes: int = Field(
        default=10080,
        alias="REFRESH_TOKEN_TTL_MINUTES",
        ge=1,
    )
    max_active_sessions: int = Field(
        default=5,
        alias="MAX_ACTIVE_SESSIONS",
        ge=1,
    )

    minio_root_user: str = Field(..., alias="MINIO_ROOT_USER", min_length=3)
    minio_root_password: str = Field(..., alias="MINIO_ROOT_PASSWORD", min_length=16)
    s3_bucket: str = Field(default="hackhaton-submissions", alias="S3_BUCKET", pattern=r"^[a-z0-9][a-z0-9-]{2,62}$")

    @field_validator("refresh_token_pepper", mode="before")
    @classmethod
    def parse_refresh_token_pepper(cls, raw_value: Any) -> str | None:
        if raw_value is None:
            raise ValueError(
                "REFRESH_TOKEN_PEPPER должен быть задан. "
                "Этот секрет используется только для хеширования refresh token."
            )
        if isinstance(raw_value, str):
            value = raw_value.strip()
            if not value:
                raise ValueError("REFRESH_TOKEN_PEPPER не должен быть пустым.")
            if len(value) < 16:
                raise ValueError("REFRESH_TOKEN_PEPPER должен содержать минимум 16 символов.")
            return value
        raise TypeError("REFRESH_TOKEN_PEPPER должен быть строкой.")

    @model_validator(mode="after")
    def validate_refresh_hash_secret(self) -> "Settings":
        if self.refresh_token_pepper is None:
            raise ValueError(
                "REFRESH_TOKEN_PEPPER должен быть задан в окружении для запуска приложения."
            )
        return self

    @model_validator(mode="after")
    def validate_jwt_secret_strength(self) -> "Settings":
        secret_length_bytes = len(self.jwt_secret.encode("utf-8"))
        if secret_length_bytes < HS256_MIN_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET слишком короткий для HS256: "
                f"нужно минимум {HS256_MIN_SECRET_BYTES} байт."
            )
        return self

    @property
    def database_url(self) -> str:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def refresh_token_hash_secret(self) -> str:
        if self.refresh_token_pepper is None:
            raise ValueError(
                "Ошибка конфигурации: REFRESH_TOKEN_PEPPER должен быть задан "
                "и не может быть пустым."
            )
        return self.refresh_token_pepper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
