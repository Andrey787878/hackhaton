from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUserContext, get_current_user_context, require_permission
from app.team_schemas import InviteCreated, InviteRead, JoinTeam, TeamRead, TeamWrite
from app.team_service import TeamError, TeamService, get_clock

router = APIRouter(tags=["teams"])


def service(db: Session = Depends(get_db), clock=Depends(get_clock)):
    return TeamService(db, clock)


def call(svc, action):
    try:
        return action()
    except TeamError as exc:
        svc.db.rollback()
        raise HTTPException(exc.status, exc.detail) from exc
    except IntegrityError as exc:
        svc.db.rollback()
        raise HTTPException(409, "Название занято или пользователь уже состоит в команде хакатона.") from exc
    except SQLAlchemyError as exc:
        svc.db.rollback()
        raise HTTPException(503, "Временная ошибка хранилища.") from exc


@router.post("/hackathons/{hackathon_id}/teams", response_model=TeamRead, status_code=201,
             dependencies=[Depends(require_permission("create-team"))])
def create(hackathon_id: int, data: TeamWrite, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.create(hackathon_id, context.user_id, data.name))


@router.get("/teams", response_model=list[TeamRead])
def mine(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
         context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.mine(context.user_id, limit, offset))


@router.post("/teams/join", response_model=TeamRead, dependencies=[Depends(require_permission("join-team"))])
def join(data: JoinTeam, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.join(context.user_id, data.code))


@router.get("/teams/{team_id}", response_model=TeamRead)
def read(team_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.read(team_id, context.user_id))


@router.patch("/teams/{team_id}", response_model=TeamRead)
def rename(team_id: int, data: TeamWrite, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.rename(team_id, context.user_id, data.name))


@router.post("/teams/{team_id}/invite", response_model=InviteCreated, status_code=201)
def issue(team_id: int, response: Response, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    response.headers["Cache-Control"] = "no-store"
    return call(svc, lambda: svc.issue(team_id, context.user_id))


@router.get("/teams/{team_id}/invite", response_model=InviteRead)
def info(team_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.invite_info(team_id, context.user_id))


@router.delete("/teams/{team_id}/invite", status_code=204)
def revoke(team_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    call(svc, lambda: svc.revoke(team_id, context.user_id))
    return Response(status_code=204)


@router.get("/organizer/hackathons/{hackathon_id}/teams", response_model=list[TeamRead],
            dependencies=[Depends(require_permission("manage-hackathon"))])
def organizer_list(hackathon_id: int, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                   context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.organizer_list(hackathon_id, context.user_id, limit, offset))
