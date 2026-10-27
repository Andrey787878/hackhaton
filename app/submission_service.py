import gzip
import hashlib
import logging
import uuid
import zipfile
from collections.abc import Callable
from datetime import datetime

from fastapi import UploadFile
from pydantic import HttpUrl, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Case, ExpertAssignment, Hackathon, Role, StoredObject, Submission, Team, TeamMember, UserRole
from app.notification_service import record

MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
log = logging.getLogger(__name__)


class SubmissionError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail


class SubmissionService:
    def __init__(self, db: Session, clock: Callable[[], datetime], storage):
        self.db, self.clock, self.storage = db, clock, storage

    def team(self, tid: int) -> Team:
        team = self.db.get(Team, tid)
        if team is None:
            raise SubmissionError(404, "Команда не найдена.")
        return team

    def access(self, team: Team, uid: int) -> None:
        member = self.db.scalar(select(TeamMember.id).where(TeamMember.team_id == team.id,
                                                             TeamMember.user_id == uid))
        if member is not None:
            return
        owner = self.db.scalar(select(Hackathon.organizer_id).where(Hackathon.id == team.hackathon_id))
        role = self.db.scalar(select(UserRole.id).join(Role, Role.id == UserRole.role_id).where(
            UserRole.user_id == uid, Role.slug.in_(("organizer", "admin")),
            Role.deleted_at.is_(None), UserRole.deleted_at.is_(None)))
        if owner == uid and role is not None:
            return
        raise SubmissionError(403, "Решения доступны только команде и организатору хакатона.")

    def check_submit(self, tid: int, case_id: int, uid: int, *, lock: bool) -> Team:
        hid = self.db.scalar(select(Team.hackathon_id).where(Team.id == tid))
        if hid is None:
            raise SubmissionError(404, "Команда не найдена.")
        query = select(Hackathon).where(Hackathon.id == hid)
        if lock:
            query = query.with_for_update()
        hackathon = self.db.scalar(query)
        team = self.team(tid)
        if team.captain_id != uid:
            raise SubmissionError(403, "Сдавать решение может только капитан команды.")
        if not hackathon.is_published or self.clock() < hackathon.starts_at:
            raise SubmissionError(409, "Приём решений ещё не начался.")
        if self.clock() >= hackathon.deadline_at:
            raise SubmissionError(409, "Дедлайн сдачи прошёл.")
        if self.db.scalar(select(Case.id).where(Case.id == case_id, Case.hackathon_id == hid)) is None:
            raise SubmissionError(404, "Кейс этого хакатона не найден.")
        return team

    @staticmethod
    def validate_url(raw: str | None) -> str | None:
        if raw is None or not raw.strip():
            return None
        if len(raw) > 2048:
            raise SubmissionError(422, "URL слишком длинный.")
        try:
            parsed = TypeAdapter(HttpUrl).validate_python(raw.strip())
        except ValidationError as exc:
            raise SubmissionError(422, "Ожидается корректный HTTPS URL.") from exc
        if parsed.scheme != "https":
            raise SubmissionError(422, "Ожидается HTTPS URL.")
        return str(parsed)

    @staticmethod
    def validate_archive(file: UploadFile):
        name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        if not name or len(name) > 255:
            raise SubmissionError(422, "Имя архива отсутствует или слишком длинное.")
        file.file.seek(0)
        digest = hashlib.sha256()
        size = 0
        while chunk := file.file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > MAX_ARCHIVE_BYTES:
                raise SubmissionError(413, "Архив больше 20 МиБ.")
            digest.update(chunk)
        if size == 0:
            raise SubmissionError(422, "Архив пустой.")
        lowered = name.lower()
        if lowered.endswith(".zip"):
            content_type = "application/zip"
            file.file.seek(0)
            if not zipfile.is_zipfile(file.file):
                raise SubmissionError(422, "Файл не является ZIP-архивом.")
        elif lowered.endswith(".tar.gz"):
            content_type = "application/gzip"
            try:
                file.file.seek(0)
                with gzip.GzipFile(fileobj=file.file, mode="rb") as archive:
                    prefix = archive.read(512)
                if prefix[257:262] != b"ustar":
                    raise ValueError("Invalid tar header")
            except (OSError, EOFError, ValueError) as exc:
                raise SubmissionError(422, "Файл не является TAR.GZ-архивом.") from exc
        else:
            raise SubmissionError(422, "Разрешены только .zip и .tar.gz.")
        file.file.seek(0)
        return name, content_type, size, digest.hexdigest()

    @staticmethod
    def result(submission: Submission):
        stored = submission.stored_object
        return dict(id=submission.id, team_id=submission.team_id, case_id=submission.case_id,
                    submitted_by=submission.submitted_by, submitted_at=submission.submitted_at,
                    url=submission.url, archive=None if stored is None else
                    dict(filename=stored.original_name, size_bytes=stored.size_bytes, sha256=stored.sha256))

    def create(self, tid: int, case_id: int, uid: int, raw_url: str | None, file: UploadFile | None):
        url = self.validate_url(raw_url)
        if url is None and file is None:
            raise SubmissionError(422, "Укажите URL и/или архив.")
        metadata = self.validate_archive(file) if file is not None else None
        self.check_submit(tid, case_id, uid, lock=False)
        # Release DB transaction while the untrusted upload is sent to object storage.
        self.db.rollback()

        key = None
        uploaded = False
        try:
            if metadata is not None:
                name, content_type, size, digest = metadata
                key = f"submissions/{tid}/{uuid.uuid4().hex}"
                self.storage.put(key, file.file, size, content_type)
                uploaded = True

            team = self.check_submit(tid, case_id, uid, lock=True)
            now = self.clock()
            # A clock change at the boundary must not permit a late commit.
            hackathon = self.db.get(Hackathon, team.hackathon_id)
            if now >= hackathon.deadline_at:
                raise SubmissionError(409, "Дедлайн сдачи прошёл.")
            stored = None
            if metadata is not None:
                stored = StoredObject(object_key=key, original_name=name, content_type=content_type,
                                      size_bytes=size, sha256=digest)
                self.db.add(stored)
                self.db.flush()
            submission = Submission(team_id=tid, case_id=case_id, submitted_by=uid,
                                    submitted_at=now, url=url, stored_object_id=stored.id if stored else None)
            self.db.add(submission)
            self.db.flush()
            record(self.db, user_id=hackathon.organizer_id, actor_id=uid,
                   kind="submission_created", resource_type="submission",
                   resource_id=submission.id, at=now)
            self.db.commit()
            return self.result(submission)
        except Exception:
            self.db.rollback()
            if uploaded and key is not None:
                try:
                    self.storage.delete(key)
                except Exception:
                    log.exception("Failed to remove orphaned object %s", key)
            raise

    def list(self, tid: int, uid: int, case_id: int | None, limit: int, offset: int):
        team = self.team(tid)
        self.access(team, uid)
        query = select(Submission).where(Submission.team_id == tid)
        if case_id is not None:
            query = query.where(Submission.case_id == case_id)
        return [self.result(item) for item in self.db.scalars(
            query.order_by(Submission.submitted_at.desc(), Submission.id.desc()).limit(limit).offset(offset))]

    def get(self, submission_id: int, uid: int):
        item = self.db.get(Submission, submission_id)
        if item is None:
            raise SubmissionError(404, "Сдача не найдена.")
        try:
            self.access(self.team(item.team_id), uid)
        except SubmissionError as exc:
            if exc.status != 403 or self.db.scalar(select(ExpertAssignment.id)
                    .join(UserRole, UserRole.user_id == ExpertAssignment.expert_id)
                    .join(Role, Role.id == UserRole.role_id)
                    .where(ExpertAssignment.submission_id == submission_id,
                           ExpertAssignment.expert_id == uid, Role.slug == "expert",
                           Role.deleted_at.is_(None), UserRole.deleted_at.is_(None))) is None:
                raise
        return item

    def download(self, submission_id: int, uid: int):
        item = self.get(submission_id, uid)
        if item.stored_object is None:
            raise SubmissionError(404, "Архив у этой сдачи отсутствует.")
        stored = item.stored_object
        body = self.storage.get(stored.object_key)
        return body, stored.content_type, stored.original_name
