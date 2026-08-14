import uuid
from datetime import datetime

from sqlalchemy import CHAR, ForeignKey, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class Coupon(UUIDPKMixin, Base):
    __tablename__ = "coupons"

    code: Mapped[str] = mapped_column(String(50), nullable=False)

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )

    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_value: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    currency_code: Mapped[str | None] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT")
    )

    max_redemptions: Mapped[int | None] = mapped_column(Integer)
    max_redemptions_per_user: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    minimum_order_amount: Mapped[float | None] = mapped_column(Numeric(19, 4))

    starts_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]

    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")

    __table_args__ = (UniqueConstraint("code", name="uq_coupons_code"),)


class CouponCourse(Base):
    __tablename__ = "coupon_courses"

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coupons.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )


class CouponRedemption(UUIDPKMixin, Base):
    __tablename__ = "coupon_redemptions"

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coupons.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )

    discount_amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    __table_args__ = (
        UniqueConstraint("coupon_id", "user_id", "order_id", name="uq_coupon_redemption"),
    )


class Promotion(UUIDPKMixin, Base):
    __tablename__ = "promotions"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="DRAFT")

    starts_at: Mapped[datetime | None]
    ends_at: Mapped[datetime | None]

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class PromotionCourse(Base):
    __tablename__ = "promotion_courses"

    promotion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("promotions.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )

    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_value: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
