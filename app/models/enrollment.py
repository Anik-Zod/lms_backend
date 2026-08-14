import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin
from app.models.enums import EnrollmentSource, EnrollmentStatus, pg_enum


class Enrollment(UUIDPKMixin, Base):
    __tablename__ = "enrollments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )

    source: Mapped[EnrollmentSource] = mapped_column(
        pg_enum(EnrollmentSource, "enrollment_source"), nullable=False
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        pg_enum(EnrollmentStatus, "enrollment_status"),
        nullable=False,
        server_default=EnrollmentStatus.ACTIVE.value,
    )

    order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("order_items.id", ondelete="SET NULL")
    )
    coupon_redemption_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("coupon_redemptions.id", ondelete="SET NULL")
    )

    enrolled_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    expires_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    suspended_at: Mapped[datetime | None]

    course: Mapped["Course"] = relationship()

    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_user_course"),)
