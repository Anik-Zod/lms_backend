import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.course import LearningContentOut

QuestionType = Literal["SINGLE_CHOICE", "TRUE_FALSE", "SHORT_ANSWER"]


class MediaAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID | None
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    created_at: datetime
    # Signed, time-limited path relative to the API host.
    url: str | None = None


class ArticleUpdate(BaseModel):
    body: str = Field(min_length=1)
    body_format: Literal["markdown", "html"] = "markdown"


class ArticleOut(BaseModel):
    body: str
    body_format: str
    version_number: int


class VideoUpdate(BaseModel):
    media_asset_id: uuid.UUID
    duration_seconds: int | None = Field(default=None, ge=0)


class VideoOut(BaseModel):
    media_asset_id: uuid.UUID
    duration_seconds: int | None
    mime_type: str | None
    url: str


class ResourceUpdate(BaseModel):
    media_asset_id: uuid.UUID
    downloadable: bool = True


class ResourceOut(BaseModel):
    media_asset_id: uuid.UUID
    filename: str | None
    mime_type: str | None
    size_bytes: int | None
    downloadable: bool
    url: str


class QuizSettingsUpdate(BaseModel):
    time_limit_seconds: int | None = Field(default=None, gt=0)
    pass_percentage: float = Field(default=70, ge=0, le=100)
    attempt_limit: int | None = Field(default=None, gt=0)
    randomize_questions: bool = False
    randomize_options: bool = False


class QuestionOptionIn(BaseModel):
    option_text: str = Field(min_length=1)
    is_correct: bool = False


class QuestionIn(BaseModel):
    question_type: QuestionType
    question_text: str = Field(min_length=1)
    explanation: str | None = None
    points: float = Field(default=1, gt=0)
    options: list[QuestionOptionIn] = []
    # SHORT_ANSWER only: answers accepted as correct, compared case-insensitively.
    accepted_answers: list[str] = []

    @model_validator(mode="after")
    def _answers_match_type(self):
        if self.question_type == "SHORT_ANSWER":
            if self.options:
                raise ValueError("SHORT_ANSWER questions take accepted_answers, not options")
            if not [a for a in self.accepted_answers if a.strip()]:
                raise ValueError("SHORT_ANSWER questions need at least one accepted answer")
        else:
            if len(self.options) < 2:
                raise ValueError("Choice questions need at least two options")
            if self.question_type == "TRUE_FALSE" and len(self.options) != 2:
                raise ValueError("TRUE_FALSE questions need exactly two options")
            if sum(o.is_correct for o in self.options) != 1:
                raise ValueError("Exactly one option must be marked correct")
        return self


class QuestionOptionOut(BaseModel):
    id: uuid.UUID
    option_text: str
    position: int
    # Hidden from students.
    is_correct: bool | None = None


class QuestionOut(BaseModel):
    id: uuid.UUID
    question_type: str
    position: int
    points: float
    question_text: str
    options: list[QuestionOptionOut] = []
    # Hidden from students.
    explanation: str | None = None
    accepted_answers: list[str] | None = None


class QuizOut(BaseModel):
    time_limit_seconds: int | None
    pass_percentage: float
    attempt_limit: int | None
    randomize_questions: bool
    randomize_options: bool
    questions: list[QuestionOut] = []


class AssignmentUpdate(BaseModel):
    instructions: str = Field(min_length=1)
    due_days: int | None = Field(default=None, gt=0)
    allow_resubmission: bool = True


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instructions: str
    due_days: int | None
    allow_resubmission: bool


class ContentDetailOut(LearningContentOut):
    """A lesson plus its body. Exactly one of the body fields is set once the
    teacher has filled the lesson in; all are null for an empty lesson."""

    article: ArticleOut | None = None
    video: VideoOut | None = None
    resource: ResourceOut | None = None
    quiz: QuizOut | None = None
    assignment: AssignmentOut | None = None


class QuizAnswerIn(BaseModel):
    question_id: uuid.UUID
    selected_option_id: uuid.UUID | None = None
    answer_text: str | None = None


class QuizAttemptSubmit(BaseModel):
    answers: list[QuizAnswerIn]


class QuizAnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: uuid.UUID
    selected_option_id: uuid.UUID | None
    answer_text: str | None
    is_correct: bool | None
    points_awarded: float | None


class QuizAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    attempt_number: int
    status: str
    submitted_at: datetime | None
    score: float | None
    percentage: float | None
    passed: bool | None
    student_name: str | None = None
    answers: list[QuizAnswerOut] = []


class SubmissionCreate(BaseModel):
    text_submission: str | None = None
    external_url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def _not_empty(self):
        if not (self.text_submission and self.text_submission.strip()) and not self.external_url:
            raise ValueError("Provide text_submission or external_url")
        return self


class GradeIn(BaseModel):
    score: float = Field(ge=0, le=100)
    feedback: str | None = None


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float
    feedback: str | None
    grader_user_id: uuid.UUID
    graded_at: datetime


class SubmissionOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    content_id: uuid.UUID
    content_title: str
    user_id: uuid.UUID
    student_name: str
    attempt_number: int
    text_submission: str | None
    external_url: str | None
    status: str
    submitted_at: datetime
    grade: GradeOut | None = None
