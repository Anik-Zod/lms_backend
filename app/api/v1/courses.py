import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_optional, require_course_management
from app.models.content import CourseSection, LearningContent
from app.models.courses import Course
from app.models.enums import ContentStatus, CourseStatus, CourseVisibility
from app.models.identity import User
from app.schemas.course import (
    CourseCreate,
    CourseOut,
    CourseSectionCreate,
    CourseSectionOut,
    CourseStatusUpdate,
    CourseUpdate,
    LearningContentCreate,
    LearningContentOut,
    LearningContentStatusUpdate,
)

router = APIRouter(prefix="/courses", tags=["courses"])


def _assert_viewable(course: Course, current_user: User | None) -> None:
    if course.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    if course.status == CourseStatus.PUBLISHED and course.visibility == CourseVisibility.PUBLIC:
        return
    if current_user is not None and current_user.id == course.owner_user_id:
        return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(select(Course).where(Course.slug == payload.slug))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already in use")

    course = Course(owner_user_id=current_user.id, **payload.model_dump())
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


@router.get("", response_model=list[CourseOut])
async def list_courses(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Course)
        .where(
            Course.status == CourseStatus.PUBLISHED,
            Course.visibility == CourseVisibility.PUBLIC,
            Course.deleted_at.is_(None),
        )
        .order_by(Course.published_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return (await db.scalars(stmt)).all()


@router.get("/{course_id}", response_model=CourseOut)
async def get_course(
    course_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    _assert_viewable(course, current_user)
    return course


@router.patch("/{course_id}", response_model=CourseOut)
async def update_course(
    payload: CourseUpdate,
    course: Course = Depends(require_course_management("course.update")),
    db: AsyncSession = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    await db.commit()
    await db.refresh(course)
    return course


@router.patch("/{course_id}/status", response_model=CourseOut)
async def update_course_status(
    payload: CourseStatusUpdate,
    course: Course = Depends(require_course_management("course.publish")),
    db: AsyncSession = Depends(get_db),
):
    if payload.status == CourseStatus.PUBLISHED and course.published_at is None:
        from datetime import datetime, timezone

        course.published_at = datetime.now(timezone.utc)
    course.status = payload.status
    await db.commit()
    await db.refresh(course)
    return course


@router.post(
    "/{course_id}/sections", response_model=CourseSectionOut, status_code=status.HTTP_201_CREATED
)
async def create_section(
    payload: CourseSectionCreate,
    course: Course = Depends(require_course_management("course.manage_content")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(CourseSection).where(
            CourseSection.course_id == course.id, CourseSection.position == payload.position
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Position already used in this course"
        )

    section = CourseSection(course_id=course.id, **payload.model_dump())
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


@router.get("/{course_id}/sections", response_model=list[CourseSectionOut])
async def list_sections(
    course_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    _assert_viewable(course, current_user)

    stmt = (
        select(CourseSection)
        .where(CourseSection.course_id == course_id, CourseSection.deleted_at.is_(None))
        .order_by(CourseSection.position)
    )
    return (await db.scalars(stmt)).all()


@router.delete("/{course_id}/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: uuid.UUID,
    course: Course = Depends(require_course_management("course.manage_content")),
    db: AsyncSession = Depends(get_db),
):
    section = await db.get(CourseSection, section_id)
    if section is None or section.course_id != course.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    await db.delete(section)
    await db.commit()


@router.post(
    "/{course_id}/sections/{section_id}/contents",
    response_model=LearningContentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_content(
    section_id: uuid.UUID,
    payload: LearningContentCreate,
    course: Course = Depends(require_course_management("course.manage_content")),
    db: AsyncSession = Depends(get_db),
):
    section = await db.get(CourseSection, section_id)
    if section is None or section.course_id != course.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    existing = await db.scalar(
        select(LearningContent).where(
            LearningContent.section_id == section_id, LearningContent.position == payload.position
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Position already used in this section"
        )

    content = LearningContent(section_id=section_id, **payload.model_dump())
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


@router.get("/{course_id}/sections/{section_id}/contents", response_model=list[LearningContentOut])
async def list_contents(
    course_id: uuid.UUID,
    section_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    _assert_viewable(course, current_user)

    stmt = (
        select(LearningContent)
        .where(LearningContent.section_id == section_id, LearningContent.deleted_at.is_(None))
        .order_by(LearningContent.position)
    )
    return (await db.scalars(stmt)).all()


@router.patch(
    "/{course_id}/sections/{section_id}/contents/{content_id}/status",
    response_model=LearningContentOut,
)
async def update_content_status(
    section_id: uuid.UUID,
    content_id: uuid.UUID,
    payload: LearningContentStatusUpdate,
    course: Course = Depends(require_course_management("course.manage_content")),
    db: AsyncSession = Depends(get_db),
):
    content = await db.get(LearningContent, content_id)
    if content is None or content.section_id != section_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    section = await db.get(CourseSection, section_id)
    if section is None or section.course_id != course.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    content.status = payload.status
    await db.commit()
    await db.refresh(content)
    return content
