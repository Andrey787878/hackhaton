from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUserContext, get_current_user_context
from app.notification_schemas import NotificationRead, UnreadCount
from app.notification_service import NotificationError, NotificationService
from app.team_service import get_clock

router = APIRouter(prefix="/notifications", tags=["notifications"])


def service(db: Session = Depends(get_db), clock=Depends(get_clock)):
    return NotificationService(db, clock)


def call(svc, action):
    try:
        return action()
    except NotificationError as exc:
        svc.db.rollback()
        raise HTTPException(exc.status, exc.detail) from exc
    except SQLAlchemyError as exc:
        svc.db.rollback()
        raise HTTPException(503, "Временная ошибка базы данных.") from exc


@router.get("", response_model=list[NotificationRead])
def list_notifications(unread_only: bool = False, limit: int = Query(20, ge=1, le=100),
                       offset: int = Query(0, ge=0),
                       context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.list(context.user_id, unread_only, limit, offset))


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return {"count": call(svc, lambda: svc.unread_count(context.user_id))}


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(notification_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.mark_read(context.user_id, notification_id))
