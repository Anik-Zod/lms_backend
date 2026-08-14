import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin
from app.models.enums import OrderStatus, PaymentStatus, pg_enum


class Cart(UUIDPKMixin, Base):
    __tablename__ = "carts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    items: Mapped[list["CartItem"]] = relationship(back_populates="cart", cascade="all, delete-orphan")


class CartItem(UUIDPKMixin, Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )

    added_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="items")
    course: Mapped["Course"] = relationship()

    __table_args__ = (UniqueConstraint("cart_id", "course_id", name="uq_cart_item_course"),)


class Order(UUIDPKMixin, Base):
    __tablename__ = "orders"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    order_number: Mapped[str] = mapped_column(String(50), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )

    subtotal: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    discount_total: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    tax_total: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    grand_total: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)

    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"), nullable=False, server_default=OrderStatus.PENDING.value
    )

    idempotency_key: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")

    __table_args__ = (
        UniqueConstraint("order_number", name="uq_order_number"),
        Index(
            "uq_orders_idempotency",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        CheckConstraint(
            "subtotal >= 0 AND discount_total >= 0 AND tax_total >= 0 AND grand_total >= 0",
            name="ck_order_amounts",
        ),
    )


class OrderItem(UUIDPKMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    seller_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    unit_price: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    tax_amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    final_amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)

    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )

    order: Mapped["Order"] = relationship(back_populates="items")
    course: Mapped["Course"] = relationship()

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_quantity"),
        CheckConstraint(
            "unit_price >= 0 AND discount_amount >= 0 AND tax_amount >= 0 AND final_amount >= 0",
            name="ck_order_item_amounts",
        ),
    )


class Payment(UUIDPKMixin, Base):
    __tablename__ = "payments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False)

    amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )

    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"), nullable=False
    )

    failure_code: Mapped[str | None] = mapped_column(String(100))
    captured_at: Mapped[datetime | None]

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="payments")

    __table_args__ = (
        UniqueConstraint("provider", "provider_payment_id", name="uq_provider_payment"),
        CheckConstraint("amount >= 0", name="ck_payment_amount"),
    )


class Refund(UUIDPKMixin, Base):
    __tablename__ = "refunds"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )

    amount: Mapped[float] = mapped_column(Numeric(19, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(
        CHAR(3), ForeignKey("currencies.code", ondelete="RESTRICT"), nullable=False
    )

    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="PENDING")

    provider_refund_id: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    completed_at: Mapped[datetime | None]

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_refund_amount"),
        UniqueConstraint("provider_refund_id", name="uq_provider_refund"),
    )
