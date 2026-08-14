import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class AssignmentSubmission(UUIDPKMixin, Base):
    __tablename__ = "assignment_submissions"

    assignment_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignment_contents.content_id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False
    )

    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    text_submission: Mapped[str | None] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="SUBMITTED")
    submitted_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "assignment_content_id", "user_id", "attempt_number", name="uq_assignment_submission"
        ),
    )


class AssignmentSubmissionFile(UUIDPKMixin, Base):
    __tablename__ = "assignment_submission_files"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=False
    )


class AssignmentGrade(UUIDPKMixin, Base):
    __tablename__ = "assignment_grades"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=False
    )
    grader_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    score: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text)
    graded_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class AssignmentRubric(UUIDPKMixin, Base):
    __tablename__ = "assignment_rubrics"

    assignment_content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignment_contents.content_id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class RubricItem(UUIDPKMixin, Base):
    __tablename__ = "rubric_items"

    rubric_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignment_rubrics.id", ondelete="CASCADE"), nullable=False
    )

    criterion: Mapped[str] = mapped_column(String(255), nullable=False)
    max_points: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
