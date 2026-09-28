"""Operator-only CLI: python -m app.bootstrap create-admin / seed-demo."""
import argparse
import getpass
import sys

import bcrypt
from pydantic import ValidationError
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Role, User, UserRole
from app.schemas import RegisterRequest


def provision_user(db: Session, profile: RegisterRequest, role_slug: str) -> tuple[str, bool]:
    """Create an operator-specified account in the caller's transaction.

    Reruns do not reset passwords or grant roles to existing accounts.
    Serialize operator commands to prevent concurrent provisioning races.
    """
    db.execute(text("SELECT pg_advisory_xact_lock(72620260927)"))
    if role_slug not in {"admin", "organizer", "participant", "expert"}:
        raise ValueError("Неизвестная роль платформы.")
    role = db.scalar(select(Role).where(Role.slug == role_slug, Role.deleted_at.is_(None)))
    if role is None:
        raise ValueError("Роль не найдена. Выполните миграции.")
    existing = list(db.scalars(select(User).where(or_(
        func.lower(User.username) == profile.username.lower(),
        func.lower(User.email) == str(profile.email).lower(),
    ))))
    if existing:
        user = existing[0]
        assigned = db.scalar(select(UserRole.id).where(
            UserRole.user_id == user.id, UserRole.role_id == role.id, UserRole.deleted_at.is_(None),
        ))
        if (len(existing) == 1 and user.username.lower() == profile.username.lower()
                and user.email.lower() == str(profile.email).lower() and assigned is not None):
            return user.username, False
        raise ValueError("Логин/email занят: существующий аккаунт не изменён и не повышен в правах.")

    user = User(
        username=profile.username,
        email=str(profile.email),
        password_hash=bcrypt.hashpw(profile.password.encode("utf-8"), bcrypt.gensalt()).decode("ascii"),
        birthday=profile.birthday,
        display_name=profile.display_name,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id, created_by=user.id))
    db.flush()
    return user.username, True


def seed_demo(db: Session, password: str) -> list[tuple[str, bool]]:
    results = []
    for role in ("admin", "organizer", "participant", "expert"):
        profile = RegisterRequest(
            username=f"demo-{role}", email=f"demo-{role}@example.com",
            password=password, c_password=password, display_name=f"Demo {role}",
        )
        results.append(provision_user(db, profile, role))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Создание аккаунтов оператором сервера")
    parser.add_argument("command", choices=["create-admin", "seed-demo"])
    parser.add_argument("--username")
    parser.add_argument("--email")
    parser.add_argument("--password-stdin", action="store_true", help="Читать пароль из stdin без вывода")
    args = parser.parse_args()
    if args.command == "create-admin" and (not args.username or not args.email):
        parser.error("create-admin требует --username и --email")
    if args.command == "seed-demo" and (args.username or args.email):
        parser.error("seed-demo использует фиксированные имена demo-<role>")
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    elif sys.stdin.isatty():
        password = getpass.getpass("Пароль: ")
        if password != getpass.getpass("Повторите пароль: "):
            parser.exit(1, "Пароли не совпадают.\n")
    else:
        parser.error("Для запуска без терминала используйте --password-stdin")

    try:
        with SessionLocal.begin() as db:
            if args.command == "seed-demo":
                results = seed_demo(db, password)
            else:
                profile = RegisterRequest(
                    username=args.username, email=args.email,
                    password=password, c_password=password,
                )
                results = [provision_user(db, profile, "admin")]
    except ValidationError as exc:
        # ValidationError.__str__ includes input values, possibly passwords.
        messages = "; ".join(error["msg"] for error in exc.errors(include_input=False))
        parser.exit(1, f"Некорректные данные: {messages}\n")
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    for username, created in results:
        print(f"{username}: {'создан' if created else 'уже существует, без изменений'}")


if __name__ == "__main__":
    main()
