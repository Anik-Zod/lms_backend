import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignments import AssignmentSubmission
from app.models.content import CourseSection, LearningContent
from app.models.courses import Course, CourseInstructor
from app.models.enrollment import Enrollment
from app.models.enums import CourseStatus
from app.models.identity import User
from app.models.instructor import InstructorProfile
from app.models.pricing import CoursePrice
from app.models.progress import CourseProgress
from app.models.revenue import Payout, RevenueAllocation
from app.schemas.course import (
    CourseInstructorAdd,
    CourseInstructorOut,
    CoursePriceUpdate,
    CourseStudentOut,
)
from app.schemas.teaching import (
    CourseEarningsOut,
    EarningsOut,
    InstructorProfileUpdate,
    TeachingOverviewOut,
)
from app.services import course_service
from app.services.commerce_service import DEFAULT_CURRENCY

OWNER_ROLE = "OWNER"


async def list_courses(db: AsyncSession, user_id: uuid.UUID, limit: int, offset: int):
    stmt = (
        select(Course)
        .where(Course.id.in_(course_service.managed_course_ids(user_id)))
        .order_by(Course.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return await course_service.with_catalog_fields(db, list((await db.scalars(stmt)).all()))


async def _total_earned(db: AsyncSession, user_id: uuid.UUID) -> Decimal:
    total = await db.scalar(
        select(func.coalesce(func.sum(RevenueAllocation.amount), 0)).where(
            RevenueAllocation.instructor_user_id == user_id,
            RevenueAllocation.currency_code == DEFAULT_CURRENCY,
        )
    )
    return Decimal(total)


async def get_overview(db: AsyncSession, user_id: uuid.UUID) -> TeachingOverviewOut:
    managed = course_service.managed_course_ids(user_id)

    course_count, published_count = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(Course.status == CourseStatus.PUBLISHED),
            ).where(Course.id.in_(managed))
        )
    ).one()
    enrollment_count, student_count = (
        await db.execute(
            select(func.count(), func.count(Enrollment.user_id.distinct())).where(
                Enrollment.course_id.in_(managed)
            )
        )
    ).one()
    pending_submissions = await db.scalar(
        select(func.count())
        .select_from(AssignmentSubmission)
        .join(LearningContent, LearningContent.id == AssignmentSubmission.assignment_content_id)
        .join(CourseSection, CourseSection.id == LearningContent.section_id)
        .where(CourseSection.course_id.in_(managed), AssignmentSubmission.status == "SUBMITTED")
    )

    return TeachingOverviewOut(
        course_count=course_count,
        published_course_count=published_count,
        student_count=student_count,
        enrollment_count=enrollment_count,
        pending_submission_count=pending_submissions,
        total_earned=float(await _total_earned(db, user_id)),
        currency_code=DEFAULT_CURRENCY,
    )


async def get_earnings(db: AsyncSession, user_id: uuid.UUID) -> EarningsOut:
    """Earnings are the instructor's share of each sale, after the platform commission."""
    per_course_stmt = (
        select(
            Course.id,
            Course.title,
            func.count(RevenueAllocation.id),
            func.sum(RevenueAllocation.amount),
        )
        .join(Course, Course.id == RevenueAllocation.course_id)
        .where(
            RevenueAllocation.instructor_user_id == user_id,
            RevenueAllocation.currency_code == DEFAULT_CURRENCY,
        )
        .group_by(Course.id, Course.title)
        .order_by(func.sum(RevenueAllocation.amount).desc())
    )
    courses = [
        CourseEarningsOut(course_id=course_id, title=title, sales_count=sales, amount=float(amount))
        for course_id, title, sales, amount in (await db.execute(per_course_stmt)).all()
    ]

    total_earned = await _total_earned(db, user_id)
    total_paid_out = Decimal(
        await db.scalar(
            select(func.coalesce(func.sum(Payout.amount), 0)).where(
                Payout.instructor_user_id == user_id,
                Payout.currency_code == DEFAULT_CURRENCY,
                Payout.processed_at.is_not(None),
            )
        )
    )
    return EarningsOut(
        currency_code=DEFAULT_CURRENCY,
        total_earned=float(total_earned),
        total_paid_out=float(total_paid_out),
        balance=float(total_earned - total_paid_out),
        courses=courses,
    )


async def get_profile(db: AsyncSession, user_id: uuid.UUID) -> InstructorProfile:
    profile = await db.get(InstructorProfile, user_id)
    if profile is None:
        profile = InstructorProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


async def update_profile(
    db: AsyncSession, user_id: uuid.UUID, data: InstructorProfileUpdate
) -> InstructorProfile:
    profile = await get_profile(db, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile


async def set_price(db: AsyncSession, course: Course, data: CoursePriceUpdate) -> CoursePrice:
    """Retires the current price and starts a new one, so past prices stay on record."""
    now = datetime.now(timezone.utc)
    current = await course_service.get_active_price(db, course.id)
    if current is not None:
        current.status = "INACTIVE"
        current.effective_to = now

    price = CoursePrice(
        course_id=course.id,
        currency_code=DEFAULT_CURRENCY,
        amount=data.amount,
        list_price=data.list_price,
        effective_from=now,
    )
    db.add(price)
    await db.commit()
    await db.refresh(price)
    return price


async def list_students(
    db: AsyncSession, course_id: uuid.UUID, limit: int, offset: int
) -> list[CourseStudentOut]:
    stmt = (
        select(Enrollment, User.display_name, CourseProgress)
        .join(User, User.id == Enrollment.user_id)
        .outerjoin(
            CourseProgress,
            (CourseProgress.user_id == Enrollment.user_id)
            & (CourseProgress.course_id == Enrollment.course_id),
        )
        .where(Enrollment.course_id == course_id)
        .order_by(Enrollment.enrolled_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        CourseStudentOut(
            user_id=enrollment.user_id,
            display_name=display_name,
            status=enrollment.status,
            source=enrollment.source,
            enrolled_at=enrollment.enrolled_at,
            completion_percentage=float(progress.completion_percentage) if progress else 0,
            completed_at=progress.completed_at if progress else None,
            last_accessed_at=progress.last_accessed_at if progress else None,
        )
        for enrollment, display_name, progress in (await db.execute(stmt)).all()
    ]


async def list_instructors(db: AsyncSession, course: Course) -> list[CourseInstructorOut]:
    owner = await db.get(User, course.owner_user_id)
    result = [
        CourseInstructorOut(user_id=owner.id, display_name=owner.display_name, role=OWNER_ROLE)
    ]
    stmt = (
        select(CourseInstructor, User.display_name)
        .join(User, User.id == CourseInstructor.user_id)
        .where(CourseInstructor.course_id == course.id)
        .order_by(CourseInstructor.display_order, User.display_name)
    )
    for instructor, display_name in (await db.execute(stmt)).all():
        result.append(
            CourseInstructorOut(
                user_id=instructor.user_id, display_name=display_name, role=instructor.role
            )
        )
    return result


async def add_instructor(db: AsyncSession, course: Course, data: CourseInstructorAdd) -> None:
    user = await db.scalar(
        select(User).where(User.email == data.email, User.deleted_at.is_(None))
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No account with that email"
        )
    if user.id == course.owner_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That user already owns this course"
        )

    instructor = await db.get(CourseInstructor, {"course_id": course.id, "user_id": user.id})
    if instructor is None:
        instructor = CourseInstructor(course_id=course.id, user_id=user.id)
        db.add(instructor)
    instructor.role = data.role
    await db.commit()


async def remove_instructor(db: AsyncSession, course: Course, user_id: uuid.UUID) -> None:
    instructor = await db.get(CourseInstructor, {"course_id": course.id, "user_id": user_id})
    if instructor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That user is not an instructor here"
        )
    await db.delete(instructor)
    await db.commit()
