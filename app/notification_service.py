from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Notification

TITLES = {
    "hackathon_published": "Хакатон опубликован",
    "team_joined": "Участник вступил в команду",
    "submission_created": "Команда сдала решение",
    "expert_assigned": "Вам назначено решение",
    "score_completed": "Решение оценено",
}


def record(db: Session, *, user_id: int, actor_id: int, kind: str,
           resource_type: str, resource_id: int, at: datetime) -> None:
    if kind not in TITLES:
        raise ValueError("Неизвестный тип уведомления.")
    db.add(Notification(user_id=user_id, actor_id=actor_id, kind=kind,
                        resource_type=resource_type, resource_id=resource_id,
                        created_at=at))


class NotificationError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail


class NotificationService:
    def __init__(self, db: Session, clock):
        self.db, self.clock = db, clock

    @staticmethod
    def result(item: Notification):
        return dict(id=item.id, kind=item.kind, title=TITLES[item.kind],
                    actor_id=item.actor_id, resource_type=item.resource_type,
                    resource_id=item.resource_id, created_at=item.created_at,
                    read_at=item.read_at)

    def list(self, uid: int, unread_only: bool, limit: int, offset: int):
        query = select(Notification).where(Notification.user_id == uid)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        return [self.result(item) for item in self.db.scalars(
            query.order_by(Notification.id.desc()).limit(limit).offset(offset))]

    def unread_count(self, uid: int) -> int:
        return self.db.scalar(select(func.count(Notification.id)).where(
            Notification.user_id == uid, Notification.read_at.is_(None)))

    def mark_read(self, uid: int, nid: int):
        item = self.db.scalar(select(Notification).where(
            Notification.id == nid, Notification.user_id == uid).with_for_update())
        if item is None:
            raise NotificationError(404, "Уведомление не найдено.")
        if item.read_at is None:
            item.read_at = self.clock()
            self.db.commit()
        return self.result(item)
