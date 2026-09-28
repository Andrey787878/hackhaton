from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.db import get_db
from app.dependencies import CurrentUserContext, get_current_user_context, require_permission
from app.submission_schemas import SubmissionRead
from app.submission_service import SubmissionError, SubmissionService
from app.storage import get_storage
from app.team_service import get_clock

router = APIRouter(tags=["submissions"])


def service(db: Session = Depends(get_db), clock=Depends(get_clock), storage=Depends(get_storage)):
    return SubmissionService(db, clock, storage)


def call(svc, action):
    try:
        return action()
    except SubmissionError as exc:
        svc.db.rollback()
        raise HTTPException(exc.status, exc.detail) from exc
    except IntegrityError as exc:
        svc.db.rollback()
        raise HTTPException(409, "Конфликт данных сдачи.") from exc
    except SQLAlchemyError as exc:
        svc.db.rollback()
        raise HTTPException(503, "Временная ошибка базы данных.") from exc
    except (BotoCoreError, ClientError, OSError) as exc:
        svc.db.rollback()
        raise HTTPException(503, "Объектное хранилище недоступно.") from exc


@router.post("/teams/{team_id}/submissions", response_model=SubmissionRead, status_code=201,
             dependencies=[Depends(require_permission("submit-solution"))])
def submit(team_id: int, case_id: int = Form(..., ge=1), url: str | None = Form(None),
           archive: UploadFile | None = File(None),
           context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.create(team_id, case_id, context.user_id, url, archive))


@router.get("/teams/{team_id}/submissions", response_model=list[SubmissionRead])
def list_submissions(team_id: int, case_id: int | None = Query(None, ge=1),
                     limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                     context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.list(team_id, context.user_id, case_id, limit, offset))


@router.get("/submissions/{submission_id}", response_model=SubmissionRead)
def get_submission(submission_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    return call(svc, lambda: svc.result(svc.get(submission_id, context.user_id)))


@router.get("/submissions/{submission_id}/archive")
def get_archive(submission_id: int, context: CurrentUserContext = Depends(get_current_user_context), svc=Depends(service)):
    body, content_type, filename = call(svc, lambda: svc.download(submission_id, context.user_id))
    def chunks():
        try:
            for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                if chunk:
                    yield chunk
        finally:
            body.close()
    return StreamingResponse(chunks(), media_type=content_type,
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                                      "Cache-Control": "no-store"})
