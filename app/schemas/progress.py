import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LearningProgressUpdate(BaseModel):
    status: str = Field(max_length=30)
    progress_seconds: int = Field(default=0, ge=0)
    last_position_seconds: int = Field(default=0, ge=0)
    completion_percentage: float = Field(default=0, ge=0, le=100)


class LearningProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    content_id: uuid.UUID
    status: str
    progress_seconds: int
    completion_percentage: float
    completed_at: datetime | None
    last_position_seconds: int
    last_accessed_at: datetime | None


class CourseProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    course_id: uuid.UUID
    completed_content_count: int
    total_required_content_count: int
    completion_percentage: float
    last_accessed_at: datetime | None
    completed_at: datetime | None
