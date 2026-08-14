import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.courses import Course
from app.models.enrollment import Enrollment
from app.models.enums import CourseStatus, EnrollmentSource
from app.models.identity import User
from app.models.pricing import CoursePrice
from app.schemas.enrollment import EnrollmentOut
from app.services.enrollment_service import create_enrollment

router = APIRouter(tags=["enrollments"])


@router.post(
    "/courses/{course_id}/enroll", response_model=EnrollmentOut, status_code=status.HTTP_201_CREATED
)
async def enroll_free(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if course is None or course.status != CourseStatus.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    active_price = await db.scalar(
        select(CoursePrice).where(
            CoursePrice.course_id == course_id,
            CoursePrice.status == "ACTIVE",
            CoursePrice.amount > 0,
        )
    )
    if active_price is not None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="This course requires purchase; use the cart/checkout flow",
        )

    enrollment = await create_enrollment(db, current_user.id, course_id, EnrollmentSource.FREE)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


@router.get("/enrollments/me", response_model=list[EnrollmentOut])
async def list_my_enrollments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Enrollment).where(Enrollment.user_id == current_user.id)
    return (await db.scalars(stmt)).all()
