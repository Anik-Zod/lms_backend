import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import CourseSection, LearningContent
from app.models.enrollment import Enrollment
from app.models.enums import ContentStatus
from app.models.progress import CourseProgress, LearningProgress
from app.schemas.progress import LearningProgressUpdate


async def _get_course_id_for_content(db: AsyncSession, content_id: uuid.UUID) -> uuid.UUID:
    stmt = (
        select(CourseSection.course_id)
        .join(LearningContent, LearningContent.section_id == CourseSection.id)
        .where(LearningContent.id == content_id)
    )
    course_id = await db.scalar(stmt)
    if course_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return course_id


async def upsert_progress(
    db: AsyncSession,
    user_id: uuid.UUID,
    content_id: uuid.UUID,
    payload: LearningProgressUpdate,
) -> LearningProgress:
    course_id = await _get_course_id_for_content(db, content_id)

    enrollment = await db.scalar(
        select(Enrollment).where(Enrollment.user_id == user_id, Enrollment.course_id == course_id)
    )
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this course"
        )

    now = datetime.now(timezone.utc)
    progress = await db.get(LearningProgress, {"user_id": user_id, "content_id": content_id})
    was_completed = progress is not None and progress.status == "COMPLETED"

    if progress is None:
        progress = LearningProgress(user_id=user_id, content_id=content_id)
        db.add(progress)

    progress.status = payload.status
    progress.progress_seconds = payload.progress_seconds
    progress.last_position_seconds = payload.last_position_seconds
    progress.completion_percentage = Decimal(str(payload.completion_percentage))
    progress.last_accessed_at = now
    if payload.status == "COMPLETED" and not was_completed:
        progress.completed_at = now

    await db.flush()
    await _recompute_course_progress(db, user_id, course_id, content_id)

    await db.commit()
    await db.refresh(progress)
    return progress


async def _recompute_course_progress(
    db: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID, last_content_id: uuid.UUID
) -> None:
    required_stmt = (
        select(LearningContent.id)
        .join(CourseSection, CourseSection.id == LearningContent.section_id)
        .where(
            CourseSection.course_id == course_id,
            LearningContent.is_required.is_(True),
            LearningContent.status == ContentStatus.PUBLISHED,
            LearningContent.deleted_at.is_(None),
        )
    )
    required_ids = (await db.scalars(required_stmt)).all()
    total_required = len(required_ids)

    completed_count = 0
    if required_ids:
        completed_stmt = select(func.count()).where(
            LearningProgress.user_id == user_id,
            LearningProgress.content_id.in_(required_ids),
            LearningProgress.status == "COMPLETED",
        )
        completed_count = (await db.scalar(completed_stmt)) or 0

    percentage = Decimal("100") if total_required == 0 else (
        Decimal(completed_count) / Decimal(total_required) * Decimal("100")
    ).quantize(Decimal("0.01"))

    course_progress = await db.get(CourseProgress, {"user_id": user_id, "course_id": course_id})
    now = datetime.now(timezone.utc)
    if course_progress is None:
        course_progress = CourseProgress(user_id=user_id, course_id=course_id)
        db.add(course_progress)

    course_progress.completed_content_count = completed_count
    course_progress.total_required_content_count = total_required
    course_progress.completion_percentage = percentage
    course_progress.last_content_id = last_content_id
    course_progress.last_accessed_at = now
    if percentage == Decimal("100") and course_progress.completed_at is None:
        course_progress.completed_at = now
