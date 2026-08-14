import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.commerce import Cart, CartItem, Order, OrderItem, Payment
from app.models.courses import Course
from app.models.enums import CourseStatus, EnrollmentSource, OrderStatus, PaymentStatus
from app.models.pricing import CoursePrice
from app.models.revenue import InstructorLedgerEntry, RevenueAllocation, RevenueTransaction
from app.services.enrollment_service import create_enrollment

DEFAULT_CURRENCY = "USD"
PLATFORM_COMMISSION_PERCENT = Decimal("30.00")


async def get_or_create_cart(db: AsyncSession, user_id: uuid.UUID) -> Cart:
    cart = await db.scalar(
        select(Cart)
        .where(Cart.user_id == user_id, Cart.status == "ACTIVE")
        .options(selectinload(Cart.items))
    )
    if cart is None:
        cart = Cart(user_id=user_id, currency_code=DEFAULT_CURRENCY)
        db.add(cart)
        await db.flush()
        await db.refresh(cart, attribute_names=["items"])
    return cart


async def add_to_cart(db: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID) -> Cart:
    course = await db.get(Course, course_id)
    if course is None or course.status != CourseStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    cart = await get_or_create_cart(db, user_id)
    existing = await db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.course_id == course_id)
    )
    if existing is None:
        db.add(CartItem(cart_id=cart.id, course_id=course_id))
        await db.commit()
        await db.refresh(cart, attribute_names=["items"])
    return cart


async def remove_from_cart(db: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID) -> Cart:
    cart = await get_or_create_cart(db, user_id)
    item = await db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.course_id == course_id)
    )
    if item is not None:
        await db.delete(item)
        await db.commit()
        await db.refresh(cart, attribute_names=["items"])
    return cart


async def checkout(db: AsyncSession, user_id: uuid.UUID, idempotency_key: str) -> Order:
    existing_order = await db.scalar(
        select(Order)
        .where(Order.user_id == user_id, Order.idempotency_key == idempotency_key)
        .options(selectinload(Order.items))
    )
    if existing_order is not None:
        return existing_order

    cart = await get_or_create_cart(db, user_id)
    if not cart.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    order_items: list[OrderItem] = []
    subtotal = Decimal("0")

    for cart_item in cart.items:
        course = await db.get(Course, cart_item.course_id)
        if course is None or course.status != CourseStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Course {cart_item.course_id} is no longer available",
            )
        price = await db.scalar(
            select(CoursePrice).where(
                CoursePrice.course_id == course.id,
                CoursePrice.currency_code == cart.currency_code,
                CoursePrice.status == "ACTIVE",
            )
        )
        unit_price = Decimal(str(price.amount)) if price is not None else Decimal("0")

        order_items.append(
            OrderItem(
                course_id=course.id,
                seller_user_id=course.owner_user_id,
                unit_price=unit_price,
                discount_amount=Decimal("0"),
                tax_amount=Decimal("0"),
                final_amount=unit_price,
                currency_code=cart.currency_code,
            )
        )
        subtotal += unit_price

    order = Order(
        user_id=user_id,
        order_number=f"ORD-{secrets.token_hex(6).upper()}",
        currency_code=cart.currency_code,
        subtotal=subtotal,
        discount_total=Decimal("0"),
        tax_total=Decimal("0"),
        grand_total=subtotal,
        status=OrderStatus.PENDING,
        idempotency_key=idempotency_key,
    )
    order.items = order_items
    db.add(order)

    for cart_item in list(cart.items):
        await db.delete(cart_item)

    await db.commit()
    await db.refresh(order, attribute_names=["items"])
    return order


async def capture_payment(
    db: AsyncSession,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    provider: str,
    provider_payment_id: str,
) -> Payment:
    order = await db.get(Order, order_id, options=[selectinload(Order.items)])
    if order is None or order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Order is already {order.status.value}"
        )

    now = datetime.now(timezone.utc)

    payment = Payment(
        order_id=order.id,
        provider=provider,
        provider_payment_id=provider_payment_id,
        amount=order.grand_total,
        currency_code=order.currency_code,
        status=PaymentStatus.CAPTURED,
        captured_at=now,
    )
    db.add(payment)
    order.status = OrderStatus.PAID

    revenue_transaction = RevenueTransaction(
        order_id=order.id,
        transaction_type="SALE",
        currency_code=order.currency_code,
        gross_amount=order.grand_total,
        tax_amount=order.tax_total,
        processing_fee=Decimal("0"),
        platform_fee=Decimal("0"),
        net_amount=order.grand_total,
    )
    db.add(revenue_transaction)
    await db.flush()

    total_platform_fee = Decimal("0")
    for item in order.items:
        item_amount = Decimal(str(item.final_amount))
        platform_fee = (item_amount * PLATFORM_COMMISSION_PERCENT / Decimal("100")).quantize(
            Decimal("0.0001")
        )
        instructor_net = item_amount - platform_fee
        total_platform_fee += platform_fee

        allocation = RevenueAllocation(
            revenue_transaction_id=revenue_transaction.id,
            course_id=item.course_id,
            instructor_user_id=item.seller_user_id,
            allocation_type="INSTRUCTOR_SHARE",
            percentage=Decimal("100") - PLATFORM_COMMISSION_PERCENT,
            amount=instructor_net,
            currency_code=order.currency_code,
        )
        db.add(allocation)
        await db.flush()

        db.add(
            InstructorLedgerEntry(
                instructor_user_id=item.seller_user_id,
                revenue_allocation_id=allocation.id,
                entry_type="EARNING",
                amount=instructor_net,
                currency_code=order.currency_code,
                available_at=now,
            )
        )

        await create_enrollment(
            db, user_id, item.course_id, EnrollmentSource.PURCHASE, order_item_id=item.id
        )

    revenue_transaction.platform_fee = total_platform_fee
    revenue_transaction.net_amount = order.grand_total - total_platform_fee

    await db.commit()
    await db.refresh(payment)
    return payment
