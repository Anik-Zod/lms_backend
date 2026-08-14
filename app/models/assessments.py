import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class QuizQuestion(UUIDPKMixin, Base):
    __tablename__ = "quiz_questions"

    quiz_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_contents.content_id", ondelete="CASCADE"), nullable=False
    )

    question_type: Mapped[str] = mapped_column(String(30), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, server_default="1")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "question_versions.id",
            ondelete="SET NULL",
            name="fk_question_current_version",
            use_alter=True,
        )
    )

    __table_args__ = (
        UniqueConstraint("quiz_content_id", "position", name="uq_quiz_question_position"),
    )


class QuestionVersion(UUIDPKMixin, Base):
    __tablename__ = "question_versions"

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    grading_config: Mapped[dict | None] = mapped_column(JSONB)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (
        UniqueConstraint("question_id", "version_number", name="uq_question_version_number"),
    )


class QuestionOption(UUIDPKMixin, Base):
    __tablename__ = "question_options"

    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="CASCADE"), nullable=False
    )

    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class QuizAttempt(UUIDPKMixin, Base):
    __tablename__ = "quiz_attempts"

    quiz_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_contents.content_id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False
    )

    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="IN_PROGRESS")

    started_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    submitted_at: Mapped[datetime | None]

    score: Mapped[float | None] = mapped_column(Numeric(10, 4))
    percentage: Mapped[float | None] = mapped_column(Numeric(5, 2))
    passed: Mapped[bool | None] = mapped_column(Boolean)

    __table_args__ = (
        UniqueConstraint(
            "quiz_content_id", "user_id", "attempt_number", name="uq_quiz_attempt_number"
        ),
    )


class QuizAnswer(UUIDPKMixin, Base):
    __tablename__ = "quiz_answers"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="RESTRICT"), nullable=False
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_versions.id", ondelete="RESTRICT"), nullable=False
    )
    selected_option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_options.id", ondelete="SET NULL")
    )

    answer_text: Mapped[str | None] = mapped_column(Text)
    numeric_answer: Mapped[float | None] = mapped_column(Numeric(19, 4))

    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    points_awarded: Mapped[float | None] = mapped_column(Numeric(10, 4))
    graded_at: Mapped[datetime | None]
