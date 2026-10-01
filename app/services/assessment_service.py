import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessments import (
    QuestionOption,
    QuestionVersion,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
)
from app.models.assignments import AssignmentGrade, AssignmentSubmission
from app.models.content import AssignmentContent, CourseSection, LearningContent, QuizContent
from app.models.enums import ContentType
from app.models.identity import User
from app.schemas.content import (
    GradeIn,
    GradeOut,
    QuestionIn,
    QuestionOptionOut,
    QuestionOut,
    QuizAnswerOut,
    QuizAttemptOut,
    QuizAttemptSubmit,
    SubmissionCreate,
    SubmissionOut,
)
from app.schemas.progress import LearningProgressUpdate
from app.services import progress_service
from app.services.enrollment_service import get_learning_enrollment

NOT_ENROLLED = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this course"
)


def expect_type(content: LearningContent, content_type: ContentType) -> None:
    if content.content_type != content_type:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This lesson is {content.content_type.value}, not {content_type.value}",
        )


# --- Quiz authoring ---------------------------------------------------------


async def ensure_quiz(db: AsyncSession, content: LearningContent) -> QuizContent:
    expect_type(content, ContentType.QUIZ)
    quiz = await db.get(QuizContent, content.id)
    if quiz is None:
        quiz = QuizContent(content_id=content.id)
        db.add(quiz)
        await db.flush()
        await db.refresh(quiz)
    return quiz


async def list_questions(
    db: AsyncSession, quiz_content_id: uuid.UUID, *, include_answers: bool
) -> list[QuestionOut]:
    questions = (
        await db.scalars(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_content_id == quiz_content_id)
            .order_by(QuizQuestion.position)
        )
    ).all()
    version_ids = [q.current_version_id for q in questions if q.current_version_id is not None]
    if not version_ids:
        return []

    versions = {
        v.id: v
        for v in (
            await db.scalars(select(QuestionVersion).where(QuestionVersion.id.in_(version_ids)))
        ).all()
    }
    options: dict[uuid.UUID, list[QuestionOption]] = {}
    option_stmt = (
        select(QuestionOption)
        .where(QuestionOption.question_version_id.in_(version_ids))
        .order_by(QuestionOption.position)
    )
    for option in (await db.scalars(option_stmt)).all():
        options.setdefault(option.question_version_id, []).append(option)

    result = []
    for question in questions:
        version = versions.get(question.current_version_id)
        if version is None:
            continue
        out = QuestionOut(
            id=question.id,
            question_type=question.question_type,
            position=question.position,
            points=float(question.points),
            question_text=version.question_text,
            options=[
                QuestionOptionOut(
                    id=o.id,
                    option_text=o.option_text,
                    position=o.position,
                    is_correct=o.is_correct if include_answers else None,
                )
                for o in options.get(version.id, [])
            ],
        )
        if include_answers:
            out.explanation = version.explanation
            if question.question_type == "SHORT_ANSWER":
                out.accepted_answers = (version.grading_config or {}).get("accepted_answers", [])
        result.append(out)
    return result


async def _add_version(
    db: AsyncSession, question: QuizQuestion, author_id: uuid.UUID, data: QuestionIn
) -> None:
    """Questions are versioned so past attempts keep pointing at the wording they answered."""
    last_version = await db.scalar(
        select(func.max(QuestionVersion.version_number)).where(
            QuestionVersion.question_id == question.id
        )
    )
    grading_config = None
    if data.question_type == "SHORT_ANSWER":
        grading_config = {
            "accepted_answers": [a.strip() for a in data.accepted_answers if a.strip()]
        }

    version = QuestionVersion(
        question_id=question.id,
        version_number=(last_version or 0) + 1,
        question_text=data.question_text,
        explanation=data.explanation,
        grading_config=grading_config,
        created_by=author_id,
    )
    db.add(version)
    await db.flush()

    for position, option in enumerate(data.options, start=1):
        db.add(
            QuestionOption(
                question_version_id=version.id,
                option_text=option.option_text,
                is_correct=option.is_correct,
                position=position,
            )
        )
    question.current_version_id = version.id


async def _get_question(
    db: AsyncSession, content: LearningContent, question_id: uuid.UUID
) -> QuizQuestion:
    question = await db.get(QuizQuestion, question_id)
    if question is None or question.quiz_content_id != content.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


async def add_question(
    db: AsyncSession, content: LearningContent, author_id: uuid.UUID, data: QuestionIn
) -> uuid.UUID:
    quiz = await ensure_quiz(db, content)
    last_position = await db.scalar(
        select(func.max(QuizQuestion.position)).where(
            QuizQuestion.quiz_content_id == quiz.content_id
        )
    )
    question = QuizQuestion(
        quiz_content_id=quiz.content_id,
        question_type=data.question_type,
        position=(last_position or 0) + 1,
        points=Decimal(str(data.points)),
    )
    db.add(question)
    await db.flush()
    await _add_version(db, question, author_id, data)
    await db.commit()
    return question.id


async def update_question(
    db: AsyncSession,
    content: LearningContent,
    question_id: uuid.UUID,
    author_id: uuid.UUID,
    data: QuestionIn,
) -> None:
    expect_type(content, ContentType.QUIZ)
    question = await _get_question(db, content, question_id)
    question.question_type = data.question_type
    question.points = Decimal(str(data.points))
    await _add_version(db, question, author_id, data)
    await db.commit()


async def delete_question(
    db: AsyncSession, content: LearningContent, question_id: uuid.UUID
) -> None:
    question = await _get_question(db, content, question_id)
    try:
        await db.execute(delete(QuizQuestion).where(QuizQuestion.id == question.id))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Students have already answered this question; edit it instead",
        )


# --- Quiz attempts ----------------------------------------------------------


async def submit_attempt(
    db: AsyncSession,
    course_id: uuid.UUID,
    content: LearningContent,
    user: User,
    data: QuizAttemptSubmit,
) -> QuizAttemptOut:
    expect_type(content, ContentType.QUIZ)
    enrollment = await get_learning_enrollment(db, user.id, course_id)
    if enrollment is None:
        raise NOT_ENROLLED

    quiz = await db.get(QuizContent, content.id)
    questions = (
        (
            await db.scalars(
                select(QuizQuestion).where(
                    QuizQuestion.quiz_content_id == content.id,
                    QuizQuestion.current_version_id.is_not(None),
                )
            )
        ).all()
        if quiz is not None
        else []
    )
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This quiz has no questions yet"
        )

    previous_attempts = await db.scalar(
        select(func.count()).where(
            QuizAttempt.quiz_content_id == content.id, QuizAttempt.user_id == user.id
        )
    )
    if quiz.attempt_limit is not None and previous_attempts >= quiz.attempt_limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No attempts left for this quiz"
        )

    version_ids = [q.current_version_id for q in questions]
    versions = {
        v.id: v
        for v in (
            await db.scalars(select(QuestionVersion).where(QuestionVersion.id.in_(version_ids)))
        ).all()
    }
    options = {
        o.id: o
        for o in (
            await db.scalars(
                select(QuestionOption).where(QuestionOption.question_version_id.in_(version_ids))
            )
        ).all()
    }
    given = {answer.question_id: answer for answer in data.answers}

    now = datetime.now(timezone.utc)
    score = Decimal("0")
    total = Decimal("0")
    answers: list[QuizAnswer] = []
    for question in questions:
        points = Decimal(str(question.points))
        total += points
        answer = given.get(question.id)
        if answer is None:
            continue

        version = versions[question.current_version_id]
        selected_option_id = None
        answer_text = None
        correct = False
        if question.question_type == "SHORT_ANSWER":
            answer_text = (answer.answer_text or "").strip()
            accepted = (version.grading_config or {}).get("accepted_answers", [])
            correct = answer_text.casefold() in {a.casefold() for a in accepted}
        else:
            option = options.get(answer.selected_option_id)
            # Ignore option ids that belong to another question.
            if option is not None and option.question_version_id == version.id:
                selected_option_id = option.id
                correct = option.is_correct

        awarded = points if correct else Decimal("0")
        score += awarded
        answers.append(
            QuizAnswer(
                question_id=question.id,
                question_version_id=version.id,
                selected_option_id=selected_option_id,
                answer_text=answer_text,
                is_correct=correct,
                points_awarded=awarded,
                graded_at=now,
            )
        )

    percentage = (score / total * Decimal("100")).quantize(Decimal("0.01"))
    passed = percentage >= Decimal(str(quiz.pass_percentage))

    attempt = QuizAttempt(
        quiz_content_id=content.id,
        user_id=user.id,
        enrollment_id=enrollment.id,
        attempt_number=previous_attempts + 1,
        status="GRADED",
        submitted_at=now,
        score=score,
        percentage=percentage,
        passed=passed,
    )
    db.add(attempt)
    await db.flush()
    for answer in answers:
        answer.attempt_id = attempt.id
        db.add(answer)
    await db.commit()
    await db.refresh(attempt)

    if passed:
        await progress_service.upsert_progress(
            db,
            user.id,
            content.id,
            LearningProgressUpdate(status="COMPLETED", completion_percentage=100),
        )

    out = QuizAttemptOut.model_validate(attempt)
    out.answers = [QuizAnswerOut.model_validate(a) for a in answers]
    return out


async def list_attempts(
    db: AsyncSession, content: LearningContent, user_id: uuid.UUID | None = None
) -> list[QuizAttemptOut]:
    """All attempts on a quiz, or only one student's when user_id is given."""
    expect_type(content, ContentType.QUIZ)
    stmt = (
        select(QuizAttempt, User.display_name)
        .join(User, User.id == QuizAttempt.user_id)
        .where(QuizAttempt.quiz_content_id == content.id)
        .order_by(QuizAttempt.started_at.desc())
    )
    if user_id is not None:
        stmt = stmt.where(QuizAttempt.user_id == user_id)

    result = []
    for attempt, student_name in (await db.execute(stmt)).all():
        out = QuizAttemptOut.model_validate(attempt)
        out.student_name = student_name
        result.append(out)
    return result


# --- Assignments ------------------------------------------------------------


async def submit_assignment(
    db: AsyncSession,
    course_id: uuid.UUID,
    content: LearningContent,
    user: User,
    data: SubmissionCreate,
) -> SubmissionOut:
    expect_type(content, ContentType.ASSIGNMENT)
    enrollment = await get_learning_enrollment(db, user.id, course_id)
    if enrollment is None:
        raise NOT_ENROLLED

    assignment = await db.get(AssignmentContent, content.id)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This assignment has no instructions yet",
        )

    previous = await db.scalar(
        select(func.count()).where(
            AssignmentSubmission.assignment_content_id == content.id,
            AssignmentSubmission.user_id == user.id,
        )
    )
    if previous and not assignment.allow_resubmission:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This assignment does not allow resubmission",
        )

    submission = AssignmentSubmission(
        assignment_content_id=content.id,
        user_id=user.id,
        enrollment_id=enrollment.id,
        attempt_number=previous + 1,
        text_submission=data.text_submission,
        external_url=data.external_url,
    )
    db.add(submission)
    await db.commit()
    return (await list_submissions(db, submission_id=submission.id))[0]


async def list_submissions(
    db: AsyncSession,
    *,
    course_ids=None,
    content_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    submission_id: uuid.UUID | None = None,
    submission_status: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[SubmissionOut]:
    """course_ids may be a list or a subquery of course ids."""
    stmt = (
        select(AssignmentSubmission, LearningContent.title, CourseSection.course_id, User.display_name)
        .join(LearningContent, LearningContent.id == AssignmentSubmission.assignment_content_id)
        .join(CourseSection, CourseSection.id == LearningContent.section_id)
        .join(User, User.id == AssignmentSubmission.user_id)
        .order_by(AssignmentSubmission.submitted_at.desc())
    )
    if course_ids is not None:
        stmt = stmt.where(CourseSection.course_id.in_(course_ids))
    if content_id is not None:
        stmt = stmt.where(AssignmentSubmission.assignment_content_id == content_id)
    if user_id is not None:
        stmt = stmt.where(AssignmentSubmission.user_id == user_id)
    if submission_id is not None:
        stmt = stmt.where(AssignmentSubmission.id == submission_id)
    if submission_status is not None:
        stmt = stmt.where(AssignmentSubmission.status == submission_status)
    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)

    rows = (await db.execute(stmt)).all()
    grades: dict[uuid.UUID, AssignmentGrade] = {}
    if rows:
        grade_stmt = (
            select(AssignmentGrade)
            .where(AssignmentGrade.submission_id.in_([row[0].id for row in rows]))
            .order_by(AssignmentGrade.graded_at)
        )
        for grade in (await db.scalars(grade_stmt)).all():
            grades[grade.submission_id] = grade

    result = []
    for submission, content_title, course_id, student_name in rows:
        grade = grades.get(submission.id)
        result.append(
            SubmissionOut(
                id=submission.id,
                course_id=course_id,
                content_id=submission.assignment_content_id,
                content_title=content_title,
                user_id=submission.user_id,
                student_name=student_name,
                attempt_number=submission.attempt_number,
                text_submission=submission.text_submission,
                external_url=submission.external_url,
                status=submission.status,
                submitted_at=submission.submitted_at,
                grade=GradeOut.model_validate(grade) if grade is not None else None,
            )
        )
    return result


async def grade_submission(
    db: AsyncSession,
    course_id: uuid.UUID,
    submission_id: uuid.UUID,
    grader_id: uuid.UUID,
    data: GradeIn,
) -> SubmissionOut:
    found = await list_submissions(db, course_ids=[course_id], submission_id=submission_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    submission = await db.get(AssignmentSubmission, submission_id)
    grade = await db.scalar(
        select(AssignmentGrade).where(AssignmentGrade.submission_id == submission_id)
    )
    if grade is None:
        grade = AssignmentGrade(submission_id=submission_id)
        db.add(grade)
    grade.grader_user_id = grader_id
    grade.score = Decimal(str(data.score))
    grade.feedback = data.feedback
    grade.graded_at = datetime.now(timezone.utc)
    submission.status = "GRADED"
    await db.commit()

    return (await list_submissions(db, submission_id=submission_id))[0]
