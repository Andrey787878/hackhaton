import secrets
import string
import subprocess
import sys
from datetime import datetime, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Role, User, UserRole
from app.bootstrap import provision_user
from app.schemas import RegisterRequest


@pytest.fixture
def client():
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        yield client


@pytest.fixture
def account(client):
    username = "Test" + "".join(secrets.choice(string.ascii_letters) for _ in range(16))
    payload = {
        "username": username,
        "email": f"{username.lower()}@example.com",
        "password": "Test-password-123!",
        "c_password": "Test-password-123!",
        "birthday": "2000-01-01",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return payload, response.json()


def login(client, payload):
    response = client.post("/api/v1/auth/login", json={
        "username": payload["username"], "password": payload["password"],
    })
    assert response.status_code == 200, response.text
    return response.json()


def bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_health_and_versioned_schema(client):
    assert client.get("/api/v1/health").json() == {"status": "ok", "database": "ok"}
    paths = client.get("/openapi.json").json()["paths"]
    assert paths and all(path.startswith("/api/v1/") for path in paths)


def test_login_logout_and_private_profile(client, account):
    payload, user = account
    assert "password_hash" not in user
    assert client.get("/api/v1/auth/me").status_code == 401
    tokens = login(client, payload)
    assert client.get("/api/v1/auth/me", headers=bearer(tokens)).json()["id"] == user["id"]
    assert client.post("/api/v1/auth/out", headers=bearer(tokens)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=bearer(tokens)).status_code == 403


def test_refresh_rotation_and_reuse(client, account):
    tokens = login(client, account[0])
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    assert client.get("/api/v1/auth/me", headers=bearer(tokens)).status_code == 403
    assert client.get("/api/v1/auth/me", headers=bearer(new_tokens)).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 403
    assert client.get("/api/v1/auth/me", headers=bearer(new_tokens)).status_code == 403


def test_forged_refresh_cannot_revoke_victim(client, account):
    tokens = login(client, account[0])
    claims = jwt.decode(tokens["refresh_token"], options={"verify_signature": False})
    forged = jwt.encode(claims, "attacker-key-that-is-at-least-32-bytes", algorithm="HS256")
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": forged}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(tokens)).status_code == 200


def test_user_role_cannot_assign_admin(client, account):
    payload, user = account
    with SessionLocal() as db:
        basic_role = db.scalar(select(Role).where(Role.slug == "user"))
        admin_role = db.scalar(select(Role).where(Role.slug == "admin"))
        admin_id = admin_role.id
        db.add(UserRole(user_id=user["id"], role_id=basic_role.id, created_by=user["id"]))
        db.commit()
    headers = bearer(login(client, payload))
    response = client.post(f"/api/v1/admin/user/{user['id']}/role", json={"role_id": admin_id}, headers=headers)
    assert response.status_code == 403, response.text
    assert client.get("/api/v1/admin/policy/role", headers=headers).status_code == 403


def test_wrong_password_and_duplicate_registration(client, account):
    payload, _ = account
    assert client.post("/api/v1/auth/register", json=payload).status_code == 422
    assert client.post("/api/v1/auth/login", json={
        "username": payload["username"], "password": "Wrong-password-123!",
    }).status_code == 401


def test_admin_permission_grant_and_revocation(client, account):
    payload, user = account
    with SessionLocal() as db:
        role = db.scalar(select(Role).where(Role.slug == "admin"))
        assignment = UserRole(user_id=user["id"], role_id=role.id, created_by=user["id"])
        db.add(assignment)
        db.commit()
        assignment_id = assignment.id
    headers = bearer(login(client, payload))
    assert client.get("/api/v1/admin/policy/role", headers=headers).status_code == 200
    with SessionLocal() as db:
        db.get(UserRole, assignment_id).deleted_at = datetime.now(timezone.utc)
        db.commit()
    assert client.get("/api/v1/admin/policy/role", headers=headers).status_code == 403


def test_long_utf8_password_is_rejected(client, account):
    payload, _ = account
    payload = {**payload, "password": "Яя1!" * 20, "c_password": "Яя1!" * 20}
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert any(error["loc"][-1] == "password" for error in response.json()["detail"])


def new_profile(prefix="user"):
    username = f"{prefix}_{secrets.token_hex(6)}"
    return RegisterRequest(username=username, email=f"{username}@example.com",
                           password="Test-password-123!", c_password="Test-password-123!")


def test_registration_has_participant_role_and_optional_birthday(client):
    payload = new_profile().model_dump(mode="json", exclude_none=True)
    payload["display_name"] = "  Андрей  "
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    user = response.json()
    assert user["birthday"] is None
    assert user["display_name"] == "Андрей"
    assert [role["slug"] for role in user["roles"]] == ["participant"]
    tokens = login(client, {**payload, "username": payload["username"].upper()})
    assert client.get("/api/v1/auth/me", headers=bearer(tokens)).json()["roles"][0]["slug"] == "participant"


@pytest.mark.parametrize("extra", [{"roles": ["admin"]}, {"role_id": 1}, {"is_admin": True}])
def test_registration_rejects_privilege_fields(client, extra):
    payload = new_profile().model_dump(mode="json")
    assert client.post("/api/v1/auth/register", json={**payload, **extra}).status_code == 422
    with SessionLocal() as db:
        assert db.scalar(select(User.id).where(User.username == payload["username"])) is None


def test_profile_updates_only_allowed_fields(client, account):
    headers = bearer(login(client, account[0]))
    response = client.patch("/api/v1/auth/me", json={"display_name": "Имя участника"}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["birthday"] == "2000-01-01"
    assert response.json()["display_name"] == "Имя участника"
    assert client.patch("/api/v1/auth/me", json={"birthday": None}, headers=headers).json()["birthday"] is None
    for changes in ({"roles": ["admin"]}, {"id": 1}, {"email": "other@example.com"}, {}, {"birthday": "2999-01-01"}):
        assert client.patch("/api/v1/auth/me", json=changes, headers=headers).status_code == 422
    assert client.patch("/api/v1/auth/me", json={"display_name": "Anon"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers).json()["id"] == account[1]["id"]


@pytest.mark.parametrize("role_slug", ["organizer", "participant", "expert"])
def test_platform_roles_cannot_manage_access(client, role_slug):
    profile = new_profile(role_slug)
    with SessionLocal.begin() as db:
        provision_user(db, profile, role_slug)
        admin_id = db.scalar(select(Role.id).where(Role.slug == "admin"))
    tokens = login(client, profile.model_dump())
    assert [role["slug"] for role in tokens["user"]["roles"]] == [role_slug]
    headers = bearer(tokens)
    assert client.get("/api/v1/admin/user", headers=headers).status_code == 403
    assert client.post(f"/api/v1/admin/user/{tokens['user']['id']}/role",
                       json={"role_id": admin_id}, headers=headers).status_code == 403
    assert client.post("/api/v1/admin/policy/role",
                       json={"name": "Forbidden", "slug": "forbidden"}, headers=headers).status_code == 403


def test_admin_assigns_and_revokes_expert_through_api(client, account):
    profile = new_profile("admin")
    with SessionLocal.begin() as db:
        provision_user(db, profile, "admin")
    headers = bearer(login(client, profile.model_dump()))
    roles = client.get("/api/v1/admin/policy/role", headers=headers).json()["items"]
    expert_id = next(role["id"] for role in roles if role["slug"] == "expert")
    target = f"/api/v1/admin/user/{account[1]['id']}/role"
    assert client.post(target, json={"role_id": expert_id}, headers=headers).status_code == 200
    participant_headers = bearer(login(client, account[0]))
    me = client.get("/api/v1/auth/me", headers=participant_headers).json()
    assert {role["slug"] for role in me["roles"]} == {"expert", "participant"}
    assert client.delete(f"{target}/{expert_id}", headers=headers).status_code == 200
    me = client.get("/api/v1/auth/me", headers=participant_headers).json()
    assert {role["slug"] for role in me["roles"]} == {"participant"}


def test_operator_provisioning_is_atomic_and_never_promotes_existing_user(client, account):
    candidate = new_profile("operator")
    with pytest.raises(ValueError, match="не повышен"):
        with SessionLocal.begin() as db:
            provision_user(db, candidate, "admin")
            provision_user(db, RegisterRequest(**account[0]), "admin")
    with SessionLocal() as db:
        assert db.scalar(select(User.id).where(User.username == candidate.username)) is None
    assert {r["slug"] for r in login(client, account[0])["user"]["roles"]} == {"participant"}


def test_create_admin_cli_and_idempotency(client):
    profile = new_profile("cliadmin")
    command = [sys.executable, "-m", "app.bootstrap", "create-admin",
               "--username", profile.username, "--email", str(profile.email), "--password-stdin"]
    for password in (profile.password, "Different-password-123!"):
        result = subprocess.run(command, input=password + "\n", text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert password not in result.stdout + result.stderr
    tokens = login(client, profile.model_dump())
    assert client.get("/api/v1/admin/policy/role", headers=bearer(tokens)).status_code == 200


def test_seed_demo_cli_is_repeatable(client):
    password = "Demo-test-password-123!"
    command = [sys.executable, "-m", "app.bootstrap", "seed-demo", "--password-stdin"]
    for _ in range(2):
        result = subprocess.run(command, input=password + "\n", text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert password not in result.stdout + result.stderr
    for role in ("admin", "organizer", "participant", "expert"):
        tokens = login(client, {"username": f"demo-{role}", "password": password})
        assert [item["slug"] for item in tokens["user"]["roles"]] == [role]


def test_birthdays_are_optional_without_lab_age_restriction(client):
    payload = new_profile().model_dump(mode="json")
    assert client.post("/api/v1/auth/register", json={**payload, "birthday": "2999-01-01"}).status_code == 422
    response = client.post("/api/v1/auth/register", json={**payload, "birthday": "2025-01-01"})
    assert response.status_code == 201, response.text
