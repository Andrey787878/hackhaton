"""Database integration tests against migrated PostgreSQL, without MinIO.

Rows created by the fixture are rolled back. The persistence smoke test
commits and then removes only its own randomly named account.
"""
from datetime import datetime, timedelta, timezone
import secrets

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Case, Hackathon, Invite, Score, Submission, Team, TeamMember, User
from scripts.verify_database import exercise_persistence, verify_schema


@pytest.fixture
def graph():
    with SessionLocal() as db:
        token = secrets.token_hex(8)
        user = User(username="db_" + token, email=f"{token}@example.invalid", password_hash="unused-in-rollback-test")
        db.add(user)
        db.flush()
        now = datetime.now(timezone.utc)
        event = Hackathon(organizer_id=user.id, title="Database test", description="Fixture",
                          starts_at=now, deadline_at=now + timedelta(days=1))
        db.add(event)
        db.flush()
        case = Case(hackathon_id=event.id, title="Case", description="Fixture")
        team = Team(hackathon_id=event.id, captain_id=user.id, name="DB team")
        db.add_all([case, team])
        db.flush()
        try:
            yield db, user, event, case, team, now
        finally:
            db.rollback()


def test_schema_and_seed_roles_match_migrations():
    result = verify_schema()
    assert result["schema_matches_models"]
    assert result["application_tables"] == 17
    assert result["foreign_keys"] > 0


def test_committed_row_is_readable_and_rollback_is_atomic():
    assert set(exercise_persistence().values()) == {"passed"}


def test_application_connections_use_utc():
    with SessionLocal() as db:
        assert db.scalar(text("SHOW TIMEZONE")) == "UTC"


def test_username_is_unique_ignoring_case(graph):
    db, user, *_ = graph
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(User(username=user.username.upper(), email="other@example.invalid", password_hash="unused"))
        db.flush()


def test_foreign_key_rejects_missing_organizer(graph):
    db, _, _, _, _, now = graph
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Hackathon(organizer_id=-1, title="Invalid", description="Fixture",
                         starts_at=now, deadline_at=now + timedelta(days=1)))
        db.flush()


def test_deadline_must_follow_start(graph):
    db, user, _, _, _, now = graph
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Hackathon(organizer_id=user.id, title="Invalid", description="Fixture",
                         starts_at=now, deadline_at=now))
        db.flush()


def test_team_member_cannot_reference_another_hackathon(graph):
    db, user, event, _, team, now = graph
    other = Hackathon(organizer_id=user.id, title="Other", description="Fixture",
                      starts_at=now, deadline_at=now + timedelta(days=1))
    db.add(other)
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(TeamMember(team_id=team.id, hackathon_id=other.id, user_id=user.id))
        db.flush()


def test_submission_requires_url_or_object(graph):
    db, user, _, case, team, now = graph
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Submission(team_id=team.id, case_id=case.id, submitted_by=user.id, submitted_at=now))
        db.flush()


def test_only_one_active_invite_per_team(graph):
    db, _, _, _, team, now = graph
    db.add(Invite(team_id=team.id, code_hash=secrets.token_hex(32), created_at=now))
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Invite(team_id=team.id, code_hash=secrets.token_hex(32), created_at=now))
        db.flush()


def test_score_range_is_enforced_in_postgresql(graph):
    db, *_ = graph
    # PostgreSQL reports check constraints before foreign keys here. Assert
    # the exact constraint so a missing assignment cannot yield a false pass.
    with pytest.raises(IntegrityError) as caught, db.begin_nested():
        db.add(Score(assignment_id=-1, criterion_id=-1, value=1001))
        db.flush()
    assert caught.value.orig.diag.constraint_name == "ck_score_value"
