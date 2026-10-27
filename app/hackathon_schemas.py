from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]


class CaseWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    description: Description


class HackathonWrite(CaseWrite):
    starts_at: AwareDatetime
    deadline_at: AwareDatetime

    @field_validator("starts_at", "deadline_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def dates(self):
        if self.deadline_at <= self.starts_at:
            raise ValueError("deadline_at должен быть позже starts_at.")
        return self


class CriterionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    description: str = Field(default="", max_length=4000)
    min_score: int = Field(default=0, ge=0, le=999, strict=True)
    max_score: int = Field(default=10, ge=1, le=1000, strict=True)
    weight: Decimal = Field(default=Decimal("1"), gt=0, le=1000, max_digits=10, decimal_places=4)

    @model_validator(mode="after")
    def score_range(self):
        if self.max_score <= self.min_score:
            raise ValueError("max_score должен быть больше min_score.")
        return self


class CriteriaWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criteria: list[CriterionWrite] = Field(min_length=1, max_length=30)


class CriterionRead(CriterionWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int


class CaseRead(CaseWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int
    hackathon_id: int
    criteria: list[CriterionRead]


class HackathonRead(HackathonWrite):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organizer_id: int
    is_published: bool


class ServerTime(BaseModel):
    server_time: datetime


class HackathonStatus(ServerTime):
    hackathon: HackathonRead
    phase: Literal["upcoming", "active", "finished"]
    materials_available: bool
