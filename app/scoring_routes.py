from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import CurrentUserContext, get_current_user_context, require_permission
from app.rbac_permissions import PermissionSlugs
from app.scoring_schemas import AssignmentRead, AssignmentWrite, LeaderboardRead, ScoresWrite
from app.scoring_service import ScoringError, ScoringService
from app.team_service import get_clock

router = APIRouter(tags=["scoring"])


def service(db: Session = Depends(get_db), clock=Depends(get_clock)):
    return ScoringService(db, clock)


def call(svc, action):
    try:
        return action()
    except ScoringError as exc:
        svc.db.rollback()
        raise HTTPException(exc.status, exc.detail) from exc
    except IntegrityError as exc:
        svc.db.rollback()
        raise HTTPException(409, "Конфликт данных оценки.") from exc
    except SQLAlchemyError as exc:
        svc.db.rollback()
        raise HTTPException(503, "Временная ошибка базы данных.") from exc


@router.post("/organizer/hackathons/{hackathon_id}/assignments", response_model=AssignmentRead,
             status_code=201, dependencies=[Depends(require_permission(PermissionSlugs.ASSIGN_EXPERT))])
def assign(hackathon_id: int, data: AssignmentWrite,
           context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.assign(hackathon_id, context.user_id, data))


@router.get("/organizer/hackathons/{hackathon_id}/assignments", response_model=list[AssignmentRead],
            dependencies=[Depends(require_permission(PermissionSlugs.ASSIGN_EXPERT))])
def organizer_assignments(hackathon_id: int, limit: int = Query(20, ge=1, le=100),
                          offset: int = Query(0, ge=0),
                          context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.organizer_assignments(hackathon_id, context.user_id, limit, offset))


@router.get("/expert/assignments", response_model=list[AssignmentRead],
            dependencies=[Depends(require_permission(PermissionSlugs.READ_ASSIGNED_SUBMISSION))])
def assigned(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
             context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.assigned(context.user_id, limit, offset))


@router.get("/expert/assignments/{assignment_id}", response_model=AssignmentRead,
            dependencies=[Depends(require_permission(PermissionSlugs.READ_ASSIGNED_SUBMISSION))])
def get_assignment(assignment_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.read(svc.assignment(assignment_id, context.user_id)))


@router.put("/expert/assignments/{assignment_id}/scores", response_model=AssignmentRead,
            dependencies=[Depends(require_permission(PermissionSlugs.SCORE_SUBMISSION))])
def score(assignment_id: int, data: ScoresWrite,
          context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.score(assignment_id, context.user_id, data))


@router.get("/hackathons/{hackathon_id}/cases/{case_id}/leaderboard", response_model=LeaderboardRead)
def leaderboard(hackathon_id: int, case_id: int, svc=Depends(service)):
    return call(svc, lambda: svc.leaderboard(hackathon_id, case_id))
