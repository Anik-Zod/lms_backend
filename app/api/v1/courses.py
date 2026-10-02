import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import (
    can_manage_course,
    get_current_user,
    get_current_user_optional,
    require_course_management,
    require_permission,
)
from app.models.content import CourseSection, LearningContent
from app.models.courses import Course
from app.models.enrollment import Enrollment
from app.models.enums import ContentStatus, CourseStatus, CourseVisibility
from app.models.identity import User
from app.schemas.course import (
    CourseCreate,
    CourseOut,
    CourseSectionCreate,
    CourseSectionOut,
    CourseSectionUpdate,
    CourseStatusUpdate,
    CourseUpdate,
    CurriculumSectionOut,
    LearningContentCreate,
    LearningContentOut,
    LearningContentStatusUpdate,
    ReorderRequest,
)
from app.services import course_service, media_service, rbac_service

router = APIRouter(prefix="/courses", tags=["courses"])


async def _get_viewable_course(
    db: AsyncSession, course_id: uuid.UUID, current_user: User | None
) -> tuple[Course, bool]:
    """The course plus whether the caller manages it. Anyone can see a published
    public course; drafts are visible only to the people who teach them."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    course = await db.get(Course, course_id)
    if course is None or course.deleted_at is not None:
        raise not_found
    if current_user is not None and await can_manage_course(db, current_user, course):
        return course, True
    if course.status == CourseStatus.PUBLISHED and course.visibility == CourseVisibility.PUBLIC:
        return course, False
    raise not_found


def _visible_contents(stmt, is_manager: bool):
    stmt = stmt.where(LearningContent.deleted_at.is_(None))
    if not is_manager:
        stmt = stmt.where(LearningContent.status == ContentStatus.PUBLISHED)
    return stmt


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate,
    current_user: User = Depends(require_permission("course.create")),
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
    return await course_service.with_catalog_fields(db, list((await db.scalars(stmt)).all()))


@router.get("/{course_id}", response_model=CourseOut)
async def get_course(
    course_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    course, _ = await _get_viewable_course(db, course_id, current_user)
    return (await course_service.with_catalog_fields(db, [course]))[0]


@router.patch("/{course_id}", response_model=CourseOut)
async def update_course(
    payload: CourseUpdate,
    course: Course = Depends(require_course_management("course.update")),
    db: AsyncSession = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("thumbnail_media_id") is not None:
        asset = await media_service.get_course_asset(db, course.id, updates["thumbnail_media_id"])
        if not (asset.mime_type or "").startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Thumbnail must be an image file"
            )
    for field, value in updates.items():
        setattr(course, field, value)
    await db.commit()
    await db.refresh(course)
    return (await course_service.with_catalog_fields(db, [course]))[0]


@router.patch("/{course_id}/status", response_model=CourseOut)
async def update_course_status(
    payload: CourseStatusUpdate,
    course: Course = Depends(require_course_management("course.publish")),
    db: AsyncSession = Depends(get_db),
):
    if payload.status == CourseStatus.PUBLISHED and course.published_at is None:
        course.published_at = datetime.now(timezone.utc)
    course.status = payload.status
    await db.commit()
    await db.refresh(course)
    return (await course_service.with_catalog_fields(db, [course]))[0]


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course: Course = Depends(require_course_management("course.archive")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Co-instructors can edit a course but only its owner (or an admin) can remove it.
    if course.owner_user_id != current_user.id and not await rbac_service.has_permission(
        db, current_user.id, "course.archive"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the course owner can delete it"
        )

    enrolled = await db.scalar(select(func.count()).where(Enrollment.course_id == course.id))
    if enrolled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Students are enrolled in this course; archive it instead",
        )

    course.deleted_at = datetime.now(timezone.utc)
    # Free the slug for reuse; the row itself is kept.
    course.slug = f"{course.slug[:200]}-deleted-{course.id.hex[:12]}"
    await db.commit()


@router.get("/{course_id}/curriculum", response_model=list[CurriculumSectionOut])
async def get_curriculum(
    course_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Sections with their lessons in one call. Learners only get published lessons."""
    _, is_manager = await _get_viewable_course(db, course_id, current_user)

    sections = (
        await db.scalars(
            select(CourseSection)
            .where(CourseSection.course_id == course_id, CourseSection.deleted_at.is_(None))
            .order_by(CourseSection.position)
        )
    ).all()
    content_stmt = _visible_contents(
        select(LearningContent)
        .join(CourseSection, CourseSection.id == LearningContent.section_id)
        .where(CourseSection.course_id == course_id)
        .order_by(LearningContent.position),
        is_manager,
    )
    by_section: dict[uuid.UUID, list[LearningContent]] = {}
    for content in (await db.scalars(content_stmt)).all():
        by_section.setdefault(content.section_id, []).append(content)

    # Built field by field: validating the ORM section directly would lazy-load
    # its unfiltered `contents` relationship.
    return [
        CurriculumSectionOut(
            **CourseSectionOut.model_validate(section).model_dump(),
            contents=[
                LearningContentOut.model_validate(c) for c in by_section.get(section.id, [])
            ],
        )
        for section in sections
    ]


@router.post(
    "/{course_id}/sections", response_model=CourseSectionOut, status_code=status.HTTP_201_CREATED
)
async def create_section(
    payload: CourseSectionCreate,
    course: Course = Depends(require_course_management("course.manage_content")),
    db: AsyncSession = Depends(get_db),
):
    data = payload.model_dump()
    if data["position"] is None:
        data["position"] = await course_service.next_position(
            db, CourseSection, CourseSection.course_id, course.id
        )
    else:
        existing = await db.scalar(
            select(CourseSection).where(
                CourseSection.course_id == course.id, CourseSection.position == data["position"]
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Position already used in this course"
            )

    section = CourseSection(course_id=course.id, **data)
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
    await _get_viewable_course(db, course_id, current_user)

    stmt = (
        select(CourseSection)
        .where(CourseSection.course_id == course_id, CourseSection.deleted_at.is_(None))
        .order_by(CourseSection.position)
    )
    return (await db.scalars(stmt)).all()


@router.put("/{course_id}/sections/order", response_model=list[CourseSectionOut])
async def reorder_sections(
    payload: ReorderRequest,
    course: Course = Depends(require_course_management("course.manage_content")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CourseSection).where(CourseSection.course_id == course.id)
    sections = list((await db.scalars(stmt)).all())
    await course_service.reorder(db, sections, payload.ids)
    return sorted(sections, key=lambda s: s.position)


@router.patch("/{course_id}/sections/{section_id}", response_model=CourseSectionOut)
async def update_section(
    section_id: uuid.UUID,
    payload: CourseSectionUpdate,
    course: Course = Depends(require_course_management("course.manage_content")),
    db: AsyncSession = Depends(get_db),
):
    section = await course_service.get_section(db, course.id, section_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(section, field, value)
    await db.commit()
    await db.refresh(section)
    return section


@router.delete("/{course_id}/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: uuid.UUID,
    course: Course = Depends(require_course_management("course.manage_content")),
    db: AsyncSession = Depends(get_db),
):
    section = await course_service.get_section(db, course.id, section_id)
    await course_service.hard_delete(
        db,
        CourseSection,
        section.id,
        "Students have progress in this section; archive its lessons instead",
    )


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
    await course_service.get_section(db, course.id, section_id)

    data = payload.model_dump()
    if data["position"] is None:
        data["position"] = await course_service.next_position(
            db, LearningContent, LearningContent.section_id, section_id
        )
    else:
        existing = await db.scalar(
            select(LearningContent).where(
                LearningContent.section_id == section_id,
                LearningContent.position == data["position"],
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Position already used in this section",
            )

    content = LearningContent(section_id=section_id, **data)
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
    _, is_manager = await _get_viewable_course(db, course_id, current_user)
    await course_service.get_section(db, course_id, section_id)

    stmt = _visible_contents(
        select(LearningContent)
        .where(LearningContent.section_id == section_id)
        .order_by(LearningContent.position),
        is_manager,
    )
    return (await db.scalars(stmt)).all()


@router.put(
    "/{course_id}/sections/{section_id}/contents/order", response_model=list[LearningContentOut]
)
async def reorder_contents(
    section_id: uuid.UUID,
    payload: ReorderRequest,
    course: Course = Depends(require_course_management("course.manage_content")),
    db: AsyncSession = Depends(get_db),
):
    await course_service.get_section(db, course.id, section_id)
    stmt = select(LearningContent).where(LearningContent.section_id == section_id)
    contents = list((await db.scalars(stmt)).all())
    await course_service.reorder(db, contents, payload.ids)
    return sorted(contents, key=lambda c: c.position)


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
    content = await course_service.get_content(db, course.id, content_id)
    if content.section_id != section_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    content.status = payload.status
    await db.commit()
    await db.refresh(content)
    return content
