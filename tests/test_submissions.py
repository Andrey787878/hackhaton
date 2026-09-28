from io import BytesIO
from datetime import timedelta
import zipfile

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal, get_db
from app.main import app
from app.models import StoredObject, Submission
from app.storage import get_storage
from test_teams import START, END, client, user, event, team, clock_state


def archive_bytes():
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("README.txt", "Рабочий архив для теста")
    return output.getvalue()


@pytest.fixture
def ready(client, team, clock_state):
    created, captain, organizer, hid = team
    cases = client.get(f"/api/v1/organizer/hackathons/{hid}/cases", headers=organizer).json()
    clock_state["now"] = START
    return created["id"], cases[0]["id"], captain, organizer, hid


def submit(client, ready, *, data=None, file=None, headers=None):
    tid, cid, captain, _, _ = ready
    fields = {"case_id": str(cid), **(data or {})}
    files = {"archive": ("solution.zip", file, "application/zip")} if file is not None else None
    return client.post(f"/api/v1/teams/{tid}/submissions", data=fields,
                       files=files, headers=headers or captain)


def test_url_only_and_latest_revision(client, ready, clock_state):
    tid, cid, captain, _, _ = ready
    first = submit(client, ready, data={"url": "https://github.com/example/one"})
    assert first.status_code == 201, first.text
    assert first.json()["submitted_at"] == START.isoformat().replace("+00:00", "Z")
    assert first.json()["archive"] is None
    second = submit(client, ready, data={"url": "https://github.com/example/two"})
    assert second.status_code == 201, second.text
    listed = client.get(f"/api/v1/teams/{tid}/submissions?case_id={cid}", headers=captain)
    assert [item["id"] for item in listed.json()] == [second.json()["id"], first.json()["id"]]
    assert client.get(f"/api/v1/submissions/{first.json()['id']}/archive", headers=captain).status_code == 404


def test_archive_in_private_minio_and_authorized_download(client, ready, user):
    tid, _, captain, organizer, hid = ready
    payload = archive_bytes()
    response = submit(client, ready, data={"url": "https://github.com/example/work"}, file=payload)
    assert response.status_code == 201, response.text
    sid = response.json()["id"]
    assert response.json()["archive"]["size_bytes"] == len(payload)
    with SessionLocal() as db:
        submission = db.get(Submission, sid)
        stored = db.get(StoredObject, submission.stored_object_id)
        assert stored.object_key.startswith(f"submissions/{tid}/")
        assert stored.object_key != "solution.zip"
        assert not hasattr(stored, "contents")
    download = client.get(f"/api/v1/submissions/{sid}/archive", headers=captain)
    assert download.status_code == 200 and download.content == payload
    assert download.headers["content-disposition"].startswith("attachment;")
    assert client.get(f"/api/v1/submissions/{sid}/archive", headers=organizer).status_code == 200
    _, outsider = user()
    for path in (f"/api/v1/submissions/{sid}", f"/api/v1/submissions/{sid}/archive",
                 f"/api/v1/teams/{tid}/submissions"):
        assert client.get(path, headers=outsider).status_code == 403
        assert client.get(path).status_code == 401
    anon = boto3.client("s3", endpoint_url="http://minio:9000",
                        config=Config(signature_version=UNSIGNED, s3={"addressing_style": "path"}))
    with pytest.raises(ClientError) as error:
        anon.get_object(Bucket=get_storage().bucket, Key=stored.object_key)
    assert error.value.response["ResponseMetadata"]["HTTPStatusCode"] in (401, 403)


def test_member_can_read_but_not_submit(client, ready, user):
    tid, _, captain, organizer, _ = ready
    member_id, member = user()
    code = client.post(f"/api/v1/teams/{tid}/invite", headers=captain).json()["code"]
    assert client.post("/api/v1/teams/join", json={"code": code}, headers=member).status_code == 200
    created = submit(client, ready, file=archive_bytes())
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    assert client.get(f"/api/v1/submissions/{sid}/archive", headers=member).status_code == 200
    assert submit(client, ready, data={"url": "https://github.com/example/forbidden"}, headers=member).status_code == 403
    assert submit(client, ready, data={"url": "https://github.com/example/forbidden"}, headers=organizer).status_code == 403


@pytest.mark.parametrize("data,status", [
    ({}, 422), ({"url": "http://example.com"}, 422),
    ({"url": "garbage"}, 422), ({"url": " "}, 422),
])
def test_missing_or_invalid_url(client, ready, data, status):
    assert submit(client, ready, data=data).status_code == status


@pytest.mark.parametrize("filename,payload,status", [
    ("bad.txt", b"bad", 422), ("bad.zip", b"not a zip", 422),
    ("large.zip", archive_bytes() + b"x" * (20 * 1024 * 1024), 413),
], ids=["extension", "invalid-zip", "too-large"])
def test_file_type_and_size(client, ready, filename, payload, status):
    tid, cid, captain, _, _ = ready
    result = client.post(f"/api/v1/teams/{tid}/submissions", data={"case_id": str(cid)},
                         files={"archive": (filename, payload)}, headers=captain)
    assert result.status_code == status, result.text
    assert client.get(f"/api/v1/teams/{tid}/submissions", headers=captain).json() == []


def test_deadline_and_start_enforced_by_server(client, ready, clock_state):
    clock_state["now"] = START - timedelta(microseconds=1)
    assert submit(client, ready, data={"url": "https://github.com/example/early"}).status_code == 409
    clock_state["now"] = END
    assert submit(client, ready, data={"url": "https://github.com/example/late"}).status_code == 409
    assert submit(client, ready, file=archive_bytes()).status_code == 409
    clock_state["now"] = END - timedelta(microseconds=1)
    assert submit(client, ready, data={"url": "https://github.com/example/just-in-time"}).status_code == 201


def test_storage_failure_cannot_create_submission(client, ready):
    class BrokenStorage:
        def put(self, *args):
            raise EndpointConnectionError(endpoint_url="http://minio:9000")
    app.dependency_overrides[get_storage] = lambda: BrokenStorage()
    try:
        assert submit(client, ready, file=archive_bytes()).status_code == 503
    finally:
        app.dependency_overrides.pop(get_storage, None)
    tid, _, captain, _, _ = ready
    assert client.get(f"/api/v1/teams/{tid}/submissions", headers=captain).json() == []


def test_deadline_during_upload_removes_object(client, ready, clock_state):
    storage = get_storage()
    before = set(item["Key"] for item in storage.client.list_objects_v2(
        Bucket=storage.bucket, Prefix=f"submissions/{ready[0]}/").get("Contents", []))
    class SlowStorage:
        def put(self, *args):
            storage.put(*args)
            clock_state["now"] = END
        def delete(self, key):
            storage.delete(key)
    app.dependency_overrides[get_storage] = lambda: SlowStorage()
    try:
        response = submit(client, ready, file=archive_bytes())
        assert response.status_code == 409, response.text
    finally:
        app.dependency_overrides.pop(get_storage, None)
    after = set(item["Key"] for item in storage.client.list_objects_v2(
        Bucket=storage.bucket, Prefix=f"submissions/{ready[0]}/").get("Contents", []))
    assert after == before
    with SessionLocal() as db:
        assert not list(db.scalars(select(Submission).where(Submission.team_id == ready[0])))


def test_db_commit_failure_removes_uploaded_object(client, ready):
    storage = get_storage()
    before = set(item["Key"] for item in storage.client.list_objects_v2(
        Bucket=storage.bucket, Prefix=f"submissions/{ready[0]}/").get("Contents", []))
    def broken_db():
        with SessionLocal() as db:
            def fail():
                raise IntegrityError("simulated commit failure", {}, Exception("test"))
            db.commit = fail
            yield db
    app.dependency_overrides[get_db] = broken_db
    try:
        assert submit(client, ready, file=archive_bytes()).status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)
    after = set(item["Key"] for item in storage.client.list_objects_v2(
        Bucket=storage.bucket, Prefix=f"submissions/{ready[0]}/").get("Contents", []))
    assert after == before
    with SessionLocal() as db:
        assert not list(db.scalars(select(StoredObject).where(StoredObject.object_key.like(f"submissions/{ready[0]}/%"))))


def test_case_must_belong_to_team_event(client, ready):
    tid, _, captain, organizer, _ = ready
    response = client.post(f"/api/v1/teams/{tid}/submissions", data={"case_id": "99999999", "url": "https://github.com/example/work"}, headers=captain)
    assert response.status_code == 404
