from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dto import AuthSuccessDTO, RegisterInputDTO, RoleDTO, TokenListDTO, TokenMetaDTO, UserDTO
from app.models import AuthSession, Role, User, UserRole
from app.token_service import TokenService, TokenServiceError


class AuthServiceError(Exception):
    """Базовое исключение сервиса авторизации."""


class UserAlreadyExistsError(AuthServiceError):
    """Ошибка при попытке зарегистрировать уже существующего пользователя."""


class UserNotFoundError(AuthServiceError):
    """Пользователь не найден."""


class InvalidCredentialsError(AuthServiceError):
    """Неверные учетные данные при логине."""


class InvalidRefreshTokenError(AuthServiceError):
    """Передан невалидный refresh token."""


class RefreshTokenCompromisedError(AuthServiceError):
    """Выявлено повторное использование или компрометация refresh token."""


class AuthPersistenceError(AuthServiceError):
    """Ошибка сохранения/фиксации данных авторизации в БД."""


class AuthService:
    """Работает с пользователями, токенами и server-side сессиями."""

    def __init__(
        self,
        db: Session,
        token_service: TokenService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._token_service = token_service or TokenService(self._settings)

    def register_user(self, data: RegisterInputDTO) -> UserDTO:
        username = data.username.strip()
        email = data.email.strip()
        raw_password = data.password
        birthday = data.birthday

        existing_username = self._db.scalar(
            select(User.id).where(func.lower(User.username) == username.lower())
        )
        if existing_username is not None:
            raise UserAlreadyExistsError("Пользователь с такими данными уже существует.")

        existing_email = self._db.scalar(
            select(User.id).where(func.lower(User.email) == email.lower())
        )
        if existing_email is not None:
            raise UserAlreadyExistsError("Пользователь с такими данными уже существует.")

        password_hash = bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")

        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            birthday=birthday,
            display_name=data.display_name,
        )
        participant = self._db.scalar(select(Role).where(
            Role.slug == "participant", Role.deleted_at.is_(None),
        ))
        if participant is None:
            raise AuthPersistenceError("Роль участника отсутствует. Примените миграции.")
        self._db.add(user)
        try:
            self._db.flush()
        except IntegrityError as exc:
            self._db.rollback()
            raise UserAlreadyExistsError("Пользователь с такими данными уже существует.") from exc
        self._db.add(UserRole(user_id=user.id, role_id=participant.id, created_by=user.id))
        self._commit_or_rollback(
            integrity_error=UserAlreadyExistsError("Пользователь с такими данными уже существует.")
        )
        self._db.refresh(user)

        return self._to_user_dto(user)

    def login_user(
        self,
        username: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSuccessDTO:
        user = self._db.scalar(
            select(User).where(func.lower(User.username) == username.strip().lower())
        )
        if user is None:
            raise InvalidCredentialsError("Неверные учетные данные.")

        if not bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("ascii")):
            raise InvalidCredentialsError("Неверные учетные данные.")

        family_id = uuid4().hex
        _, access_token, refresh_token = self._create_session(
            user=user,
            family_id=family_id,
            ip=ip,
            user_agent=user_agent,
        )

        self._db.flush()
        self._enforce_session_limit(user.id)
        self._commit_or_rollback()

        return AuthSuccessDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            user=self._to_user_dto(user),
        )

    def get_current_user(self, user_id: int) -> UserDTO:
        user = self._db.get(User, user_id)
        if user is None:
            raise UserNotFoundError("Пользователь не найден.")

        return self._to_user_dto(user)

    def update_profile(self, user_id: int, changes: dict) -> UserDTO:
        if not changes or set(changes) - {"display_name", "birthday"}:
            raise ValueError("Разрешены только display_name и birthday.")
        user = self._db.get(User, user_id)
        if user is None:
            raise UserNotFoundError("Пользователь не найден.")
        for name, value in changes.items():
            setattr(user, name, value)
        self._commit_or_rollback()
        self._db.refresh(user)
        return self._to_user_dto(user)

    def list_active_sessions(self, user_id: int) -> TokenListDTO:
        self._require_user(user_id)
        now = self._now_utc()

        sessions = list(
            self._db.scalars(
                select(AuthSession)
                .where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                    AuthSession.refresh_expires_at > now,
                )
                .order_by(AuthSession.created_at.desc())
            )
        )

        items = [self._to_token_meta_dto(session) for session in sessions]
        return TokenListDTO(items=items)

    def logout_current_session(self, user_id: int, access_jti: str) -> bool:
        session = self._db.scalar(
            select(AuthSession).where(
                AuthSession.user_id == user_id,
                AuthSession.access_jti == access_jti,
            )
        )
        if session is None:
            return False

        was_revoked = self._revoke_session(session, reason="logout_current")
        if was_revoked:
            self._commit_or_rollback()

        return was_revoked

    def logout_all_sessions(self, user_id: int) -> int:
        revoked_count = self._revoke_all_user_sessions(user_id=user_id, reason="logout_all")
        if revoked_count > 0:
            self._commit_or_rollback()

        return revoked_count

    def refresh_tokens(
        self,
        raw_refresh_token: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuthSuccessDTO:
        normalized_refresh_token = raw_refresh_token.strip()
        if not normalized_refresh_token:
            raise InvalidRefreshTokenError("Refresh token не должен быть пустым.")

        try:
            refresh_payload = self._token_service.decode_refresh_token(
                normalized_refresh_token,
                verify_exp=False,
            )
        except TokenServiceError as exc:
            raise InvalidRefreshTokenError("Refresh token невалиден.") from exc

        locked_user_id = self._db.scalar(
            select(User.id).where(User.id == refresh_payload.sub).with_for_update()
        )
        if locked_user_id is None:
            raise UserNotFoundError("Пользователь для refresh token не найден.")

        now = self._now_utc()
        session = self._db.scalar(
            select(AuthSession)
            .where(
                AuthSession.user_id == refresh_payload.sub,
                AuthSession.access_jti == refresh_payload.access_jti,
            )
            .with_for_update()
        )
        if session is None:
            self._revoke_all_user_sessions(
                user_id=refresh_payload.sub,
                reason="refresh_session_not_found",
                revoked_at=now,
            )
            self._commit_or_rollback()
            raise RefreshTokenCompromisedError(
                "Refresh token недействителен или уже использован. Все сессии пользователя отозваны."
            )

        refresh_hash = self._token_service.hash_refresh_token(normalized_refresh_token)
        if (
            session.refresh_hash != refresh_hash
            or
            session.revoked_at is not None
            or session.refresh_used_at is not None
            or session.refresh_expires_at <= now
            or refresh_payload.exp <= now
        ):
            # Повторное использование refresh token = отзыв сессий
            self._revoke_all_user_sessions(
                user_id=session.user_id,
                reason="refresh_reuse_or_invalid",
                revoked_at=now,
            )
            self._commit_or_rollback()
            raise RefreshTokenCompromisedError(
                "Refresh token недействителен или уже использован. Все сессии пользователя отозваны."
            )

        user = self._db.get(User, session.user_id)
        if user is None:
            raise UserNotFoundError("Пользователь для refresh token не найден.")

        session.refresh_used_at = now
        session.last_used_at = now
        # После успешной ротации refresh старая сессия сразу отзывается
        self._revoke_session(session, reason="refresh_rotated", revoked_at=now)

        _, access_token, refresh_token = self._create_session(
            user=user,
            family_id=session.family_id,
            ip=ip,
            user_agent=user_agent,
            created_at=now,
        )

        self._db.flush()
        self._enforce_session_limit(user.id)
        self._commit_or_rollback()

        return AuthSuccessDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            user=self._to_user_dto(user),
        )

    def _create_session(
        self,
        user: User,
        family_id: str,
        ip: str | None,
        user_agent: str | None,
        created_at: datetime | None = None,
    ) -> tuple[AuthSession, str, str]:
        """Создает запись server-side сессии и возвращает пару токенов."""
        now = created_at or self._now_utc()
        access_jti = uuid4().hex

        access_token = self._token_service.create_access_token(user_id=user.id, jti=access_jti)
        access_payload = self._token_service.decode_access_token(access_token)

        refresh_token = self._token_service.create_refresh_token(
            user_id=user.id,
            access_jti=access_jti,
        )
        refresh_hash = self._token_service.hash_refresh_token(refresh_token)
        refresh_expires_at = now + timedelta(minutes=self._settings.refresh_token_ttl_minutes)
        validated_ip = self._validate_ip(ip)
        validated_user_agent = self._validate_user_agent(user_agent)

        # IP и User-Agent хранятся только на сервере как метаданные сессии, а не в JWT
        session = AuthSession(
            user_id=user.id,
            family_id=family_id,
            access_jti=access_jti,
            refresh_hash=refresh_hash,
            created_at=now,
            last_used_at=now,
            access_expires_at=access_payload.exp,
            refresh_expires_at=refresh_expires_at,
            ip=validated_ip,
            user_agent=validated_user_agent,
        )
        self._db.add(session)

        return session, access_token, refresh_token

    def _revoke_session(
        self,
        session: AuthSession,
        reason: str,
        revoked_at: datetime | None = None,
    ) -> bool:
        """Помечает одну сессию отозванной; если уже отозвана, ничего не делает."""
        if session.revoked_at is not None:
            return False

        now = revoked_at or self._now_utc()
        session.revoked_at = now
        session.revoked_reason = reason
        session.last_used_at = now
        return True

    def _revoke_all_user_sessions(
        self,
        user_id: int,
        reason: str,
        revoked_at: datetime | None = None,
    ) -> int:
        """Отзывает все неотозванные сессии пользователя."""
        now = revoked_at or self._now_utc()
        sessions = list(
            self._db.scalars(
                select(AuthSession).where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                )
            )
        )

        revoked_count = 0
        for session in sessions:
            if self._revoke_session(session, reason=reason, revoked_at=now):
                revoked_count += 1

        return revoked_count

    def _enforce_session_limit(self, user_id: int) -> None:
        """Соблюдает лимит активных сессий, отзывая самые старые при переполнении."""
        now = self._now_utc()
        self._db.scalar(
            select(User.id).where(User.id == user_id).with_for_update()
        )
        active_sessions = list(
            self._db.scalars(
                select(AuthSession)
                .where(
                    AuthSession.user_id == user_id,
                    AuthSession.revoked_at.is_(None),
                    AuthSession.refresh_expires_at > now,
                )
                .order_by(AuthSession.created_at.asc())
            )
        )

        overflow = len(active_sessions) - self._settings.max_active_sessions
        if overflow <= 0:
            return

        for session in active_sessions[:overflow]:
            self._revoke_session(session, reason="session_limit_exceeded", revoked_at=now)

    def _commit_or_rollback(self, integrity_error: AuthServiceError | None = None) -> None:
        """Фиксирует транзакцию и откатывает сессию при ошибке БД."""
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            if integrity_error is not None:
                raise integrity_error from exc
            raise AuthPersistenceError("Ошибка сохранения данных авторизации.") from exc
        except SQLAlchemyError as exc:
            self._db.rollback()
            raise AuthPersistenceError("Ошибка сохранения данных авторизации.") from exc

    def _require_user(self, user_id: int) -> User:
        """Возвращает пользователя по id или выбрасывает понятную ошибку."""
        user = self._db.get(User, user_id)
        if user is None:
            raise UserNotFoundError("Пользователь не найден.")
        return user

    @staticmethod
    def _to_user_dto(user: User) -> UserDTO:
        """Преобразует модель User в UserDTO."""
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            birthday=user.birthday,
            display_name=user.display_name,
            roles=[RoleDTO.model_validate(role, from_attributes=True)
                   for role in sorted(user.roles, key=lambda role: role.slug)],
        )

    @staticmethod
    def _to_token_meta_dto(session: AuthSession) -> TokenMetaDTO:
        """Преобразует модель AuthSession в безопасный DTO без секретных токенов."""
        return TokenMetaDTO(
            id=session.id,
            created_at=session.created_at,
            last_used_at=session.last_used_at,
            access_expires_at=session.access_expires_at,
            refresh_expires_at=session.refresh_expires_at,
            ip=session.ip,
            user_agent=session.user_agent,
            revoked_at=session.revoked_at,
            revoked_reason=session.revoked_reason,
        )

    @staticmethod
    def _now_utc() -> datetime:
        """Возвращает текущее время в UTC с timezone-aware datetime."""
        return datetime.now(timezone.utc)

    @staticmethod
    def _validate_ip(ip: str | None) -> str | None:
        """Проверяет, что значение IP является корректным IPv4/IPv6 адресом."""
        if ip is None:
            return None

        value = ip.strip()
        if not value:
            return None

        try:
            ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("IP адрес клиента невалиден.") from exc

        return value

    @staticmethod
    def _validate_user_agent(user_agent: str | None) -> str | None:
        """Нормализует User-Agent и отсекает явно подозрительные паттерны."""
        if user_agent is None:
            return None

        value = user_agent.strip()
        if not value:
            return None

        if len(value) > 512:
            raise ValueError("User-Agent не должен превышать 512 символов.")

        if any(char in value for char in ("\r", "\n", "\x00")):
            raise ValueError("User-Agent содержит недопустимые управляющие символы.")

        lower_value = value.lower()
        if "<script" in lower_value or "</script" in lower_value or "javascript:" in lower_value:
            raise ValueError("User-Agent содержит недопустимые script-конструкции.")

        return value
