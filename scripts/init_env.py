"""Создать локальный .env со случайными секретами, не перезаписывая существующий."""
from pathlib import Path
import secrets


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    content = (root / ".env.example").read_text(encoding="utf-8")
    replacements = {
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "JWT_SECRET": secrets.token_urlsafe(48),
        "REFRESH_TOKEN_PEPPER": secrets.token_urlsafe(32),
        "MINIO_ROOT_PASSWORD": secrets.token_urlsafe(32),
    }
    lines = [
        f"{line.split('=', 1)[0]}={replacements[line.split('=', 1)[0]]}"
        if line.split("=", 1)[0] in replacements else line
        for line in content.splitlines()
    ]
    try:
        with (root / ".env").open("x", encoding="utf-8") as file:
            file.write("\n".join(lines) + "\n")
    except FileExistsError:
        target = root / ".env"
        existing = target.read_text(encoding="utf-8")
        missing = [line for line in lines if line.startswith(("MINIO_ROOT_USER=", "MINIO_ROOT_PASSWORD=", "S3_BUCKET=", "MINIO_CONSOLE_PORT="))
                   and line.split("=", 1)[0] not in {row.split("=", 1)[0] for row in existing.splitlines()}]
        if missing:
            with target.open("a", encoding="utf-8") as file:
                file.write(("\n" if existing and not existing.endswith("\n") else "") + "\n".join(missing) + "\n")
            print("В существующий .env добавлены недостающие параметры MinIO; прежние сохранены.")
        else:
            print(".env уже настроен; изменения не внесены.")
    else:
        print("Создан .env со случайными секретами.")


if __name__ == "__main__":
    main()
