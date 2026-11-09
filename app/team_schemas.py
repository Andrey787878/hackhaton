from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class TeamWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class JoinTeam(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class MemberRead(BaseModel):
    user_id: int
    username: str
    display_name: str | None
    joined_at: datetime


class TeamRead(BaseModel):
    id: int
    hackathon_id: int
    captain_id: int
    name: str
    created_at: datetime
    members: list[MemberRead]


class InviteRead(BaseModel):
    team_id: int
    active: bool
    created_at: datetime | None
    expires_at: datetime


class InviteCreated(InviteRead):
    code: str
