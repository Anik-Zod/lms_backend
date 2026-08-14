import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class ModerationCase(UUIDPKMixin, Base):
    __tablename__ = "moderation_cases"

    case_type: Mapped[str] = mapped_column(String(40), nullable=False)

    reported_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    target_course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT")
    )
    target_review_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reviews.id", ondelete="RESTRICT")
    )
    target_content_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="RESTRICT")
    )

    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="OPEN")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="NORMAL")

    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    reason: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    resolved_at: Mapped[datetime | None]
