import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContentStatus, ContentType, CourseLevel, CourseStatus, CourseVisibility


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subtitle: str | None = Field(default=None, max_length=500)
    description: str | None = None
    language_code: str = Field(max_length=10)
    level: CourseLevel = CourseLevel.ALL_LEVELS
    slug: str = Field(min_length=1, max_length=255)


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    subtitle: str | None = Field(default=None, max_length=500)
    description: str | None = None
    language_code: str | None = Field(default=None, max_length=10)
    level: CourseLevel | None = None
    visibility: CourseVisibility | None = None


class CourseStatusUpdate(BaseModel):
    status: CourseStatus


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    owner_user_id: uuid.UUID
    slug: str
    title: str
    subtitle: str | None
    description: str | None
    language_code: str
    level: CourseLevel
    status: CourseStatus
    visibility: CourseVisibility
    rating_average: float
    rating_count: int
    enrollment_count: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CourseSectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    position: int = Field(gt=0)


class CourseSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    description: str | None
    position: int


class LearningContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content_type: ContentType
    position: int = Field(gt=0)
    is_preview: bool = False
    is_required: bool = True
    estimated_duration_seconds: int | None = Field(default=None, ge=0)


class LearningContentStatusUpdate(BaseModel):
    status: ContentStatus


class LearningContentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    section_id: uuid.UUID
    title: str
    content_type: ContentType
    position: int
    is_preview: bool
    is_required: bool
    status: ContentStatus
    estimated_duration_seconds: int | None
