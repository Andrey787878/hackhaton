from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArchiveRead(BaseModel):
    filename: str
    size_bytes: int
    sha256: str


class SubmissionRead(BaseModel):
    id: int
    team_id: int
    case_id: int
    submitted_by: int
    submitted_at: datetime
    url: str | None
    archive: ArchiveRead | None
