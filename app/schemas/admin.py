import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RoleOut(BaseModel):
    code: str
    name: str
    description: str | None
    permissions: list[str]


class RoleAssignRequest(BaseModel):
    role_code: str = Field(min_length=1, max_length=100)


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    status: str
    created_at: datetime
    roles: list[str]
