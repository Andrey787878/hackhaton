from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (Case, Criterion, ExpertAssignment, Hackathon, Role, Score,
                        Submission, Team, TeamMember, User, UserRole)
from app.scoring_schemas import AssignmentWrite, ScoresWrite
from app.notification_service import record
from app.submission_service import SubmissionService


class ScoringError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail


def expert_total(criteria: list[Criterion], values: dict[int, int]) -> Decimal | None:
    if not criteria or set(values) != {criterion.id for criterion in criteria}:
        return None
    if any(not criterion.min_score <= values[criterion.id] <= criterion.max_score for criterion in criteria):
        return None
    weighted = sum((criterion.weight * Decimal(values[criterion.id] - criterion.min_score)
                    / Decimal(criterion.max_score - criterion.min_score) for criterion in criteria), Decimal(0))
    return Decimal(100) * weighted / sum((criterion.weight for criterion in criteria), Decimal(0))


def rounded(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ScoringService:
    def __init__(self, db: Session, clock: Callable[[], datetime]):
        self.db, self.clock = db, clock

    def active_expert(self, uid: int) -> bool:
        return self.db.scalar(select(UserRole.id).join(Role, Role.id == UserRole.role_id).where(
            UserRole.user_id == uid, Role.slug == "expert", Role.deleted_at.is_(None),
            UserRole.deleted_at.is_(None))) is not None

    def event(self, hid: int, owner: int | None = None) -> Hackathon:
        event = self.db.get(Hackathon, hid)
        if event is None or (owner is None and not event.is_published):
            raise ScoringError(404, "Хакатон не найден.")
        if owner is not None and event.organizer_id != owner:
            raise ScoringError(403, "Можно управлять только своим хакатоном.")
        return event

    def case(self, hid: int, cid: int) -> Case:
        item = self.db.scalar(select(Case).where(Case.id == cid, Case.hackathon_id == hid))
        if item is None:
            raise ScoringError(404, "Кейс этого хакатона не найден.")
        return item

    def ensure_finished(self, event: Hackathon):
        if not event.is_published or self.clock() < event.deadline_at:
            raise ScoringError(409, "Оценивание доступно после дедлайна опубликованного хакатона.")

    def latest(self, tid: int, cid: int) -> Submission | None:
        return self.db.scalar(select(Submission).where(Submission.team_id == tid, Submission.case_id == cid)
                              .order_by(Submission.submitted_at.desc(), Submission.id.desc()).limit(1))

    def assign(self, hid: int, owner: int, data: AssignmentWrite):
        event = self.event(hid, owner)
        self.ensure_finished(event)
        self.case(hid, data.case_id)
        team = self.db.get(Team, data.team_id)
        if team is None or team.hackathon_id != hid:
            raise ScoringError(404, "Команда этого хакатона не найдена.")
        if self.db.get(User, data.expert_id) is None or not self.active_expert(data.expert_id):
            raise ScoringError(422, "Пользователь не имеет активной роли эксперта.")
        if self.db.scalar(select(TeamMember.id).where(TeamMember.team_id == team.id,
                                                       TeamMember.user_id == data.expert_id)) is not None:
            raise ScoringError(409, "Участник команды не может оценивать её решение.")
        submission = self.latest(team.id, data.case_id)
        if submission is None:
            raise ScoringError(404, "У команды нет сдачи по этому кейсу.")
        if self.db.scalar(select(ExpertAssignment.id).where(
                ExpertAssignment.submission_id == submission.id,
                ExpertAssignment.expert_id == data.expert_id)) is not None:
            raise ScoringError(409, "Эксперт уже назначен на это решение.")
        assignment = ExpertAssignment(submission_id=submission.id, expert_id=data.expert_id, assigned_by=owner)
        self.db.add(assignment)
        self.db.flush()
        record(self.db, user_id=data.expert_id, actor_id=owner, kind="expert_assigned",
               resource_type="assignment", resource_id=assignment.id, at=self.clock())
        self.db.commit()
        return self.read(assignment)

    def assignment(self, aid: int, uid: int, *, lock=False) -> ExpertAssignment:
        query = select(ExpertAssignment).where(ExpertAssignment.id == aid)
        if lock:
            query = query.with_for_update()
        item = self.db.scalar(query)
        if item is None:
            raise ScoringError(404, "Назначение не найдено.")
        if item.expert_id != uid or not self.active_expert(uid):
            raise ScoringError(403, "Доступно только назначенному эксперту.")
        return item

    def criteria(self, cid: int) -> list[Criterion]:
        return list(self.db.scalars(select(Criterion).where(Criterion.case_id == cid).order_by(Criterion.position)))

    def read(self, item: ExpertAssignment):
        submission = item.submission
        criteria = self.criteria(submission.case_id)
        scores = sorted(item.scores, key=lambda score: next(
            (criterion.position for criterion in criteria if criterion.id == score.criterion_id), 1000))
        values = {score.criterion_id: score.value for score in scores}
        total = expert_total(criteria, values)
        return dict(id=item.id, expert_id=item.expert_id, assigned_at=item.assigned_at,
                    submission=SubmissionService.result(submission), criteria=criteria,
                    scores=[dict(criterion_id=score.criterion_id, value=score.value) for score in scores],
                    complete=total is not None, total=rounded(total) if total is not None else None)

    def assigned(self, uid: int, limit: int, offset: int):
        if not self.active_expert(uid):
            raise ScoringError(403, "Нужна активная роль эксперта.")
        items = self.db.scalars(select(ExpertAssignment).where(ExpertAssignment.expert_id == uid)
                                .order_by(ExpertAssignment.id).limit(limit).offset(offset))
        return [self.read(item) for item in items]

    def organizer_assignments(self, hid: int, owner: int, limit: int, offset: int):
        self.event(hid, owner)
        items = self.db.scalars(select(ExpertAssignment).join(Submission).join(
            Team, Team.id == Submission.team_id).where(Team.hackathon_id == hid)
            .order_by(ExpertAssignment.id).limit(limit).offset(offset))
        return [self.read(item) for item in items]

    def score(self, aid: int, uid: int, data: ScoresWrite):
        item = self.assignment(aid, uid, lock=True)
        event = self.event(self.db.get(Team, item.submission.team_id).hackathon_id)
        self.ensure_finished(event)
        criteria = self.criteria(item.submission.case_id)
        by_id = {criterion.id: criterion for criterion in criteria}
        for score in data.scores:
            criterion = by_id.get(score.criterion_id)
            if criterion is None:
                raise ScoringError(422, "Критерий не принадлежит кейсу решения.")
            if not criterion.min_score <= score.value <= criterion.max_score:
                raise ScoringError(422, "Балл вне диапазона критерия.")
        self.db.execute(delete(Score).where(Score.assignment_id == aid))
        for score in data.scores:
            self.db.add(Score(assignment_id=aid, criterion_id=score.criterion_id, value=score.value))
        if set(score.criterion_id for score in data.scores) == set(by_id):
            record(self.db, user_id=self.db.get(Team, item.submission.team_id).captain_id,
                   actor_id=uid, kind="score_completed", resource_type="submission",
                   resource_id=item.submission_id, at=self.clock())
        self.db.commit()
        self.db.refresh(item)
        return self.read(item)

    def leaderboard(self, hid: int, cid: int):
        event = self.event(hid)
        self.ensure_finished(event)
        self.case(hid, cid)
        criteria = self.criteria(cid)
        teams = list(self.db.scalars(select(Team).where(Team.hackathon_id == hid).order_by(Team.id)))
        latest = {team.id: self.latest(team.id, cid) for team in teams}
        ids = [item.id for item in latest.values() if item is not None]
        assignments = list(self.db.scalars(select(ExpertAssignment).where(
            ExpertAssignment.submission_id.in_(ids)))) if ids else []
        totals = defaultdict(list)
        submissions_by_id = {item.id: item for item in latest.values() if item is not None}
        for assignment in assignments:
            values = {score.criterion_id: score.value for score in assignment.scores}
            total = expert_total(criteria, values)
            if total is not None and self.active_expert(assignment.expert_id):
                totals[submissions_by_id[assignment.submission_id].team_id].append(total)
        entries = []
        for team in teams:
            if totals[team.id]:
                mean = sum(totals[team.id], Decimal(0)) / len(totals[team.id])
                entries.append(dict(team_id=team.id, team_name=team.name, case_id=cid,
                                    total=rounded(mean), expert_count=len(totals[team.id])))
        entries.sort(key=lambda row: (-row["total"], row["team_id"]))
        for position, entry in enumerate(entries, 1):
            entry["rank"] = position if position == 1 or entry["total"] != entries[position - 2]["total"] else entries[position - 2]["rank"]
        return dict(hackathon_id=hid, case_id=cid, entries=entries)
