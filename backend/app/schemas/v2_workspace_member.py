import uuid

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.enums import MembershipStatus


WorkspaceVisibleRole = Literal["Propietario", "Miembro"]


class WorkspaceMemberRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    display_name: str
    email: str
    role: WorkspaceVisibleRole
    status: MembershipStatus
    joined_at: datetime
    ended_at: datetime | None
