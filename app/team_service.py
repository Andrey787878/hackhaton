import hashlib
import secrets
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.hackathon_service import get_server_time
from app.models import Hackathon, Invite, Team, TeamMember
from app.notification_service import record


def get_clock():
    return get_server_time


class TeamError(Exception):
    def __init__(self, status, detail):
        self.status, self.detail = status, detail


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("ascii")).hexdigest()


class TeamService:
    def __init__(self, db: Session, clock: Callable[[], datetime]):
        self.db, self.clock = db, clock

    def hackathon(self, hid, *, lock=False):
        query = select(Hackathon).where(Hackathon.id == hid)
        if lock:
            query = query.with_for_update()
        result = self.db.scalar(query)
        if result is None:
            raise TeamError(404, "Хакатон не найден.")
        return result

    def open(self, hackathon):
        if not hackathon.is_published:
            raise TeamError(409, "Формирование команд доступно только для опубликованного хакатона.")
        # Check time after acquiring locks, not at the start of a waiting request.
        if self.clock() >= hackathon.deadline_at:
            raise TeamError(409, "Дедлайн прошёл: состав и приглашения изменять нельзя.")

    def team(self, tid):
        team = self.db.get(Team, tid)
        if team is None:
            raise TeamError(404, "Команда не найдена.")
        return team

    def locked_team(self, tid):
        hid = self.db.scalar(select(Team.hackathon_id).where(Team.id == tid))
        if hid is None:
            raise TeamError(404, "Команда не найдена.")
        hackathon = self.hackathon(hid, lock=True)
        team = self.db.scalar(select(Team).where(Team.id == tid).with_for_update())
        return team, hackathon

    def captain(self, team, uid):
        if team.captain_id != uid:
            raise TeamError(403, "Операция доступна только капитану этой команды.")

    def no_membership(self, hid, uid):
        if self.db.scalar(select(TeamMember.id).where(TeamMember.hackathon_id == hid, TeamMember.user_id == uid)):
            raise TeamError(409, "Пользователь уже состоит в команде этого хакатона.")

    def result(self, team):
        return dict(id=team.id, hackathon_id=team.hackathon_id, captain_id=team.captain_id,
            name=team.name, created_at=team.created_at,
            members=[dict(user_id=m.user_id, username=m.user.username,
                          display_name=m.user.display_name, joined_at=m.joined_at) for m in team.members])

    def create(self, hid, uid, name):
        hackathon = self.hackathon(hid, lock=True)
        self.open(hackathon)
        self.no_membership(hid, uid)
        team = Team(hackathon_id=hid, captain_id=uid, name=name)
        self.db.add(team)
        self.db.flush()
        self.db.add(TeamMember(team_id=team.id, hackathon_id=hid, user_id=uid))
        self.db.commit()
        return self.result(team)

    def read(self, tid, uid):
        team = self.team(tid)
        if not self.db.scalar(select(TeamMember.id).where(TeamMember.team_id == tid, TeamMember.user_id == uid)):
            raise TeamError(403, "Состав команды доступен только её участникам.")
        return self.result(team)

    def mine(self, uid, limit, offset):
        teams = self.db.scalars(select(Team).join(TeamMember, TeamMember.team_id == Team.id)
                               .where(TeamMember.user_id == uid).order_by(Team.id).limit(limit).offset(offset))
        return [self.result(team) for team in teams]

    def organizer_list(self, hid, uid, limit, offset):
        hackathon = self.hackathon(hid)
        if hackathon.organizer_id != uid:
            raise TeamError(403, "Можно просматривать команды только своего хакатона.")
        teams = self.db.scalars(select(Team).where(Team.hackathon_id == hid).order_by(Team.id).limit(limit).offset(offset))
        return [self.result(team) for team in teams]

    def rename(self, tid, uid, name):
        team, hackathon = self.locked_team(tid)
        self.captain(team, uid)
        self.open(hackathon)
        team.name = name
        self.db.commit()
        return self.result(team)

    def invite_info(self, tid, uid):
        team = self.team(tid)
        self.captain(team, uid)
        hackathon = self.hackathon(team.hackathon_id)
        invite = self.db.scalar(select(Invite).where(Invite.team_id == tid, Invite.revoked_at.is_(None)))
        return dict(team_id=tid, active=bool(invite and hackathon.is_published and self.clock() < hackathon.deadline_at),
                    created_at=invite.created_at if invite else None, expires_at=hackathon.deadline_at)

    def issue(self, tid, uid):
        team, hackathon = self.locked_team(tid)
        self.captain(team, uid)
        self.open(hackathon)
        now = self.clock()
        self.db.execute(update(Invite).where(Invite.team_id == tid, Invite.revoked_at.is_(None)).values(revoked_at=now))
        code = secrets.token_urlsafe(32)
        self.db.add(Invite(team_id=tid, code_hash=hash_code(code), created_at=now))
        self.db.commit()
        return dict(team_id=tid, active=True, created_at=now, expires_at=hackathon.deadline_at, code=code)

    def revoke(self, tid, uid):
        team, _ = self.locked_team(tid)
        self.captain(team, uid)
        # Revocation remains available even after the deadline.
        self.db.execute(update(Invite).where(Invite.team_id == tid, Invite.revoked_at.is_(None)).values(revoked_at=self.clock()))
        self.db.commit()

    def join(self, uid, code):
        digest = hash_code(code)
        tid = self.db.scalar(select(Invite.team_id).where(Invite.code_hash == digest))
        if tid is None:
            raise TeamError(404, "Код приглашения недействителен.")
        team, hackathon = self.locked_team(tid)
        invite = self.db.scalar(select(Invite).where(Invite.code_hash == digest).with_for_update())
        if invite is None or invite.revoked_at is not None:
            raise TeamError(404, "Код приглашения недействителен.")
        self.open(hackathon)
        self.no_membership(hackathon.id, uid)
        self.db.add(TeamMember(team_id=tid, hackathon_id=hackathon.id, user_id=uid))
        record(self.db, user_id=team.captain_id, actor_id=uid, kind="team_joined",
               resource_type="team", resource_id=tid, at=self.clock())
        self.db.commit()
        self.db.expire(team, ["members"])
        return self.result(team)
