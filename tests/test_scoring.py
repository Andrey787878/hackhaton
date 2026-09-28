from io import BytesIO
import zipfile

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ExpertAssignment, Role, Score, UserRole
from test_teams import END, EVENT, START, client, clock_state, user


@pytest.fixture
def scenario(client, user, clock_state):
    _, organizer = user("organizer")
    created = client.post("/api/v1/organizer/hackathons", json=EVENT, headers=organizer)
    assert created.status_code == 201, created.text
    hid = created.json()["id"]
    base = f"/api/v1/organizer/hackathons/{hid}"
    case = client.post(base + "/cases", json={"title": "Кейс", "description": "Описание"}, headers=organizer)
    assert case.status_code == 201, case.text
    cid = case.json()["id"]
    criteria = client.put(base + f"/cases/{cid}/criteria", json={"criteria": [
        {"title": "Функциональность", "min_score": 0, "max_score": 10, "weight": "3"},
        {"title": "Код", "min_score": 0, "max_score": 5, "weight": "1"},
    ]}, headers=organizer)
    assert criteria.status_code == 200, criteria.text
    ids = [item["id"] for item in criteria.json()["criteria"]]
    assert client.post(base + "/publish", headers=organizer).status_code == 200
    clock_state["now"] = START
    return hid, cid, ids, organizer


def make_submission(client, user, scenario, name="Alpha", url="https://github.com/example/work", archive=None):
    hid, cid, _, _ = scenario
    _, captain = user()
    team = client.post(f"/api/v1/hackathons/{hid}/teams", json={"name": name}, headers=captain)
    assert team.status_code == 201, team.text
    tid = team.json()["id"]
    files = {"archive": ("solution.zip", archive, "application/zip")} if archive else None
    submission = client.post(f"/api/v1/teams/{tid}/submissions", data={"case_id": cid, "url": url},
                             files=files, headers=captain)
    assert submission.status_code == 201, submission.text
    return tid, captain, submission.json()["id"]


def assign(client, scenario, tid, expert_id):
    hid, cid, _, organizer = scenario
    return client.post(f"/api/v1/organizer/hackathons/{hid}/assignments",
                       json={"team_id": tid, "case_id": cid, "expert_id": expert_id}, headers=organizer)


def score(client, aid, headers, values):
    return client.put(f"/api/v1/expert/assignments/{aid}/scores",
                      json={"scores": values}, headers=headers)


def board(client, scenario):
    hid, cid, _, _ = scenario
    return client.get(f"/api/v1/hackathons/{hid}/cases/{cid}/leaderboard")


def test_assignment_uses_latest_submission_and_scopes_expert(client, user, scenario, clock_state):
    tid, captain, old_id = make_submission(client, user, scenario)
    second = client.post(f"/api/v1/teams/{tid}/submissions",
                         data={"case_id": scenario[1], "url": "https://github.com/example/new"}, headers=captain)
    assert second.status_code == 201
    latest_id = second.json()["id"]
    expert_id, expert = user("expert")
    other_id, other = user("expert")
    assert assign(client, scenario, tid, expert_id).status_code == 409
    clock_state["now"] = END
    created = assign(client, scenario, tid, expert_id)
    assert created.status_code == 201, created.text
    aid = created.json()["id"]
    assert created.json()["submission"]["id"] == latest_id
    assert len(created.json()["criteria"]) == 2
    assert assign(client, scenario, tid, expert_id).status_code == 409
    assert client.get("/api/v1/expert/assignments", headers=expert).json()[0]["id"] == aid
    assert client.get(f"/api/v1/expert/assignments/{aid}", headers=other).status_code == 403
    assert client.get(f"/api/v1/submissions/{latest_id}", headers=expert).status_code == 200
    assert client.get(f"/api/v1/submissions/{old_id}", headers=expert).status_code == 403
    assert client.get(f"/api/v1/submissions/{latest_id}", headers=other).status_code == 403
    assert client.get(f"/api/v1/submissions/{latest_id}").status_code == 401
    assert client.get("/api/v1/expert/assignments", headers=captain).status_code == 403
    assert other_id != expert_id


def test_archive_access_for_assigned_expert(client, user, scenario, clock_state):
    memory = BytesIO()
    with zipfile.ZipFile(memory, "w") as archive:
        archive.writestr("readme.txt", "Решение")
    tid, _, sid = make_submission(client, user, scenario, archive=memory.getvalue())
    expert_id, expert = user("expert")
    _, outsider = user("expert")
    clock_state["now"] = END
    assert assign(client, scenario, tid, expert_id).status_code == 201
    path = f"/api/v1/submissions/{sid}/archive"
    assert client.get(path, headers=expert).content == memory.getvalue()
    assert client.get(path, headers=outsider).status_code == 403


def test_weighted_total_partial_scores_and_public_board(client, user, scenario, clock_state):
    tid, _, _ = make_submission(client, user, scenario)
    expert_id, expert = user("expert")
    assert board(client, scenario).status_code == 409
    clock_state["now"] = END
    aid = assign(client, scenario, tid, expert_id).json()["id"]
    first, second = scenario[2]
    partial = score(client, aid, expert, [{"criterion_id": first, "value": 8}])
    assert partial.status_code == 200, partial.text
    assert partial.json()["complete"] is False and partial.json()["total"] is None
    assert board(client, scenario).json()["entries"] == []
    full = score(client, aid, expert, [{"criterion_id": first, "value": 8},
                                       {"criterion_id": second, "value": 5}])
    assert full.status_code == 200, full.text
    assert full.json()["complete"] is True
    assert full.json()["total"] == "85.00"
    entries = board(client, scenario).json()["entries"]
    assert entries == [{"rank": 1, "team_id": tid, "team_name": "Alpha",
                        "case_id": scenario[1], "total": "85.00", "expert_count": 1}]
    with SessionLocal() as db:
        assert len(list(db.scalars(select(Score).where(Score.assignment_id == aid)))) == 2


def test_mean_of_experts_and_deterministic_tie_order(client, user, scenario, clock_state):
    first_tid, _, _ = make_submission(client, user, scenario, name="Alpha")
    second_tid, _, _ = make_submission(client, user, scenario, name="Beta")
    first_expert_id, first_expert = user("expert")
    second_expert_id, second_expert = user("expert")
    clock_state["now"] = END
    a1 = assign(client, scenario, first_tid, first_expert_id).json()["id"]
    a2 = assign(client, scenario, first_tid, second_expert_id).json()["id"]
    b1 = assign(client, scenario, second_tid, first_expert_id).json()["id"]
    first, second = scenario[2]
    assert score(client, a1, first_expert, [{"criterion_id": first, "value": 10},
                                            {"criterion_id": second, "value": 5}]).status_code == 200
    assert score(client, a2, second_expert, [{"criterion_id": first, "value": 6},
                                             {"criterion_id": second, "value": 5}]).status_code == 200
    assert score(client, b1, first_expert, [{"criterion_id": first, "value": 8},
                                            {"criterion_id": second, "value": 5}]).status_code == 200
    entries = board(client, scenario).json()["entries"]
    assert [(row["team_id"], row["rank"], row["total"], row["expert_count"]) for row in entries] == [
        (first_tid, 1, "85.00", 2), (second_tid, 1, "85.00", 1)]
    assert board(client, scenario).json()["entries"] == entries
    changed = score(client, a2, second_expert, [{"criterion_id": first, "value": 5},
                                              {"criterion_id": second, "value": 5}])
    assert changed.status_code == 200
    assert board(client, scenario).json()["entries"][0]["team_id"] == second_tid


def test_invalid_scores_do_not_change_previous_result(client, user, scenario, clock_state):
    tid, _, _ = make_submission(client, user, scenario)
    expert_id, expert = user("expert")
    clock_state["now"] = END
    aid = assign(client, scenario, tid, expert_id).json()["id"]
    first, second = scenario[2]
    assert score(client, aid, expert, [{"criterion_id": first, "value": 7},
                                      {"criterion_id": second, "value": 4}]).status_code == 200
    original = board(client, scenario).json()["entries"]
    for payload in (
        {"scores": [{"criterion_id": first, "value": 11}]},
        {"scores": [{"criterion_id": 999999, "value": 5}]},
        {"scores": [{"criterion_id": first, "value": 5}, {"criterion_id": first, "value": 6}]},
        {"scores": [{"criterion_id": first, "value": 5}], "total": 100},
        {"scores": [{"criterion_id": first, "value": 1.5}]},
    ):
        result = client.put(f"/api/v1/expert/assignments/{aid}/scores", json=payload, headers=expert)
        assert result.status_code == 422, result.text
        assert board(client, scenario).json()["entries"] == original


def test_assignment_owner_role_and_team_membership(client, user, scenario, clock_state):
    tid, captain, sid = make_submission(client, user, scenario)
    expert_id, expert = user("expert")
    _, other_organizer = user("organizer")
    clock_state["now"] = END
    assert client.post(f"/api/v1/organizer/hackathons/{scenario[0]}/assignments",
                       json={"team_id": tid, "case_id": scenario[1], "expert_id": expert_id},
                       headers=other_organizer).status_code == 403
    assert assign(client, scenario, tid, expert_id).status_code == 201
    assert client.get(f"/api/v1/organizer/hackathons/{scenario[0]}/assignments",
                      headers=other_organizer).status_code == 403
    assert assign(client, scenario, tid, user()[0]).status_code == 422
    assert client.put(f"/api/v1/expert/assignments/999999/scores", json={"scores": []},
                      headers=expert).status_code == 404
    assert sid > 0 and captain


def test_revoked_expert_loses_file_access_and_ranking_count(client, user, scenario, clock_state):
    tid, _, sid = make_submission(client, user, scenario)
    expert_id, expert = user("expert")
    clock_state["now"] = END
    aid = assign(client, scenario, tid, expert_id).json()["id"]
    first, second = scenario[2]
    assert score(client, aid, expert, [{"criterion_id": first, "value": 8},
                                      {"criterion_id": second, "value": 5}]).status_code == 200
    assert len(board(client, scenario).json()["entries"]) == 1
    with SessionLocal.begin() as db:
        assignment = db.scalar(select(UserRole).join(Role, Role.id == UserRole.role_id).where(
            UserRole.user_id == expert_id, Role.slug == "expert", UserRole.deleted_at.is_(None)))
        assignment.deleted_at = clock_state["now"]
    assert client.get("/api/v1/expert/assignments", headers=expert).status_code == 403
    assert client.get(f"/api/v1/submissions/{sid}", headers=expert).status_code == 403
    assert board(client, scenario).json()["entries"] == []


def test_empty_and_draft_leaderboard(client, user, scenario, clock_state):
    clock_state["now"] = END
    result = board(client, scenario)
    assert result.status_code == 200 and result.json()["entries"] == []
    assert client.get(f"/api/v1/hackathons/{scenario[0]}/cases/999999/leaderboard").status_code == 404
    assert client.get("/api/v1/hackathons/999999/cases/1/leaderboard").status_code == 404


def test_assignment_is_persisted_once(client, user, scenario, clock_state):
    tid, _, sid = make_submission(client, user, scenario)
    expert_id, _ = user("expert")
    clock_state["now"] = END
    first = assign(client, scenario, tid, expert_id)
    assert first.status_code == 201
    with SessionLocal() as db:
        assignments = list(db.scalars(select(ExpertAssignment).where(
            ExpertAssignment.submission_id == sid, ExpertAssignment.expert_id == expert_id)))
        assert len(assignments) == 1
