from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUserContext, get_current_user_context, require_permission
from app.hackathon_schemas import CaseRead, CaseWrite, CriteriaWrite, HackathonRead, HackathonStatus, HackathonWrite, ServerTime
from app.hackathon_service import HackathonError, HackathonService, get_server_time
from app.rbac_permissions import PermissionSlugs

router = APIRouter(tags=["hackathons"])
manage = [Depends(require_permission(PermissionSlugs.MANAGE_HACKATHON))]


def service(db: Session = Depends(get_db), now: datetime = Depends(get_server_time)):
    return HackathonService(db, now)


def call(svc, action):
    try:
        return action()
    except HackathonError as exc:
        svc.db.rollback()
        raise HTTPException(exc.status, exc.detail) from exc
    except IntegrityError as exc:
        svc.db.rollback()
        raise HTTPException(409, "Конфликт данных хакатона.") from exc
    except SQLAlchemyError as exc:
        svc.db.rollback()
        raise HTTPException(503, "Временная ошибка хранилища.") from exc


@router.get("/time", response_model=ServerTime)
def server_time(now: datetime = Depends(get_server_time)):
    return {"server_time": now}


@router.get("/hackathons", response_model=list[HackathonRead])
def public_list(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), svc=Depends(service)):
    return call(svc, lambda: svc.list(None, limit, offset))


@router.get("/hackathons/{hackathon_id}", response_model=HackathonStatus)
def public_get(hackathon_id: int, svc=Depends(service)):
    item = call(svc, lambda: svc.get(hackathon_id))
    phase = "upcoming" if svc.now < item.starts_at else "active" if svc.now < item.deadline_at else "finished"
    return {"hackathon": item, "server_time": svc.now, "phase": phase, "materials_available": phase == "active"}


@router.get("/hackathons/{hackathon_id}/cases", response_model=list[CaseRead])
def public_cases(hackathon_id: int, svc=Depends(service)):
    return call(svc, lambda: svc.cases(hackathon_id, None))


@router.get("/organizer/hackathons", response_model=list[HackathonRead], dependencies=manage)
def own_list(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
             context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.list(context.user_id, limit, offset))


@router.post("/organizer/hackathons", response_model=HackathonRead, status_code=201,
             dependencies=[Depends(require_permission(PermissionSlugs.CREATE_HACKATHON))])
def create(data: HackathonWrite, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.create(context.user_id, data))


@router.get("/organizer/hackathons/{hackathon_id}", response_model=HackathonRead, dependencies=manage)
def own_get(hackathon_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.get(hackathon_id, owner=context.user_id))


@router.put("/organizer/hackathons/{hackathon_id}", response_model=HackathonRead, dependencies=manage)
def update(hackathon_id: int, data: HackathonWrite, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.update(context.user_id, hackathon_id, data))


@router.post("/organizer/hackathons/{hackathon_id}/publish", response_model=HackathonRead, dependencies=manage)
def publish(hackathon_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.publish(context.user_id, hackathon_id, True))


@router.post("/organizer/hackathons/{hackathon_id}/unpublish", response_model=HackathonRead, dependencies=manage)
def unpublish(hackathon_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.publish(context.user_id, hackathon_id, False))


@router.get("/organizer/hackathons/{hackathon_id}/cases", response_model=list[CaseRead], dependencies=manage)
def own_cases(hackathon_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.cases(hackathon_id, context.user_id))


@router.post("/organizer/hackathons/{hackathon_id}/cases", response_model=CaseRead, status_code=201, dependencies=manage)
def create_case(hackathon_id: int, data: CaseWrite, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.save_case(context.user_id, hackathon_id, data))


@router.put("/organizer/hackathons/{hackathon_id}/cases/{case_id}", response_model=CaseRead, dependencies=manage)
def update_case(hackathon_id: int, case_id: int, data: CaseWrite,
                context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.save_case(context.user_id, hackathon_id, data, case_id))


@router.put("/organizer/hackathons/{hackathon_id}/cases/{case_id}/criteria", response_model=CaseRead, dependencies=manage)
def criteria(hackathon_id: int, case_id: int, data: CriteriaWrite,
             context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.set_criteria(context.user_id, hackathon_id, case_id, data))


@router.delete("/organizer/hackathons/{hackathon_id}/cases/{case_id}", status_code=204, dependencies=manage)
def remove_case(hackathon_id: int, case_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    call(svc, lambda: svc.remove_case(context.user_id, hackathon_id, case_id))
    return Response(status_code=204)
