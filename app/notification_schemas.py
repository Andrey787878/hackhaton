from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: int
    kind: Literal["hackathon_published", "team_joined", "submission_created",
                  "expert_assigned", "score_completed"]
    title: str
    actor_id: int
    resource_type: Literal["hackathon", "team", "submission", "assignment"]
    resource_id: int
    created_at: datetime
    read_at: datetime | None


class UnreadCount(BaseModel):
    count: int
