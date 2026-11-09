from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Boolean, Numeric, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, and_, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Hackathon(Base):
    __tablename__ = "hackathons"
    id: Mapped[int] = mapped_column(primary_key=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    cases: Mapped[list[Case]] = relationship(back_populates="hackathon", cascade="all, delete-orphan", order_by="Case.id")
    __table_args__ = (CheckConstraint("deadline_at > starts_at", name="ck_hackathon_dates"),)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    hackathon_id: Mapped[int] = mapped_column(ForeignKey("hackathons.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    hackathon: Mapped[Hackathon] = relationship(back_populates="cases")
    criteria: Mapped[list[Criterion]] = relationship(back_populates="case", cascade="all, delete-orphan", order_by="Criterion.position")


class Criterion(Base):
    __tablename__ = "criteria"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    min_score: Mapped[int] = mapped_column()
    max_score: Mapped[int] = mapped_column()
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    position: Mapped[int] = mapped_column()
    case: Mapped[Case] = relationship(back_populates="criteria")
    __table_args__ = (
        CheckConstraint("min_score >= 0 AND max_score > min_score AND max_score <= 1000", name="ck_criterion_scores"),
        CheckConstraint("weight > 0 AND weight <= 1000", name="ck_criterion_weight"),
        CheckConstraint("position >= 0", name="ck_criterion_position"),
        UniqueConstraint("case_id", "position", name="uq_criterion_position"),
    )


class StoredObject(Base):
    __tablename__ = "stored_objects"
    id: Mapped[int] = mapped_column(primary_key=True)
    object_key: Mapped[str] = mapped_column(String(255), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("size_bytes > 0", name="ck_stored_object_size"),)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="RESTRICT"), index=True)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    stored_object_id: Mapped[int | None] = mapped_column(ForeignKey("stored_objects.id", ondelete="RESTRICT"), nullable=True, unique=True)
    stored_object: Mapped[StoredObject | None] = relationship()
    __table_args__ = (
        CheckConstraint("url IS NOT NULL OR stored_object_id IS NOT NULL", name="ck_submission_content"),
        Index("ix_submission_team_case_latest", "team_id", "case_id", "submitted_at", "id"),
    )


class ExpertAssignment(Base):
    __tablename__ = "expert_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="RESTRICT"), index=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submission: Mapped[Submission] = relationship()
    scores: Mapped[list[Score]] = relationship(back_populates="assignment", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("submission_id", "expert_id", name="uq_expert_assignment"),)


class Score(Base):
    __tablename__ = "scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("expert_assignments.id", ondelete="CASCADE"), index=True)
    criterion_id: Mapped[int] = mapped_column(ForeignKey("criteria.id", ondelete="RESTRICT"), index=True)
    value: Mapped[int] = mapped_column()
    assignment: Mapped[ExpertAssignment] = relationship(back_populates="scores")
    __table_args__ = (
        UniqueConstraint("assignment_id", "criterion_id", name="uq_score_assignment_criterion"),
        CheckConstraint("value >= 0 AND value <= 1000", name="ck_score_value"),
    )


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(40))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("ix_notifications_user_id_id", "user_id", "id"),)


# ==================== ЛР2: Авторизация ====================
class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    hackathon_id: Mapped[int] = mapped_column(ForeignKey("hackathons.id", ondelete="RESTRICT"), index=True)
    captain_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    members: Mapped[list[TeamMember]] = relationship(
        primaryjoin="Team.id == TeamMember.team_id", foreign_keys="TeamMember.team_id",
        order_by="TeamMember.user_id", cascade="all, delete-orphan",
    )
    __table_args__ = (
        UniqueConstraint("id", "hackathon_id", name="uq_team_hackathon"),
        Index("uq_team_name_ci", "hackathon_id", func.lower(name), unique=True),
    )


class TeamMember(Base):
    __tablename__ = "team_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(index=True)
    hackathon_id: Mapped[int] = mapped_column()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    __table_args__ = (
        ForeignKeyConstraint(["team_id", "hackathon_id"], ["teams.id", "teams.hackathon_id"], ondelete="CASCADE", name="fk_member_team_hackathon"),
        UniqueConstraint("hackathon_id", "user_id", name="uq_member_hackathon_user"),
        UniqueConstraint("team_id", "user_id", name="uq_member_team_user"),
    )


class Invite(Base):
    __tablename__ = "invites"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index("uq_invite_active_team", "team_id", unique=True, postgresql_where=text("revoked_at IS NULL")),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("uq_users_username_ci", func.lower(username), unique=True),
        Index("uq_users_email_ci", func.lower(email), unique=True),
    )

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.user_id",
    )
    roles: Mapped[list[Role]] = relationship(
        secondary="role_user",
        primaryjoin=lambda: and_(
            User.id == UserRole.user_id,
            UserRole.deleted_at.is_(None),
        ),
        secondaryjoin=lambda: and_(
            Role.id == UserRole.role_id,
            Role.deleted_at.is_(None),
        ),
        viewonly=True,
        overlaps="user_roles,users,role,user",
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    family_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    access_jti: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    refresh_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


# ==================== ЛР3: RBAC ====================
class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.role_id",
    )
    permission_roles: Mapped[list[PermissionRole]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
        foreign_keys="PermissionRole.role_id",
    )
    users: Mapped[list[User]] = relationship(
        secondary="role_user",
        primaryjoin=lambda: and_(
            Role.id == UserRole.role_id,
            UserRole.deleted_at.is_(None),
        ),
        secondaryjoin=lambda: User.id == UserRole.user_id,
        viewonly=True,
        overlaps="user_roles,user,role,roles",
    )
    permissions: Mapped[list[Permission]] = relationship(
        secondary="permission_role",
        primaryjoin=lambda: and_(
            Role.id == PermissionRole.role_id,
            PermissionRole.deleted_at.is_(None),
        ),
        secondaryjoin=lambda: and_(
            Permission.id == PermissionRole.permission_id,
            Permission.deleted_at.is_(None),
        ),
        viewonly=True,
        overlaps="permission_roles,permission,roles,permissions",
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    permission_roles: Mapped[list[PermissionRole]] = relationship(
        back_populates="permission",
        cascade="all, delete-orphan",
        foreign_keys="PermissionRole.permission_id",
    )
    roles: Mapped[list[Role]] = relationship(
        secondary="permission_role",
        primaryjoin=lambda: and_(
            Permission.id == PermissionRole.permission_id,
            PermissionRole.deleted_at.is_(None),
        ),
        secondaryjoin=lambda: and_(
            Role.id == PermissionRole.role_id,
            Role.deleted_at.is_(None),
        ),
        viewonly=True,
        overlaps="permission_roles,permission,role,permissions",
    )


class UserRole(Base):
    __tablename__ = "role_user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_role_user_user_id_role_id"),
    )

    user: Mapped[User] = relationship(
        back_populates="user_roles",
        foreign_keys=[user_id],
        overlaps="roles,users",
    )
    role: Mapped[Role] = relationship(
        back_populates="user_roles",
        foreign_keys=[role_id],
        overlaps="roles,users",
    )


class PermissionRole(Base):
    __tablename__ = "permission_role"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_permission_role_role_id_permission_id"),
    )

    role: Mapped[Role] = relationship(
        back_populates="permission_roles",
        foreign_keys=[role_id],
        overlaps="roles,permissions",
    )
    permission: Mapped[Permission] = relationship(
        back_populates="permission_roles",
        foreign_keys=[permission_id],
        overlaps="roles,permissions",
    )
