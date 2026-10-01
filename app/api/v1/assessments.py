import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_course_management
from app.models.courses import Course
from app.models.enums import ContentType
from app.models.identity import User
from app.schemas.content import (
    GradeIn,
    QuizAttemptOut,
    QuizAttemptSubmit,
    SubmissionCreate,
    SubmissionOut,
)
from app.services import assessment_service, course_service

router = APIRouter(prefix="/courses/{course_id}", tags=["assessments"])

manage_course = require_course_management("course.manage_content")


# --- Students ---------------------------------------------------------------


@router.post(
    "/contents/{content_id}/quiz/attempts",
    response_model=QuizAttemptOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_quiz_attempt(
    course_id: uuid.UUID,
    content_id: uuid.UUID,
    payload: QuizAttemptSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit all answers at once; the attempt is graded immediately."""
    content = await course_service.get_content(db, course_id, content_id)
    return await assessment_service.submit_attempt(db, course_id, content, current_user, payload)


@router.get("/contents/{content_id}/quiz/attempts/me", response_model=list[QuizAttemptOut])
async def list_my_quiz_attempts(
    course_id: uuid.UUID,
    content_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course_id, content_id)
    return await assessment_service.list_attempts(db, content, user_id=current_user.id)


@router.post(
    "/contents/{content_id}/assignment/submissions",
    response_model=SubmissionOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_assignment(
    course_id: uuid.UUID,
    content_id: uuid.UUID,
    payload: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course_id, content_id)
    return await assessment_service.submit_assignment(db, course_id, content, current_user, payload)


@router.get(
    "/contents/{content_id}/assignment/submissions/me", response_model=list[SubmissionOut]
)
async def list_my_submissions(
    course_id: uuid.UUID,
    content_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The caller's own submissions for this assignment, with grades and feedback."""
    content = await course_service.get_content(db, course_id, content_id)
    return await assessment_service.list_submissions(
        db, content_id=content.id, user_id=current_user.id
    )


# --- Teachers ---------------------------------------------------------------


@router.get("/contents/{content_id}/quiz/attempts", response_model=list[QuizAttemptOut])
async def list_quiz_attempts(
    content_id: uuid.UUID,
    course: Course = Depends(manage_course),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    return await assessment_service.list_attempts(db, content)


@router.get("/contents/{content_id}/assignment/submissions", response_model=list[SubmissionOut])
async def list_assignment_submissions(
    content_id: uuid.UUID,
    course: Course = Depends(manage_course),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    assessment_service.expect_type(content, ContentType.ASSIGNMENT)
    return await assessment_service.list_submissions(db, content_id=content.id)


@router.put("/submissions/{submission_id}/grade", response_model=SubmissionOut)
async def grade_submission(
    submission_id: uuid.UUID,
    payload: GradeIn,
    course: Course = Depends(manage_course),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Score a submission out of 100. Grading again replaces the earlier grade."""
    return await assessment_service.grade_submission(
        db, course.id, submission_id, current_user.id, payload
    )
