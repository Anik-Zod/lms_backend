import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrollment import Enrollment
from app.models.enums import EnrollmentSource
from app.models.progress import CourseProgress


async def create_enrollment(
    db: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    source: EnrollmentSource,
    order_item_id: uuid.UUID | None = None,
) -> Enrollment:
    existing = await db.scalar(
        select(Enrollment).where(Enrollment.user_id == user_id, Enrollment.course_id == course_id)
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already enrolled")

    enrollment = Enrollment(
        user_id=user_id, course_id=course_id, source=source, order_item_id=order_item_id
    )
    db.add(enrollment)

    db.add(CourseProgress(user_id=user_id, course_id=course_id))

    await db.flush()
    return enrollment
