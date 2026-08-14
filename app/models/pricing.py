import uuid
from datetime import datetime

from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    minor_unit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")


class CoursePrice(UUIDPKMixin, Base):
    __tablename__ = "course_prices"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )

    amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    list_price: Mapped[float | None] = mapped_column(Numeric(19, 4))

    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")

    effective_from: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    effective_to: Mapped[datetime | None]

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_course_price_amount"),
    )
