import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import EnrollmentSource, EnrollmentStatus


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    source: EnrollmentSource
    status: EnrollmentStatus
    enrolled_at: datetime
    completed_at: datetime | None
