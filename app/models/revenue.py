import uuid
from datetime import datetime

from sqlalchemy import CHAR, ForeignKey, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class RevenueTransaction(UUIDPKMixin, Base):
    __tablename__ = "revenue_transactions"

    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT")
    )
    refund_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("refunds.id", ondelete="RESTRICT")
    )

    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )

    gross_amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    tax_amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    processing_fee: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    platform_fee: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    net_amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")

    occurred_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class RevenueAllocation(UUIDPKMixin, Base):
    __tablename__ = "revenue_allocations"

    revenue_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("revenue_transactions.id", ondelete="RESTRICT"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    instructor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    allocation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    percentage: Mapped[float | None] = mapped_column(Numeric(7, 4))
    amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)

    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class PayoutAccount(UUIDPKMixin, Base):
    __tablename__ = "payout_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_account_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="PENDING")

    country_code: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class Payout(UUIDPKMixin, Base):
    __tablename__ = "payouts"

    instructor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )

    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="PENDING")
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_payout_id: Mapped[str | None] = mapped_column(String(255))

    requested_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    processed_at: Mapped[datetime | None]
    failed_at: Mapped[datetime | None]


class InstructorLedgerEntry(UUIDPKMixin, Base):
    __tablename__ = "instructor_ledger_entries"

    instructor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    revenue_allocation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("revenue_allocations.id", ondelete="RESTRICT")
    )
    payout_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payouts.id", ondelete="SET NULL")
    )

    entry_type: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )

    available_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class PayoutItem(Base):
    __tablename__ = "payout_items"

    payout_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payouts.id", ondelete="CASCADE"), primary_key=True
    )
    ledger_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("instructor_ledger_entries.id", ondelete="RESTRICT"), primary_key=True
    )

    amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
