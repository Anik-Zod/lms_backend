import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_course_management
from app.models.courses import Course
from app.models.identity import User
from app.schemas.content import SubmissionOut
from app.schemas.course import (
    CourseInstructorAdd,
    CourseInstructorOut,
    CourseOut,
    CoursePriceOut,
    CoursePriceUpdate,
    CourseStudentOut,
)
from app.schemas.teaching import (
    EarningsOut,
    InstructorProfileOut,
    InstructorProfileUpdate,
    TeachingOverviewOut,
)
from app.services import assessment_service, course_service, rbac_service, teaching_service

router = APIRouter(tags=["teaching"])


# --- The teacher's own dashboard --------------------------------------------
# These are scoped to the caller's courses, so any signed-in user may call them;
# someone who teaches nothing simply gets empty results.


@router.get("/teaching/overview", response_model=TeachingOverviewOut)
async def get_overview(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await teaching_service.get_overview(db, current_user.id)


@router.get("/teaching/courses", response_model=list[CourseOut])
async def list_my_courses(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Every course the caller owns or co-teaches, in any status, drafts included."""
    return await teaching_service.list_courses(db, current_user.id, limit, offset)


@router.get("/teaching/submissions", response_model=list[SubmissionOut])
async def list_submissions_to_grade(
    submission_status: Literal["SUBMITTED", "GRADED"] | None = Query(
        default="SUBMITTED", alias="status"
    ),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Assignment submissions across all the caller's courses; ungraded ones by default."""
    return await assessment_service.list_submissions(
        db,
        course_ids=course_service.managed_course_ids(current_user.id),
        submission_status=submission_status,
        limit=limit,
        offset=offset,
    )


@router.get("/teaching/earnings", response_model=EarningsOut)
async def get_earnings(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await teaching_service.get_earnings(db, current_user.id)


@router.get("/teaching/profile", response_model=InstructorProfileOut)
async def get_instructor_profile(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await teaching_service.get_profile(db, current_user.id)


@router.patch("/teaching/profile", response_model=InstructorProfileOut)
async def update_instructor_profile(
    payload: InstructorProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await teaching_service.update_profile(db, current_user.id, payload)


# --- Per-course management --------------------------------------------------


async def _require_owner(
    course: Course = Depends(require_course_management("course.update")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Course:
    """Co-instructors can edit a course but cannot change its price or its staff."""
    if course.owner_user_id != current_user.id and not await rbac_service.has_permission(
        db, current_user.id, "course.update"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the course owner can do this"
        )
    return course


@router.put("/courses/{course_id}/price", response_model=CoursePriceOut)
async def set_course_price(
    payload: CoursePriceUpdate,
    course: Course = Depends(_require_owner),
    db: AsyncSession = Depends(get_db),
):
    return await teaching_service.set_price(db, course, payload)


@router.get("/courses/{course_id}/students", response_model=list[CourseStudentOut])
async def list_course_students(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    course: Course = Depends(require_course_management("enrollment.read")),
    db: AsyncSession = Depends(get_db),
):
    return await teaching_service.list_students(db, course.id, limit, offset)


@router.get("/courses/{course_id}/instructors", response_model=list[CourseInstructorOut])
async def list_course_instructors(
    course: Course = Depends(require_course_management("course.update")),
    db: AsyncSession = Depends(get_db),
):
    return await teaching_service.list_instructors(db, course)


@router.post(
    "/courses/{course_id}/instructors",
    response_model=list[CourseInstructorOut],
    status_code=status.HTTP_201_CREATED,
)
async def add_course_instructor(
    payload: CourseInstructorAdd,
    course: Course = Depends(_require_owner),
    db: AsyncSession = Depends(get_db),
):
    await teaching_service.add_instructor(db, course, payload)
    return await teaching_service.list_instructors(db, course)


@router.delete(
    "/courses/{course_id}/instructors/{user_id}", response_model=list[CourseInstructorOut]
)
async def remove_course_instructor(
    user_id: uuid.UUID,
    course: Course = Depends(_require_owner),
    db: AsyncSession = Depends(get_db),
):
    await teaching_service.remove_instructor(db, course, user_id)
    return await teaching_service.list_instructors(db, course)
