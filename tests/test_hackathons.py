import secrets
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import provision_user
from app.db import SessionLocal
from app.hackathon_service import get_server_time
from app.main import app
from app.schemas import RegisterRequest

NOW = datetime(2031, 1, 1, tzinfo=timezone.utc)
START = NOW + timedelta(days=1)
END = START + timedelta(days=2)
BODY = {"title": "Хакатон", "description": "Публичное описание",
        "starts_at": START.isoformat(), "deadline_at": END.isoformat()}
CASE = {"title": "Кейс", "description": "Закрытые материалы кейса"}
CRITERIA = {"criteria": [{"title": "Качество", "min_score": 0, "max_score": 10, "weight": "2.5"}]}


@pytest.fixture
def client():
    app.dependency_overrides[get_server_time] = lambda: NOW
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        yield client
    app.dependency_overrides.pop(get_server_time, None)


@pytest.fixture
def identity(client):
    def make(role):
        username = "h_" + secrets.token_hex(8)
        profile = RegisterRequest(username=username, email=f"{username}@example.com",
                                  password="Test-password-123!", c_password="Test-password-123!")
        with SessionLocal.begin() as db:
            provision_user(db, profile, role)
        response = client.post("/api/v1/auth/login", json={"username": username, "password": profile.password})
        assert response.status_code == 200, response.text
        return {"Authorization": "Bearer " + response.json()["access_token"]}
    return make


@pytest.fixture
def draft(client, identity):
    headers = identity("organizer")
    response = client.post("/api/v1/organizer/hackathons", json=BODY, headers=headers)
    assert response.status_code == 201, response.text
    hid = response.json()["id"]
    return headers, hid, f"/api/v1/organizer/hackathons/{hid}"


def add_case(client, draft):
    headers, _, path = draft
    response = client.post(path + "/cases", json=CASE, headers=headers)
    assert response.status_code == 201, response.text
    cid = response.json()["id"]
    response = client.put(f"{path}/cases/{cid}/criteria", json=CRITERIA, headers=headers)
    assert response.status_code == 200, response.text
    return cid


def test_draft_publication_and_editing(client, draft):
    headers, hid, path = draft
    assert client.get(f"/api/v1/hackathons/{hid}").status_code == 404
    assert client.get(f"/api/v1/hackathons/{hid}/cases").status_code == 404
    assert client.post(path + "/publish", headers=headers).status_code == 409
    response = client.post(path + "/cases", json=CASE, headers=headers)
    cid = response.json()["id"]
    assert client.post(path + "/publish", headers=headers).status_code == 409
    assert client.put(f"{path}/cases/{cid}/criteria", json=CRITERIA, headers=headers).status_code == 200
    assert client.post(path + "/publish", headers=headers).status_code == 200
    details = client.get(f"/api/v1/hackathons/{hid}").json()
    assert details["phase"] == "upcoming" and not details["materials_available"]
    assert "Закрытые" not in str(details)
    assert client.put(path, json=BODY, headers=headers).status_code == 409
    assert client.delete(f"{path}/cases/{cid}", headers=headers).status_code == 409
    assert client.post(path + "/unpublish", headers=headers).status_code == 200
    assert client.put(path, json={**BODY, "title": "Изменено"}, headers=headers).status_code == 200
    assert client.put(f"{path}/cases/{cid}", json={**CASE, "title": "Изменён кейс"}, headers=headers).status_code == 200
    assert client.delete(f"{path}/cases/{cid}", headers=headers).status_code == 204
    assert client.get(path + "/cases", headers=headers).json() == []


@pytest.mark.parametrize("moment,phase,status", [
    (START - timedelta(microseconds=1), "upcoming", 403),
    (START, "active", 200),
    (END - timedelta(microseconds=1), "active", 200),
    (END, "finished", 403),
    (END + timedelta(seconds=1), "finished", 403),
])
def test_exact_material_boundaries(client, draft, moment, phase, status):
    headers, hid, path = draft
    add_case(client, draft)
    assert client.post(path + "/publish", headers=headers).status_code == 200
    app.dependency_overrides[get_server_time] = lambda: moment
    details = client.get(f"/api/v1/hackathons/{hid}").json()
    assert details["phase"] == phase
    assert details["materials_available"] == (status == 200)
    assert client.get(f"/api/v1/hackathons/{hid}/cases").status_code == status
    assert client.get(path + "/cases", headers=headers).status_code == 200


@pytest.mark.parametrize("role", ["organizer", "admin"])
def test_ownership_even_for_other_admin(client, draft, identity, role):
    cid = add_case(client, draft)
    _, _, path = draft
    other = identity(role)
    operations = [
        ("GET", path, None), ("GET", path + "/cases", None),
        ("PUT", path, BODY), ("POST", path + "/publish", None),
        ("POST", path + "/unpublish", None), ("POST", path + "/cases", CASE),
        ("PUT", f"{path}/cases/{cid}", CASE),
        ("PUT", f"{path}/cases/{cid}/criteria", CRITERIA),
        ("DELETE", f"{path}/cases/{cid}", None),
    ]
    for method, url, payload in operations:
        response = client.request(method, url, headers=other, json=payload)
        assert response.status_code == 403, (url, response.text)
    assert client.get("/api/v1/organizer/hackathons", headers=other).json() == []


@pytest.mark.parametrize("role", ["participant", "expert", None])
def test_role_checks(client, draft, identity, role):
    headers = identity(role) if role else {}
    expected = 403 if role else 401
    assert client.post("/api/v1/organizer/hackathons", json=BODY, headers=headers).status_code == expected
    assert client.get(draft[2] + "/cases", headers=headers).status_code == expected


@pytest.mark.parametrize("changes", [
    {"starts_at": "2031-01-02T00:00:00"},
    {"deadline_at": START.isoformat()},
    {"deadline_at": NOW.isoformat()},
    {"starts_at": NOW.isoformat()},
    {"title": "  "}, {"organizer_id": 1}, {"is_published": True},
])
def test_invalid_hackathon_payload(client, identity, changes):
    response = client.post("/api/v1/organizer/hackathons", json={**BODY, **changes}, headers=identity("organizer"))
    assert response.status_code == 422, response.text


def test_utc_and_server_time(client, identity):
    response = client.post("/api/v1/organizer/hackathons", json={**BODY,
        "starts_at": "2031-01-02T05:00:00+05:00"}, headers=identity("organizer"))
    assert response.status_code == 201, response.text
    assert response.json()["starts_at"] == "2031-01-02T00:00:00Z"
    assert client.get("/api/v1/time").json()["server_time"] == "2031-01-01T00:00:00Z"


@pytest.mark.parametrize("changes", [
    {"min_score": 10, "max_score": 10}, {"weight": "0"}, {"weight": "-1"},
    {"weight": "NaN"}, {"weight": "0.00001"}, {"max_score": 1001}, {"max_score": True},
])
def test_invalid_criteria_leave_previous_values(client, draft, changes):
    cid = add_case(client, draft)
    headers, _, path = draft
    before = client.get(path + "/cases", headers=headers).json()
    response = client.put(f"{path}/cases/{cid}/criteria", json={"criteria": [{**CRITERIA["criteria"][0], **changes}]}, headers=headers)
    assert response.status_code == 422, response.text
    assert client.get(path + "/cases", headers=headers).json() == before


def test_criteria_replacement_and_foreign_case(client, draft):
    cid = add_case(client, draft)
    headers, hid, path = draft
    new_criteria = {"criteria": [{"title": "Новое", "max_score": 100, "weight": "3"},
                                 {"title": "Второе", "max_score": 5, "weight": "1"}]}
    response = client.put(f"{path}/cases/{cid}/criteria", json=new_criteria, headers=headers)
    assert response.status_code == 200, response.text
    assert [c["title"] for c in response.json()["criteria"]] == ["Новое", "Второе"]
    other = client.post("/api/v1/organizer/hackathons", json=BODY, headers=headers).json()["id"]
    assert client.put(f"/api/v1/organizer/hackathons/{other}/cases/{cid}/criteria", json=CRITERIA, headers=headers).status_code == 404
    assert client.put(f"{path}/cases/{cid}/criteria", json={"criteria": []}, headers=headers).status_code == 422


def test_configuration_frozen_at_start(client, draft):
    cid = add_case(client, draft)
    headers, _, path = draft
    assert client.post(path + "/publish", headers=headers).status_code == 200
    app.dependency_overrides[get_server_time] = lambda: START
    for method, url, payload in [
        ("PUT", path, BODY), ("POST", path + "/unpublish", None),
        ("PUT", f"{path}/cases/{cid}/criteria", CRITERIA),
        ("POST", path + "/cases", CASE),
    ]:
        assert client.request(method, url, json=payload, headers=headers).status_code == 409


def test_lists_hide_drafts_and_support_pagination(client, draft):
    headers, hid, path = draft
    assert hid not in [item["id"] for item in client.get("/api/v1/hackathons?limit=100").json()]
    own = client.get("/api/v1/organizer/hackathons", headers=headers).json()
    assert [item["id"] for item in own] == [hid]
    add_case(client, draft)
    assert client.post(path + "/publish", headers=headers).status_code == 200
    items = client.get("/api/v1/hackathons?limit=100").json()
    assert hid in [item["id"] for item in items]
    assert client.get("/api/v1/hackathons?limit=1&offset=0").json() == items[:1]
    assert client.get("/api/v1/hackathons?limit=101").status_code == 422


def test_second_unfinished_case_prevents_publication(client, draft):
    add_case(client, draft)
    headers, _, path = draft
    assert client.post(path + "/cases", json=CASE, headers=headers).status_code == 201
    assert client.post(path + "/publish", headers=headers).status_code == 409
