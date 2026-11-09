import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.bootstrap import provision_user
from app.db import SessionLocal
from app.hackathon_service import get_server_time
from app.main import app
from app.models import Invite, Team, TeamMember
from app.schemas import RegisterRequest
from app.team_service import get_clock, hash_code

NOW = datetime(2032, 1, 1, tzinfo=timezone.utc)
START = NOW + timedelta(days=1)
END = NOW + timedelta(days=3)
EVENT = {"title": "Командный хакатон", "description": "Публичное описание",
         "starts_at": START.isoformat(), "deadline_at": END.isoformat()}


@pytest.fixture
def clock_state():
    return {"now": NOW}


@pytest.fixture
def client(clock_state):
    app.dependency_overrides[get_clock] = lambda: lambda: clock_state["now"]
    app.dependency_overrides[get_server_time] = lambda: clock_state["now"]
    with TestClient(app, client=("127.0.0.1", 50000)) as instance:
        yield instance
    app.dependency_overrides.pop(get_clock, None)
    app.dependency_overrides.pop(get_server_time, None)


@pytest.fixture
def user(client):
    def make(role="participant"):
        username = "t_" + secrets.token_hex(8)
        profile = RegisterRequest(username=username, email=f"{username}@example.com",
                                  password="Test-password-123!", c_password="Test-password-123!")
        with SessionLocal.begin() as db:
            provision_user(db, profile, role)
        login = client.post("/api/v1/auth/login", json={"username": username, "password": profile.password})
        assert login.status_code == 200, login.text
        return login.json()["user"]["id"], {"Authorization": "Bearer " + login.json()["access_token"]}
    return make


@pytest.fixture
def event(client, user):
    _, organizer = user("organizer")
    base = "/api/v1/organizer/hackathons"
    response = client.post(base, json=EVENT, headers=organizer)
    assert response.status_code == 201, response.text
    hid = response.json()["id"]
    path = base + f"/{hid}"
    case = client.post(path + "/cases", json={"title": "Задача", "description": "Описание"}, headers=organizer)
    assert case.status_code == 201, case.text
    criteria = client.put(path + f"/cases/{case.json()['id']}/criteria",
                          json={"criteria": [{"title": "Качество"}]}, headers=organizer)
    assert criteria.status_code == 200, criteria.text
    assert client.post(path + "/publish", headers=organizer).status_code == 200
    return hid, organizer


@pytest.fixture
def team(client, user, event):
    hid, organizer = event
    captain_id, captain = user()
    response = client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": "Alpha"}, headers=captain)
    assert response.status_code == 201, response.text
    return response.json(), captain, organizer, hid


def test_captain_creates_team_and_member_joins(client, team, user):
    created, captain, organizer, hid = team
    tid = created["id"]
    assert created["captain_id"] == created["members"][0]["user_id"]
    assert len(created["members"]) == 1
    issued = client.post(f"/api/v1/teams/{tid}/invite", headers=captain)
    assert issued.status_code == 201, issued.text
    code = issued.json()["code"]
    assert len(code) == 43 and issued.headers["Cache-Control"] == "no-store"
    assert issued.json()["expires_at"] == END.isoformat().replace("+00:00", "Z")
    with SessionLocal() as db:
        invite = db.scalar(select(Invite).where(Invite.team_id == tid))
        assert invite.code_hash == hash_code(code)
        assert code not in invite.code_hash
    participant_id, participant = user()
    joined = client.post("/api/v1/teams/join", json={"code": code}, headers=participant)
    assert joined.status_code == 200, joined.text
    assert participant_id in [m["user_id"] for m in joined.json()["members"]]
    assert len(client.get(f"/api/v1/teams/{tid}", headers=participant).json()["members"]) == 2
    assert [item["id"] for item in client.get("/api/v1/teams", headers=participant).json()] == [tid]
    assert [item["id"] for item in client.get(f"/api/v1/organizer/hackathons/{hid}/teams", headers=organizer).json()] == [tid]
    assert client.get(f"/api/v1/teams/{tid}/invite", headers=captain).json().get("code") is None
    assert client.post("/api/v1/teams/join", json={"code": code}, headers=participant).status_code == 409


def test_invite_rotation_revocation_and_invalid_codes(client, team, user):
    created, captain, _, _ = team
    tid = created["id"]
    url = f"/api/v1/teams/{tid}/invite"
    old = client.post(url, headers=captain).json()["code"]
    new = client.post(url, headers=captain).json()["code"]
    assert old != new
    _, outsider = user()
    for code, status in [(old, 404), ("A" * 43, 404), ("bad", 422)]:
        assert client.post("/api/v1/teams/join", json={"code": code}, headers=outsider).status_code == status
    assert client.delete(url, headers=captain).status_code == 204
    assert client.delete(url, headers=captain).status_code == 204
    assert client.get(url, headers=captain).json()["active"] is False
    assert client.post("/api/v1/teams/join", json={"code": new}, headers=outsider).status_code == 404


def test_only_captain_controls_team(client, team, user):
    created, captain, _, _ = team
    tid = created["id"]
    _, outsider = user()
    invite = client.post(f"/api/v1/teams/{tid}/invite", headers=captain).json()["code"]
    assert client.post("/api/v1/teams/join", json={"code": invite}, headers=outsider).status_code == 200
    for headers in (outsider, {}):
        expected = 403 if headers else 401
        assert client.patch(f"/api/v1/teams/{tid}", json={"name": "Other"}, headers=headers).status_code == expected
        assert client.post(f"/api/v1/teams/{tid}/invite", headers=headers).status_code == expected
        assert client.delete(f"/api/v1/teams/{tid}/invite", headers=headers).status_code == expected
    assert client.patch(f"/api/v1/teams/{tid}", json={"name": "Renamed"}, headers=captain).json()["name"] == "Renamed"


def test_cannot_join_other_team_in_same_hackathon(client, team, user):
    first, captain, _, hid = team
    first_code = client.post(f"/api/v1/teams/{first['id']}/invite", headers=captain).json()["code"]
    other_id, other = user()
    second = client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": "Beta"}, headers=other)
    assert second.status_code == 201, second.text
    second_code = client.post(f"/api/v1/teams/{second.json()['id']}/invite", headers=other).json()["code"]
    assert client.post("/api/v1/teams/join", json={"code": first_code}, headers=other).status_code == 409
    assert client.post("/api/v1/teams/join", json={"code": second_code}, headers=captain).status_code == 409
    with SessionLocal() as db:
        assert len(list(db.scalars(select(TeamMember).where(TeamMember.hackathon_id == hid)))) == 2


def test_member_cannot_create_second_team_and_names_unique(client, team, user):
    first, captain, _, hid = team
    assert client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": "Second"}, headers=captain).status_code == 409
    _, outsider = user()
    assert client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": " alpha "}, headers=outsider).status_code == 409
    assert client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": "   "}, headers=outsider).status_code == 422


def test_private_team_and_organizer_scope(client, team, user):
    first, captain, _, hid = team
    _, outsider = user()
    _, other_organizer = user("organizer")
    assert client.get(f"/api/v1/teams/{first['id']}", headers=outsider).status_code == 403
    assert client.get(f"/api/v1/organizer/hackathons/{hid}/teams", headers=other_organizer).status_code == 403
    assert client.get(f"/api/v1/organizer/hackathons/{hid}/teams", headers=outsider).status_code == 403


def test_team_creation_requires_published_hackathon_and_permission(client, user, event):
    hid, organizer = event
    _, expert = user("expert")
    _, participant = user()
    assert client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": "Expert"}, headers=expert).status_code == 403
    assert client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": "Anon"}).status_code == 401
    # A second draft can only be accessed by its owner; participant cannot create there.
    draft = client.post("/api/v1/organizer/hackathons", json=EVENT, headers=organizer).json()["id"]
    assert client.post(f"/api/v1/hackathons/{draft}/teams", json={"name": "Draft"}, headers=participant).status_code == 409


def test_deadline_blocks_changes_but_read_and_revocation_remain(client, team, user, clock_state):
    first, captain, _, hid = team
    code = client.post(f"/api/v1/teams/{first['id']}/invite", headers=captain).json()["code"]
    _, outsider = user()
    clock_state["now"] = END
    assert client.post("/api/v1/teams/join", json={"code": code}, headers=outsider).status_code == 409
    assert client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": "Late"}, headers=outsider).status_code == 409
    assert client.patch(f"/api/v1/teams/{first['id']}", json={"name": "Late"}, headers=captain).status_code == 409
    assert client.post(f"/api/v1/teams/{first['id']}/invite", headers=captain).status_code == 409
    assert client.get(f"/api/v1/teams/{first['id']}", headers=captain).status_code == 200
    assert client.delete(f"/api/v1/teams/{first['id']}/invite", headers=captain).status_code == 204


def test_invite_is_multi_use_before_deadline(client, team, user):
    first, captain, _, _ = team
    code = client.post(f"/api/v1/teams/{first['id']}/invite", headers=captain).json()["code"]
    a = user()[1]
    b = user()[1]
    for headers in (a, b):
        assert client.post("/api/v1/teams/join", json={"code": code}, headers=headers).status_code == 200
    assert len(client.get(f"/api/v1/teams/{first['id']}", headers=captain).json()["members"]) == 3


def test_parallel_join_same_user_only_once(client, team, user):
    first, captain, _, hid = team
    code = client.post(f"/api/v1/teams/{first['id']}/invite", headers=captain).json()["code"]
    uid, headers = user()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post("/api/v1/teams/join", json={"code": code}, headers=headers).status_code, range(2)))
    assert sorted(results) == [200, 409]
    with SessionLocal() as db:
        assert len(list(db.scalars(select(TeamMember).where(TeamMember.hackathon_id == hid, TeamMember.user_id == uid)))) == 1
