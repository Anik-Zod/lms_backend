import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin
from app.models.enums import CourseLevel, CourseStatus, CourseVisibility, pg_enum


class Course(UUIDPKMixin, Base):
    __tablename__ = "courses"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)

    language_code: Mapped[str] = mapped_column(String(10), nullable=False)
    level: Mapped[CourseLevel] = mapped_column(
        pg_enum(CourseLevel, "course_level"), nullable=False, server_default=CourseLevel.ALL_LEVELS.value
    )

    thumbnail_media_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    promotional_video_media_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    status: Mapped[CourseStatus] = mapped_column(
        pg_enum(CourseStatus, "course_status"), nullable=False, server_default=CourseStatus.DRAFT.value
    )
    visibility: Mapped[CourseVisibility] = mapped_column(
        pg_enum(CourseVisibility, "course_visibility"),
        nullable=False,
        server_default=CourseVisibility.PUBLIC.value,
    )

    rating_average: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, server_default="0")
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    enrollment_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    published_at: Mapped[datetime | None]

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
    deleted_at: Mapped[datetime | None]

    sections: Mapped[list["CourseSection"]] = relationship(
        back_populates="course", order_by="CourseSection.position"
    )
    instructors: Mapped[list["CourseInstructor"]] = relationship(back_populates="course")

    __table_args__ = (
        UniqueConstraint("slug", name="uq_courses_slug"),
        CheckConstraint("rating_average >= 0 AND rating_average <= 5", name="ck_course_rating"),
        CheckConstraint(
            "rating_count >= 0 AND enrollment_count >= 0", name="ck_course_counts"
        ),
    )


class CourseInstructor(Base):
    __tablename__ = "course_instructors"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )

    role: Mapped[str] = mapped_column(String(30), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    revenue_share_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))

    course: Mapped["Course"] = relationship(back_populates="instructors")

    __table_args__ = (
        CheckConstraint(
            "revenue_share_percent IS NULL OR (revenue_share_percent >= 0 AND revenue_share_percent <= 100)",
            name="ck_revenue_share",
        ),
    )


class CourseRevision(UUIDPKMixin, Base):
    __tablename__ = "course_revisions"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="DRAFT")
    snapshot: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    published_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("course_id", "revision_number", name="uq_course_revision_number"),
    )


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    prerequisite_course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )

    type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="RECOMMENDED")
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class CoursePrerequisiteKnowledge(UUIDPKMixin, Base):
    __tablename__ = "course_prerequisite_knowledge"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
