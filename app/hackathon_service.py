from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.hackathon_schemas import CaseWrite, CriteriaWrite, HackathonWrite
from app.models import Case, Criterion, Hackathon
from app.notification_service import record


def get_server_time() -> datetime:
    return datetime.now(timezone.utc)


class HackathonError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail


class HackathonService:
    def __init__(self, db: Session, now: datetime):
        self.db, self.now = db, now

    def get(self, hackathon_id: int, *, owner: int | None = None, lock=False) -> Hackathon:
        query = select(Hackathon).where(Hackathon.id == hackathon_id)
        if lock:
            query = query.with_for_update()
        hackathon = self.db.scalar(query)
        if hackathon is None or (owner is None and not hackathon.is_published):
            raise HackathonError(404, "Хакатон не найден.")
        if owner is not None and hackathon.organizer_id != owner:
            raise HackathonError(403, "Можно управлять только своим хакатоном.")
        return hackathon

    def list(self, owner: int | None, limit: int, offset: int):
        condition = Hackathon.is_published.is_(True) if owner is None else Hackathon.organizer_id == owner
        return list(self.db.scalars(select(Hackathon).where(condition).order_by(Hackathon.id).limit(limit).offset(offset)))

    def editable(self, hackathon: Hackathon):
        if self.now >= hackathon.starts_at:
            raise HackathonError(409, "После старта изменение конфигурации запрещено.")
        if hackathon.is_published:
            raise HackathonError(409, "Перед изменением снимите хакатон с публикации.")

    def create(self, owner: int, data: HackathonWrite):
        if data.starts_at <= self.now:
            raise HackathonError(422, "Начало должно быть в будущем.")
        hackathon = Hackathon(organizer_id=owner, **data.model_dump())
        self.db.add(hackathon)
        self.db.commit()
        self.db.refresh(hackathon)
        return hackathon

    def update(self, owner: int, hackathon_id: int, data: HackathonWrite):
        hackathon = self.get(hackathon_id, owner=owner, lock=True)
        self.editable(hackathon)
        if data.starts_at <= self.now:
            raise HackathonError(422, "Начало должно быть в будущем.")
        for key, value in data.model_dump().items():
            setattr(hackathon, key, value)
        self.db.commit()
        return hackathon

    def publish(self, owner: int, hackathon_id: int, published: bool):
        hackathon = self.get(hackathon_id, owner=owner, lock=True)
        if self.now >= hackathon.starts_at:
            raise HackathonError(409, "После старта публикацию менять нельзя.")
        if published and (not hackathon.cases or any(not case.criteria for case in hackathon.cases)):
            raise HackathonError(409, "Нужен хотя бы один кейс и критерии для каждого кейса.")
        hackathon.is_published = published
        if published:
            record(self.db, user_id=owner, actor_id=owner, kind="hackathon_published",
                   resource_type="hackathon", resource_id=hackathon.id, at=self.now)
        self.db.commit()
        return hackathon

    def cases(self, hackathon_id: int, owner: int | None):
        hackathon = self.get(hackathon_id, owner=owner)
        if owner is None and not (hackathon.starts_at <= self.now < hackathon.deadline_at):
            raise HackathonError(403, "Материалы доступны от начала до дедлайна хакатона.")
        return hackathon.cases

    def case(self, hackathon: Hackathon, case_id: int):
        case = self.db.scalar(select(Case).where(Case.id == case_id, Case.hackathon_id == hackathon.id))
        if case is None:
            raise HackathonError(404, "Кейс в этом хакатоне не найден.")
        return case

    def save_case(self, owner: int, hackathon_id: int, data: CaseWrite, case_id: int | None = None):
        hackathon = self.get(hackathon_id, owner=owner, lock=True)
        self.editable(hackathon)
        if case_id is None:
            case = Case(hackathon_id=hackathon.id, **data.model_dump())
            self.db.add(case)
        else:
            case = self.case(hackathon, case_id)
            case.title, case.description = data.title, data.description
        self.db.commit()
        self.db.refresh(case)
        return case

    def set_criteria(self, owner: int, hackathon_id: int, case_id: int, data: CriteriaWrite):
        hackathon = self.get(hackathon_id, owner=owner, lock=True)
        self.editable(hackathon)
        case = self.case(hackathon, case_id)
        self.db.execute(delete(Criterion).where(Criterion.case_id == case.id))
        for position, criterion in enumerate(data.criteria):
            self.db.add(Criterion(case_id=case.id, position=position, **criterion.model_dump()))
        self.db.commit()
        self.db.refresh(case)
        return case

    def remove_case(self, owner: int, hackathon_id: int, case_id: int):
        hackathon = self.get(hackathon_id, owner=owner, lock=True)
        self.editable(hackathon)
        self.db.delete(self.case(hackathon, case_id))
        self.db.commit()
