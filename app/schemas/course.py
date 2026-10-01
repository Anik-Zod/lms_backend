import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.enums import (
    ContentStatus,
    ContentType,
    CourseLevel,
    CourseStatus,
    CourseVisibility,
    EnrollmentSource,
    EnrollmentStatus,
)


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
    thumbnail_media_id: uuid.UUID | None = None


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
    thumbnail_media_id: uuid.UUID | None
    rating_average: float
    rating_count: int
    enrollment_count: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # Catalog fields, filled in by the list/detail endpoints (not Course columns).
    price: float | None = None
    list_price: float | None = None
    currency_code: str | None = None
    instructor_name: str | None = None
    thumbnail_url: str | None = None


class CoursePriceUpdate(BaseModel):
    """amount 0 makes the course free. list_price is the struck-through "was" price."""

    amount: Decimal = Field(ge=0, max_digits=19, decimal_places=4)
    list_price: Decimal | None = Field(default=None, ge=0, max_digits=19, decimal_places=4)

    @model_validator(mode="after")
    def _list_price_not_below_amount(self):
        if self.list_price is not None and self.list_price < self.amount:
            raise ValueError("list_price cannot be lower than amount")
        return self


class CoursePriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_id: uuid.UUID
    currency_code: str
    amount: float
    list_price: float | None
    effective_from: datetime


class CourseInstructorAdd(BaseModel):
    email: EmailStr
    role: Literal["CO_INSTRUCTOR", "TEACHING_ASSISTANT"] = "CO_INSTRUCTOR"


class CourseInstructorOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    role: str


class CourseStudentOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    status: EnrollmentStatus
    source: EnrollmentSource
    enrolled_at: datetime
    completion_percentage: float
    completed_at: datetime | None
    last_accessed_at: datetime | None


class ReorderRequest(BaseModel):
    """Every id of the list being reordered, in the new order."""

    ids: list[uuid.UUID] = Field(min_length=1)


class CourseSectionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    # Omit to append at the end.
    position: int | None = Field(default=None, gt=0)


class CourseSectionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


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
    # Omit to append at the end.
    position: int | None = Field(default=None, gt=0)
    is_preview: bool = False
    is_required: bool = True
    estimated_duration_seconds: int | None = Field(default=None, ge=0)


class LearningContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    is_preview: bool | None = None
    is_required: bool | None = None
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


class CurriculumSectionOut(CourseSectionOut):
    contents: list[LearningContentOut] = []
