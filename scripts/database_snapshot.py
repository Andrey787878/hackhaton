"""Read-only, credential-free snapshot for a synthetic development/test DB.

Includes row counts and a few public domain fields. Never exports users,
password hashes, sessions, invitations or object-storage keys.
Run: python -m scripts.database_snapshot
"""
import json

from sqlalchemy import func, select

from app import models
from app.db import Base, engine


def snapshot() -> dict:
    with engine.connect() as connection:
        # One repeatable-read snapshot makes counts and example rows consistent.
        connection = connection.execution_options(isolation_level="REPEATABLE READ")
        counts = {name: connection.scalar(select(func.count()).select_from(table))
                  for name, table in sorted(Base.metadata.tables.items())}
        examples = {}
        for model, columns in (
            (models.Role, (models.Role.id, models.Role.slug)),
            (models.Hackathon, (models.Hackathon.id, models.Hackathon.title, models.Hackathon.is_published)),
            (models.Team, (models.Team.id, models.Team.hackathon_id, models.Team.name)),
            (models.Score, (models.Score.id, models.Score.assignment_id, models.Score.criterion_id, models.Score.value)),
        ):
            result = connection.execute(select(*columns).order_by(model.id).limit(6))
            examples[model.__tablename__] = [dict(row) for row in result.mappings()]
        return {"counts": counts, "examples": examples}


if __name__ == "__main__":
    print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
