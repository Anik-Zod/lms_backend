import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class CourseProgress(Base):
    __tablename__ = "course_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), primary_key=True
    )

    completed_content_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_required_content_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    completion_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )

    last_content_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="SET NULL")
    )
    last_accessed_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]

    __table_args__ = (
        CheckConstraint(
            "completion_percentage >= 0 AND completion_percentage <= 100",
            name="ck_course_progress_percentage",
        ),
    )


class LearningProgress(Base):
    __tablename__ = "learning_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="RESTRICT"), primary_key=True
    )

    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="NOT_STARTED")

    progress_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completion_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="0"
    )

    completed_at: Mapped[datetime | None]

    last_position_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_accessed_at: Mapped[datetime | None]

    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "completion_percentage >= 0 AND completion_percentage <= 100",
            name="ck_progress_percentage",
        ),
    )


class LearningEvent(UUIDPKMixin, Base):
    __tablename__ = "learning_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="SET NULL")
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_time: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    position_seconds: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)


class CompletionRule(UUIDPKMixin, Base):
    __tablename__ = "completion_rules"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )

    rule_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_content_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="CASCADE")
    )

    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    configuration: Mapped[dict | None] = mapped_column(JSONB)
