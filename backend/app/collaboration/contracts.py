from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TripMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    user_id: str
    role: Literal["OWNER", "EDITOR", "VIEWER"]


class ShareInvitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    trip_id: str
    role: Literal["EDITOR", "VIEWER"]
    expires_at: datetime
    revoked_at: datetime | None
    accepted_by: str | None
    accepted_at: datetime | None
    created_at: datetime
