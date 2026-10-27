from io import BytesIO
import zipfile

import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
import boto3
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.main import app
from app.models import Notification, StoredObject, Submission
from app.storage import get_storage
from test_teams import END, EVENT, START, client, clock_state, user


def archive_bytes():
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("README.md", "Демонстрационное решение")
    return output.getvalue()


def notices(client, headers):
    result = client.get("/api/v1/notifications", headers=headers)
    assert result.status_code == 200, result.text
    return result.json()


def test_full_journey_and_notification_ownership(client, user, clock_state):
    organizer_id, organizer = user("organizer")
    captain_id, captain = user()
    member_id, member = user()
    expert_id, expert = user("expert")
    _, outsider = user()
    created = client.post("/api/v1/organizer/hackathons", json=EVENT, headers=organizer)
    assert created.status_code == 201, created.text
    hid = created.json()["id"]
    base = f"/api/v1/organizer/hackathons/{hid}"
    case = client.post(base + "/cases", json={"title": "API", "description": "Решение"}, headers=organizer)
    assert case.status_code == 201
    cid = case.json()["id"]
    criteria = client.put(base + f"/cases/{cid}/criteria", json={"criteria": [
        {"title": "Функциональность", "min_score": 0, "max_score": 10, "weight": "3"},
        {"title": "Код", "min_score": 0, "max_score": 5, "weight": "1"},
    ]}, headers=organizer)
    assert criteria.status_code == 200
    criterion_ids = [row["id"] for row in criteria.json()["criteria"]]
    assert client.post(base + "/publish", headers=organizer).status_code == 200
    assert notices(client, organizer)[0]["kind"] == "hackathon_published"
    team = client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": "Команда"}, headers=captain)
    assert team.status_code == 201, team.text
    tid = team.json()["id"]
    code = client.post(f"/api/v1/teams/{tid}/invite", headers=captain).json()["code"]
    assert client.post("/api/v1/teams/join", json={"code": code}, headers=member).status_code == 200
    assert notices(client, captain)[0]["kind"] == "team_joined"
    assert notices(client, captain)[0]["actor_id"] == member_id

    payload = archive_bytes()
    clock_state["now"] = START
    submission = client.post(f"/api/v1/teams/{tid}/submissions",
                             data={"case_id": cid, "url": "https://github.com/example/demo"},
                             files={"archive": ("demo.zip", payload, "application/zip")}, headers=captain)
    assert submission.status_code == 201, submission.text
    sid = submission.json()["id"]
    assert submission.json()["submitted_at"] == START.isoformat().replace("+00:00", "Z")
    assert notices(client, organizer)[0]["kind"] == "submission_created"
    assert notices(client, organizer)[0]["resource_id"] == sid
    with SessionLocal() as db:
        stored = db.get(StoredObject, db.get(Submission, sid).stored_object_id)
        assert stored.object_key != "demo.zip"
    anon = boto3.client("s3", endpoint_url="http://minio:9000",
                        config=Config(signature_version=UNSIGNED, s3={"addressing_style": "path"}))
    with pytest.raises(ClientError):
        anon.get_object(Bucket=get_storage().bucket, Key=stored.object_key)
    assert client.get(f"/api/v1/submissions/{sid}/archive", headers=outsider).status_code == 403
    assert client.get(f"/api/v1/submissions/{sid}/archive", headers=member).content == payload

    clock_state["now"] = END
    late = client.post(f"/api/v1/teams/{tid}/submissions",
                       data={"case_id": cid, "url": "https://github.com/example/late"}, headers=captain)
    assert late.status_code == 409
    assert len([n for n in notices(client, organizer) if n["kind"] == "submission_created"]) == 1
    assigned = client.post(base + "/assignments", json={"team_id": tid, "case_id": cid,
                                                        "expert_id": expert_id}, headers=organizer)
    assert assigned.status_code == 201, assigned.text
    aid = assigned.json()["id"]
    assert notices(client, expert)[0]["kind"] == "expert_assigned"
    assert client.get(f"/api/v1/submissions/{sid}/archive", headers=expert).content == payload
    score = client.put(f"/api/v1/expert/assignments/{aid}/scores", json={"scores": [
        {"criterion_id": criterion_ids[0], "value": 8},
        {"criterion_id": criterion_ids[1], "value": 5},
    ]}, headers=expert)
    assert score.status_code == 200, score.text
    assert score.json()["total"] == "85.00"
    board = client.get(f"/api/v1/hackathons/{hid}/cases/{cid}/leaderboard")
    assert board.status_code == 200 and board.json()["entries"][0]["total"] == "85.00"
    captain_notices = notices(client, captain)
    assert captain_notices[0]["kind"] == "score_completed"
    assert captain_notices[0]["resource_id"] == sid
    nid = captain_notices[0]["id"]
    assert client.get("/api/v1/notifications/unread-count", headers=captain).json()["count"] == 2
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=outsider).status_code == 404
    marked = client.post(f"/api/v1/notifications/{nid}/read", headers=captain)
    assert marked.status_code == 200 and marked.json()["read_at"] is not None
    assert client.post(f"/api/v1/notifications/{nid}/read", headers=captain).json()["read_at"] == marked.json()["read_at"]
    assert client.get("/api/v1/notifications/unread-count", headers=captain).json()["count"] == 1
    assert len(client.get("/api/v1/notifications?unread_only=true", headers=captain).json()) == 1
    assert client.get("/api/v1/notifications").status_code == 401
    assert organizer_id != captain_id


def test_notification_failure_rolls_back_submission_and_object(client, user, clock_state, monkeypatch):
    organizer_id, organizer = user("organizer")
    _, captain = user()
    event = client.post("/api/v1/organizer/hackathons", json=EVENT, headers=organizer).json()
    hid = event["id"]
    base = f"/api/v1/organizer/hackathons/{hid}"
    cid = client.post(base + "/cases", json={"title": "Кейс", "description": "Описание"},
                      headers=organizer).json()["id"]
    assert client.put(base + f"/cases/{cid}/criteria", json={"criteria": [{"title": "Качество"}]},
                      headers=organizer).status_code == 200
    assert client.post(base + "/publish", headers=organizer).status_code == 200
    tid = client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": "Alpha"}, headers=captain).json()["id"]
    clock_state["now"] = START
    storage = get_storage()
    before = {row["Key"] for row in storage.client.list_objects_v2(
        Bucket=storage.bucket, Prefix=f"submissions/{tid}/").get("Contents", [])}
    def fail(*args, **kwargs):
        raise IntegrityError("notification failed", {}, Exception("test"))
    monkeypatch.setattr("app.submission_service.record", fail)
    result = client.post(f"/api/v1/teams/{tid}/submissions", data={"case_id": cid},
                         files={"archive": ("demo.zip", archive_bytes())}, headers=captain)
    assert result.status_code == 409
    after = {row["Key"] for row in storage.client.list_objects_v2(
        Bucket=storage.bucket, Prefix=f"submissions/{tid}/").get("Contents", [])}
    assert after == before
    with SessionLocal() as db:
        assert db.scalar(select(Submission.id).where(Submission.team_id == tid)) is None
        assert db.scalar(select(Notification.id).where(Notification.kind == "submission_created",
                                                      Notification.user_id == organizer_id)) is None
