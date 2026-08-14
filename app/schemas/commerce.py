import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrderStatus, PaymentStatus


class CartItemAdd(BaseModel):
    course_id: uuid.UUID


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    added_at: datetime


class CartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    currency_code: str
    status: str
    items: list[CartItemOut] = []


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    seller_user_id: uuid.UUID
    unit_price: float
    discount_amount: float
    tax_amount: float
    final_amount: float
    currency_code: str


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    currency_code: str
    subtotal: float
    discount_total: float
    tax_total: float
    grand_total: float
    status: OrderStatus
    created_at: datetime
    items: list[OrderItemOut] = []


class CheckoutRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=255)


class PaymentCaptureRequest(BaseModel):
    provider: str = Field(default="mock", max_length=50)
    provider_payment_id: str = Field(min_length=1, max_length=255)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    provider: str
    amount: float
    currency_code: str
    status: PaymentStatus
    captured_at: datetime | None
