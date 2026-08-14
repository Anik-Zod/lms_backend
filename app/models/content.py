import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin
from app.models.enums import ContentStatus, ContentType, pg_enum


class CourseSection(UUIDPKMixin, Base):
    __tablename__ = "course_sections"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    position: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
    deleted_at: Mapped[datetime | None]

    course: Mapped["Course"] = relationship(back_populates="sections")
    contents: Mapped[list["LearningContent"]] = relationship(
        back_populates="section", order_by="LearningContent.position"
    )

    __table_args__ = (
        UniqueConstraint("course_id", "position", name="uq_section_position"),
        CheckConstraint("position > 0", name="ck_section_position"),
    )


class LearningContent(UUIDPKMixin, Base):
    __tablename__ = "learning_contents"

    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[ContentType] = mapped_column(
        pg_enum(ContentType, "content_type"), nullable=False
    )

    position: Mapped[int] = mapped_column(Integer, nullable=False)

    is_preview: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    status: Mapped[ContentStatus] = mapped_column(
        pg_enum(ContentStatus, "content_status"),
        nullable=False,
        server_default=ContentStatus.DRAFT.value,
    )

    estimated_duration_seconds: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
    deleted_at: Mapped[datetime | None]

    section: Mapped["CourseSection"] = relationship(back_populates="contents")

    __table_args__ = (
        UniqueConstraint("section_id", "position", name="uq_content_position"),
        CheckConstraint("position > 0", name="ck_content_position"),
        CheckConstraint(
            "estimated_duration_seconds IS NULL OR estimated_duration_seconds >= 0",
            name="ck_duration",
        ),
    )


class VideoContent(Base):
    __tablename__ = "video_contents"

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="CASCADE"), primary_key=True
    )

    media_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    processing_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="PENDING"
    )

    provider: Mapped[str | None] = mapped_column(String(50))
    provider_asset_id: Mapped[str | None] = mapped_column(String(255))

    captions_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0", name="ck_video_duration"
        ),
    )


class ArticleContent(Base):
    __tablename__ = "article_contents"

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="CASCADE"), primary_key=True
    )

    body_format: Mapped[str] = mapped_column(String(20), nullable=False, server_default="markdown")
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "article_content_revisions.id",
            ondelete="SET NULL",
            name="fk_article_current_revision",
            use_alter=True,
        )
    )


class ArticleContentRevision(UUIDPKMixin, Base):
    __tablename__ = "article_content_revisions"

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("article_contents.content_id", ondelete="CASCADE"), nullable=False
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (
        UniqueConstraint("content_id", "version_number", name="uq_article_revision_version"),
    )


class ResourceContent(Base):
    __tablename__ = "resource_contents"

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="CASCADE"), primary_key=True
    )

    media_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    downloadable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class QuizContent(Base):
    __tablename__ = "quiz_contents"

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="CASCADE"), primary_key=True
    )

    time_limit_seconds: Mapped[int | None] = mapped_column(Integer)
    pass_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="70")
    attempt_limit: Mapped[int | None] = mapped_column(Integer)
    randomize_questions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    randomize_options: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class AssignmentContent(Base):
    __tablename__ = "assignment_contents"

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="CASCADE"), primary_key=True
    )

    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    due_days: Mapped[int | None] = mapped_column(Integer)
    max_file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="20971520")
    allow_resubmission: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
