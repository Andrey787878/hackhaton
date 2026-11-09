"""Run the complete API journey against a local Compose stack.

The output contains only public IDs and verification results, never credentials.
"""
import argparse
from datetime import datetime, timedelta, timezone
from getpass import getpass
from io import BytesIO
import json
from pathlib import Path
import secrets
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile


def api(base, method, path, *, token=None, payload=None, archive=None, expected=200):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if archive is not None:
        boundary = "----hackhaton" + secrets.token_hex(12)
        fields = [("case_id", str(payload["case_id"])), ("url", payload["url"])]
        parts = []
        for name, value in fields:
            parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode())
        parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"archive\"; "
                      f"filename=\"demo.zip\"\r\nContent-Type: application/zip\r\n\r\n").encode())
        parts.extend((archive, b"\r\n", f"--{boundary}--\r\n".encode()))
        body = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = Request(base.rstrip("/") + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            status, raw = response.status, response.read()
    except HTTPError as exc:
        status, raw = exc.code, exc.read()
    if status != expected:
        raise RuntimeError(f"{method} {path}: ожидался HTTP {expected}, получен {status}: {raw[:300].decode(errors='replace')}")
    if not raw:
        return None
    if raw.startswith(b"{") or raw.startswith(b"["):
        return json.loads(raw)
    return raw


def login(base, username, password):
    result = api(base, "POST", "/api/v1/auth/login", payload={"username": username, "password": password})
    return result["user"]["id"], result["access_token"]


def wait_until(moment):
    while True:
        seconds = (moment - datetime.now(timezone.utc)).total_seconds()
        if seconds <= 0:
            return
        time.sleep(min(seconds, 2))


def main():
    parser = argparse.ArgumentParser(description="Сквозной HTTP-демосценарий")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--credentials-file", type=Path, default=Path(".local/demo-accounts.json"))
    parser.add_argument("--output", type=Path, default=Path(".local/stage7-demo.json"))
    args = parser.parse_args()
    if args.credentials_file.exists():
        data = json.loads(args.credentials_file.read_text())
        password = data["password"]
        names = {entry["role"]: entry["username"] for entry in data["users"]}
    else:
        password = getpass("Пароль аккаунтов seed-demo: ")
        names = {role: "demo-" + role for role in ("organizer", "participant", "expert")}
    organizer_id, organizer = login(args.base_url, names["organizer"], password)
    captain_id, captain = login(args.base_url, names["participant"], password)
    expert_id, expert = login(args.base_url, names["expert"], password)
    suffix = secrets.token_hex(4)
    member_name = "demo_" + suffix
    member_password = secrets.token_urlsafe(18) + "Aa1!"
    api(args.base_url, "POST", "/api/v1/auth/register", payload={
        "username": member_name, "email": f"{member_name}@example.com",
        "password": member_password, "c_password": member_password,
    }, expected=201)
    member_id, member = login(args.base_url, member_name, member_password)

    server_time = datetime.fromisoformat(api(args.base_url, "GET", "/api/v1/time")["server_time"].replace("Z", "+00:00"))
    start = server_time + timedelta(seconds=15)
    deadline = server_time + timedelta(seconds=55)
    event = api(args.base_url, "POST", "/api/v1/organizer/hackathons", token=organizer, payload={
        "title": "Демо " + suffix, "description": "Сквозная проверка API",
        "starts_at": start.isoformat(), "deadline_at": deadline.isoformat(),
    }, expected=201)
    hid = event["id"]
    owner = f"/api/v1/organizer/hackathons/{hid}"
    case = api(args.base_url, "POST", owner + "/cases", token=organizer,
               payload={"title": "Разработка API", "description": "Рабочий сервис"}, expected=201)
    cid = case["id"]
    criteria = api(args.base_url, "PUT", owner + f"/cases/{cid}/criteria", token=organizer, payload={"criteria": [
        {"title": "Функциональность", "min_score": 0, "max_score": 10, "weight": "3"},
        {"title": "Код", "min_score": 0, "max_score": 5, "weight": "1"},
    ]})["criteria"]
    api(args.base_url, "POST", owner + "/publish", token=organizer)
    team = api(args.base_url, "POST", f"/api/v1/hackathons/{hid}/teams", token=captain,
               payload={"name": "Демо-команда"}, expected=201)
    tid = team["id"]
    invitation = api(args.base_url, "POST", f"/api/v1/teams/{tid}/invite", token=captain, expected=201)
    api(args.base_url, "POST", "/api/v1/teams/join", token=member,
        payload={"code": invitation["code"]})

    print("Хакатон и команда созданы; ожидаю серверное время начала...", flush=True)
    wait_until(start + timedelta(seconds=1))
    file = BytesIO()
    with zipfile.ZipFile(file, "w") as archive:
        archive.writestr("README.md", "Демонстрационный архив решения")
    submission = api(args.base_url, "POST", f"/api/v1/teams/{tid}/submissions", token=captain,
                     payload={"case_id": cid, "url": "https://github.com/example/demo-solution"},
                     archive=file.getvalue(), expected=201)
    sid = submission["id"]
    archive_path = f"/api/v1/submissions/{sid}/archive"
    api(args.base_url, "GET", archive_path, expected=401)
    assert api(args.base_url, "GET", archive_path, token=member) == file.getvalue()

    print("Решение сдано; ожидаю дедлайн для проверки отказа и оценивания...", flush=True)
    wait_until(deadline + timedelta(seconds=1))
    api(args.base_url, "POST", f"/api/v1/teams/{tid}/submissions", token=captain,
        payload={"case_id": cid, "url": "https://github.com/example/late"},
        archive=file.getvalue(), expected=409)
    assignment = api(args.base_url, "POST", owner + "/assignments", token=organizer,
                     payload={"team_id": tid, "case_id": cid, "expert_id": expert_id}, expected=201)
    aid = assignment["id"]
    assert api(args.base_url, "GET", archive_path, token=expert) == file.getvalue()
    scored = api(args.base_url, "PUT", f"/api/v1/expert/assignments/{aid}/scores", token=expert,
                 payload={"scores": [{"criterion_id": criteria[0]["id"], "value": 8},
                                     {"criterion_id": criteria[1]["id"], "value": 5}]})
    board = api(args.base_url, "GET", f"/api/v1/hackathons/{hid}/cases/{cid}/leaderboard")
    assert scored["total"] == "85.00" and board["entries"][0]["total"] == "85.00"
    recipient_notifications = {}
    for role, token in (("organizer", organizer), ("captain", captain), ("expert", expert)):
        recipient_notifications[role] = [item["kind"] for item in api(
            args.base_url, "GET", "/api/v1/notifications", token=token)]
    evidence = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "hackathon_id": hid, "case_id": cid, "team_id": tid,
        "submission_id": sid, "assignment_id": aid,
        "users": {"organizer_id": organizer_id, "captain_id": captain_id,
                  "member_id": member_id, "expert_id": expert_id},
        "deadline_rejected_status": 409, "anonymous_archive_status": 401,
        "archive_sha256": submission["archive"]["sha256"],
        "leaderboard": board["entries"], "notification_kinds": recipient_notifications,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(f"Готово: рейтинг {board['entries'][0]['total']}, результаты: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"Демосценарий прерван: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
