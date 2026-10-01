import uuid

from pydantic import BaseModel, ConfigDict, Field


class TeachingOverviewOut(BaseModel):
    course_count: int
    published_course_count: int
    student_count: int
    enrollment_count: int
    pending_submission_count: int
    total_earned: float
    currency_code: str


class CourseEarningsOut(BaseModel):
    course_id: uuid.UUID
    title: str
    sales_count: int
    amount: float


class EarningsOut(BaseModel):
    currency_code: str
    total_earned: float
    total_paid_out: float
    balance: float
    courses: list[CourseEarningsOut]


class InstructorProfileUpdate(BaseModel):
    professional_title: str | None = Field(default=None, max_length=255)
    biography: str | None = None
    expertise_summary: str | None = None


class InstructorProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    professional_title: str | None
    biography: str | None
    expertise_summary: str | None
    status: str
    verification_status: str
