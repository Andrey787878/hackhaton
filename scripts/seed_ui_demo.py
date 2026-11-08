"""Наполнить локальный стенд данными для демонстрации веб-интерфейса.

Создаёт через HTTP API три опубликованных хакатона: идущий (приём решений открыт),
будущий и завершённый с оценками экспертов и рейтингом. Нужны аккаунты
`seed-demo` и файл `.local/demo-accounts.json` (см. docs/DEMO.md).
Логины созданных участников и их пароли пишутся только в игнорируемый
`.local/ui-demo.json`.
"""
import argparse
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
import secrets
import zipfile

from demo_journey import api, login, wait_until


CRITERIA = [
    {"title": "Функциональность", "description": "Сценарии работают end-to-end", "min_score": 0, "max_score": 10, "weight": "3"},
    {"title": "Качество кода", "description": "Структура, тесты, README", "min_score": 0, "max_score": 5, "weight": "1"},
    {"title": "Презентация", "description": "Демо за 5 минут", "min_score": 1, "max_score": 5, "weight": "1"},
]


def server_now(base):
    return datetime.fromisoformat(api(base, "GET", "/api/v1/time")["server_time"].replace("Z", "+00:00"))


def register(base, prefix):
    name = f"{prefix}-{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(12) + "Aa1!"
    api(base, "POST", "/api/v1/auth/register", payload={
        "username": name, "email": f"{name}@example.com", "password": password,
        "c_password": password, "display_name": prefix.replace("-", " ").title(),
    }, expected=201)
    uid, token = login(base, name, password)
    return {"id": uid, "username": name, "password": password, "token": token}


def event(base, token, title, description, start, deadline, cases):
    created = api(base, "POST", "/api/v1/organizer/hackathons", token=token, payload={
        "title": title, "description": description,
        "starts_at": start.isoformat(), "deadline_at": deadline.isoformat(),
    }, expected=201)
    owner = f"/api/v1/organizer/hackathons/{created['id']}"
    result = []
    for case_title, case_text in cases:
        case = api(base, "POST", owner + "/cases", token=token,
                   payload={"title": case_title, "description": case_text}, expected=201)
        case = api(base, "PUT", owner + f"/cases/{case['id']}/criteria", token=token, payload={"criteria": CRITERIA})
        result.append(case)
    api(base, "POST", owner + "/publish", token=token)
    return created["id"], result


def archive(name):
    file = BytesIO()
    with zipfile.ZipFile(file, "w") as zf:
        zf.writestr("README.md", f"# {name}\n\nДемонстрационное решение.")
    return file.getvalue()


def main():
    parser = argparse.ArgumentParser(description="Демоданные для фронтенда")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--credentials-file", type=Path, default=Path(".local/demo-accounts.json"))
    parser.add_argument("--output", type=Path, default=Path(".local/ui-demo.json"))
    args = parser.parse_args()
    base = args.base_url
    accounts = json.loads(args.credentials_file.read_text())
    names = {entry["role"]: entry["username"] for entry in accounts["users"]}
    _, organizer = login(base, names["organizer"], accounts["password"])
    captain_id, captain = login(base, names["participant"], accounts["password"])
    expert_id, expert = login(base, names["expert"], accounts["password"])
    users = {key: register(base, key) for key in ("anna-red", "max-blue", "ira-dark", "lev-member")}

    # 1. Будущий хакатон: материалы закрыты, команды уже можно собирать.
    now = server_now(base)
    upcoming, _ = event(base, organizer, "Winter Data Cup",
                        "Аналитика данных городского транспорта. Старт через два дня.",
                        now + timedelta(days=2), now + timedelta(days=4),
                        [("Прогноз пассажиропотока", "Модель и дашборд прогноза загрузки маршрутов.")])

    # 2. Завершённый хакатон: три команды, оценка эксперта, рейтинг.
    now = server_now(base)
    start, deadline = now + timedelta(seconds=20), now + timedelta(seconds=70)
    finished, finished_cases = event(base, organizer, "Neon Night Hack",
                                     "Ночной спринт: сервисы реального времени за 24 часа.",
                                     start, deadline,
                                     [("Realtime-чат", "Чат с комнатами и историей сообщений."),
                                      ("Мониторинг", "Панель метрик с алертами.")])
    teams = []
    for (key, team_name) in (("anna-red", "Red Comet"), ("max-blue", "Blue Shift"), ("ira-dark", "Dark Matter")):
        team = api(base, "POST", f"/api/v1/hackathons/{finished}/teams", token=users[key]["token"],
                   payload={"name": team_name}, expected=201)
        teams.append((key, team))

    # 3. Идущий хакатон: приём открыт ещё три часа.
    now = server_now(base)
    active_start, active_deadline = now + timedelta(seconds=15), now + timedelta(hours=3)
    active, active_cases = event(base, organizer, "Blue & Red AI Hackathon",
                                 "Интеллектуальные сервисы для онлайн-образования: ассистенты, проверка "
                                 "заданий и аналитика прогресса студентов.",
                                 active_start, active_deadline,
                                 [("AI-ассистент преподавателя", "Помощник, который готовит задания и разбирает ответы."),
                                  ("Аналитика обучения", "Дашборд прогресса группы с рекомендациями.")])
    own = api(base, "POST", f"/api/v1/hackathons/{active}/teams", token=captain,
              payload={"name": "Pulse Squad"}, expected=201)
    code = api(base, "POST", f"/api/v1/teams/{own['id']}/invite", token=captain, expected=201)["code"]
    api(base, "POST", "/api/v1/teams/join", token=users["lev-member"]["token"], payload={"code": code})
    rival = api(base, "POST", f"/api/v1/hackathons/{active}/teams", token=users["anna-red"]["token"],
                payload={"name": "Red Comet"}, expected=201)

    print("Хакатоны созданы; жду старта по серверному времени…", flush=True)
    wait_until(max(start, active_start) + timedelta(seconds=1))
    for key, team in teams:
        for case in finished_cases:
            api(base, "POST", f"/api/v1/teams/{team['id']}/submissions", token=users[key]["token"],
                payload={"case_id": case["id"], "url": f"https://github.com/example/{team['name'].lower().replace(' ', '-')}"},
                archive=archive(team["name"]), expected=201)
    api(base, "POST", f"/api/v1/teams/{rival['id']}/submissions", token=users["anna-red"]["token"],
        payload={"case_id": active_cases[0]["id"], "url": "https://github.com/example/red-comet-ai"},
        archive=archive("Red Comet AI"), expected=201)

    print("Решения сданы; жду дедлайна завершённого хакатона…", flush=True)
    wait_until(deadline + timedelta(seconds=1))
    owner = f"/api/v1/organizer/hackathons/{finished}"
    marks = {"Red Comet": [(9, 4, 5), (7, 5, 4)], "Blue Shift": [(8, 5, 4), (9, 4, 5)], "Dark Matter": [(6, 3, 3), (8, 3, 4)]}
    pending = None
    for _, team in teams:
        for index, case in enumerate(finished_cases):
            assignment = api(base, "POST", owner + "/assignments", token=organizer,
                             payload={"team_id": team["id"], "case_id": case["id"], "expert_id": expert_id}, expected=201)
            if team["name"] == "Dark Matter" and index == 1:
                pending = assignment["id"]  # оставим для демонстрации формы эксперта
                continue
            values = marks[team["name"]][index]
            api(base, "PUT", f"/api/v1/expert/assignments/{assignment['id']}/scores", token=expert, payload={
                "scores": [{"criterion_id": c["id"], "value": v} for c, v in zip(case["criteria"], values)]})

    result = {
        "hackathons": {"upcoming": upcoming, "active": active, "finished": finished},
        "active_team": own["id"], "pending_assignment": pending, "captain_id": captain_id,
        "users": {key: {k: v for k, v in value.items() if k != "token"} for key, value in users.items()},
    }
    args.output.parent.mkdir(exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "users"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
