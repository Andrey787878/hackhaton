from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.hackathon_schemas import CriterionRead
from app.submission_schemas import SubmissionRead


class AssignmentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: int = Field(gt=0)
    case_id: int = Field(gt=0)
    expert_id: int = Field(gt=0)


class ScoreWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion_id: int = Field(gt=0)
    value: int = Field(ge=0, le=1000, strict=True)


class ScoresWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scores: list[ScoreWrite] = Field(max_length=30)

    @model_validator(mode="after")
    def distinct_criteria(self):
        ids = [score.criterion_id for score in self.scores]
        if len(ids) != len(set(ids)):
            raise ValueError("Один критерий нельзя оценить дважды.")
        return self


class AssignmentRead(BaseModel):
    id: int
    expert_id: int
    assigned_at: datetime
    submission: SubmissionRead
    criteria: list[CriterionRead]
    scores: list[ScoreWrite]
    complete: bool
    total: Decimal | None


class LeaderboardEntry(BaseModel):
    rank: int
    team_id: int
    team_name: str
    case_id: int
    total: Decimal
    expert_count: int


class LeaderboardRead(BaseModel):
    hackathon_id: int
    case_id: int
    entries: list[LeaderboardEntry]
