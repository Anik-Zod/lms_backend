import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import CourseSection, LearningContent
from app.models.courses import Course, CourseInstructor
from app.models.identity import User
from app.models.pricing import CoursePrice
from app.schemas.course import CourseOut
from app.services import media_service
from app.services.commerce_service import DEFAULT_CURRENCY


def managed_course_ids(user_id: uuid.UUID):
    """Subquery of the courses a user teaches: owned, or listed as co-instructor/TA."""
    return select(Course.id).where(
        Course.deleted_at.is_(None),
        or_(
            Course.owner_user_id == user_id,
            Course.id.in_(
                select(CourseInstructor.course_id).where(CourseInstructor.user_id == user_id)
            ),
        ),
    )


async def get_active_price(db: AsyncSession, course_id: uuid.UUID) -> CoursePrice | None:
    return await db.scalar(
        select(CoursePrice).where(
            CoursePrice.course_id == course_id,
            CoursePrice.currency_code == DEFAULT_CURRENCY,
            CoursePrice.status == "ACTIVE",
        )
    )


async def with_catalog_fields(db: AsyncSession, courses: list[Course]) -> list[CourseOut]:
    """Attach the active price, the owner's display name and the thumbnail URL to each course."""
    if not courses:
        return []

    price_stmt = select(CoursePrice).where(
        CoursePrice.course_id.in_([c.id for c in courses]),
        CoursePrice.currency_code == DEFAULT_CURRENCY,
        CoursePrice.status == "ACTIVE",
    )
    prices = {p.course_id: p for p in (await db.scalars(price_stmt)).all()}

    owner_stmt = select(User.id, User.display_name).where(
        User.id.in_({c.owner_user_id for c in courses})
    )
    owner_names = {row.id: row.display_name for row in (await db.execute(owner_stmt)).all()}

    result = []
    for course in courses:
        out = CourseOut.model_validate(course)
        price = prices.get(course.id)
        if price is not None:
            out.price = float(price.amount)
            out.list_price = float(price.list_price) if price.list_price is not None else None
            out.currency_code = price.currency_code
        out.instructor_name = owner_names.get(course.owner_user_id)
        if course.thumbnail_media_id is not None:
            out.thumbnail_url = media_service.signed_url(course.thumbnail_media_id)
        result.append(out)
    return result


async def next_position(db: AsyncSession, model, parent_column, parent_id: uuid.UUID) -> int:
    current = await db.scalar(select(func.max(model.position)).where(parent_column == parent_id))
    return (current or 0) + 1


async def reorder(db: AsyncSession, rows: list, ids: list[uuid.UUID]) -> None:
    """Renumber rows 1..n in the order of ids. Positions are unique per parent, so
    rows are first parked above the current range to avoid colliding mid-update."""
    by_id = {row.id: row for row in rows}
    if len(ids) != len(by_id) or set(ids) != set(by_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ids must list every item exactly once",
        )

    parked = max(row.position for row in rows)
    for offset, item_id in enumerate(ids, start=1):
        by_id[item_id].position = parked + offset
    await db.flush()

    for position, item_id in enumerate(ids, start=1):
        by_id[item_id].position = position
    await db.commit()


async def hard_delete(db: AsyncSession, model, row_id: uuid.UUID, in_use_detail: str) -> None:
    """Deletes through the database so its cascades apply. Rows that students have
    already worked on are protected by RESTRICT foreign keys; that surfaces as a 409."""
    try:
        await db.execute(delete(model).where(model.id == row_id))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=in_use_detail)


async def get_section(db: AsyncSession, course_id: uuid.UUID, section_id: uuid.UUID) -> CourseSection:
    section = await db.get(CourseSection, section_id)
    if section is None or section.course_id != course_id or section.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return section


async def get_content(
    db: AsyncSession, course_id: uuid.UUID, content_id: uuid.UUID
) -> LearningContent:
    stmt = (
        select(LearningContent)
        .join(CourseSection, CourseSection.id == LearningContent.section_id)
        .where(
            LearningContent.id == content_id,
            LearningContent.deleted_at.is_(None),
            CourseSection.course_id == course_id,
        )
    )
    content = await db.scalar(stmt)
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return content
