import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import can_manage_course
from app.models.content import (
    ArticleContent,
    ArticleContentRevision,
    AssignmentContent,
    LearningContent,
    QuizContent,
    ResourceContent,
    VideoContent,
)
from app.models.courses import Course
from app.models.enums import ContentStatus, ContentType, CourseStatus
from app.models.identity import User
from app.models.media import MediaAsset
from app.schemas.content import (
    ArticleOut,
    ArticleUpdate,
    AssignmentOut,
    AssignmentUpdate,
    ContentDetailOut,
    QuizOut,
    QuizSettingsUpdate,
    ResourceOut,
    ResourceUpdate,
    VideoOut,
    VideoUpdate,
)
from app.services import assessment_service, media_service
from app.services.assessment_service import expect_type
from app.services.enrollment_service import get_learning_enrollment

async def authorize_view(
    db: AsyncSession, course: Course, content: LearningContent, user: User | None
) -> bool:
    """Returns True for course managers, False for learners; raises otherwise.
    Learners see published lessons of a published course once enrolled, and
    preview lessons without enrolling."""
    if user is not None and await can_manage_course(db, user, course):
        return True

    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    if course.status != CourseStatus.PUBLISHED or content.status != ContentStatus.PUBLISHED:
        raise not_found
    if content.is_preview:
        return False
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to view this lesson"
        )
    if await get_learning_enrollment(db, user.id, course.id) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this course"
        )
    return False


async def set_article(
    db: AsyncSession, content: LearningContent, author_id: uuid.UUID, data: ArticleUpdate
) -> None:
    expect_type(content, ContentType.ARTICLE)

    article = await db.get(ArticleContent, content.id)
    if article is None:
        article = ArticleContent(content_id=content.id)
        db.add(article)
        await db.flush()
    article.body_format = data.body_format

    last_version = await db.scalar(
        select(func.max(ArticleContentRevision.version_number)).where(
            ArticleContentRevision.content_id == content.id
        )
    )
    revision = ArticleContentRevision(
        content_id=content.id,
        body=data.body,
        version_number=(last_version or 0) + 1,
        created_by=author_id,
    )
    db.add(revision)
    await db.flush()

    article.current_revision_id = revision.id
    await db.commit()


async def set_video(
    db: AsyncSession, course: Course, content: LearningContent, data: VideoUpdate
) -> None:
    expect_type(content, ContentType.VIDEO)
    asset = await media_service.get_course_asset(db, course.id, data.media_asset_id)
    if not (asset.mime_type or "").startswith("video/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Media asset is not a video file"
        )

    video = await db.get(VideoContent, content.id)
    if video is None:
        video = VideoContent(content_id=content.id)
        db.add(video)
    video.media_asset_id = asset.id
    video.duration_seconds = data.duration_seconds
    # Files are served as uploaded; there is no transcoding step.
    video.processing_status = "READY"
    video.provider = asset.storage_provider

    asset.content_id = content.id
    if data.duration_seconds is not None:
        content.estimated_duration_seconds = data.duration_seconds
    await db.commit()


async def set_resource(
    db: AsyncSession, course: Course, content: LearningContent, data: ResourceUpdate
) -> None:
    expect_type(content, ContentType.RESOURCE)
    asset = await media_service.get_course_asset(db, course.id, data.media_asset_id)

    resource = await db.get(ResourceContent, content.id)
    if resource is None:
        resource = ResourceContent(content_id=content.id)
        db.add(resource)
    resource.media_asset_id = asset.id
    resource.downloadable = data.downloadable

    asset.content_id = content.id
    await db.commit()


async def set_quiz_settings(
    db: AsyncSession, content: LearningContent, data: QuizSettingsUpdate
) -> None:
    quiz = await assessment_service.ensure_quiz(db, content)
    for field, value in data.model_dump().items():
        setattr(quiz, field, value)
    await db.commit()


async def set_assignment(
    db: AsyncSession, content: LearningContent, data: AssignmentUpdate
) -> None:
    expect_type(content, ContentType.ASSIGNMENT)
    assignment = await db.get(AssignmentContent, content.id)
    if assignment is None:
        assignment = AssignmentContent(content_id=content.id)
        db.add(assignment)
    for field, value in data.model_dump().items():
        setattr(assignment, field, value)
    await db.commit()


async def build_detail(
    db: AsyncSession, content: LearningContent, *, for_manager: bool
) -> ContentDetailOut:
    out = ContentDetailOut.model_validate(content)

    if content.content_type == ContentType.ARTICLE:
        article = await db.get(ArticleContent, content.id)
        if article is not None and article.current_revision_id is not None:
            revision = await db.get(ArticleContentRevision, article.current_revision_id)
            out.article = ArticleOut(
                body=revision.body,
                body_format=article.body_format,
                version_number=revision.version_number,
            )

    elif content.content_type == ContentType.VIDEO:
        video = await db.get(VideoContent, content.id)
        if video is not None:
            asset = await db.get(MediaAsset, video.media_asset_id)
            out.video = VideoOut(
                media_asset_id=video.media_asset_id,
                duration_seconds=video.duration_seconds,
                mime_type=asset.mime_type if asset else None,
                url=media_service.signed_url(video.media_asset_id),
            )

    elif content.content_type == ContentType.RESOURCE:
        resource = await db.get(ResourceContent, content.id)
        if resource is not None:
            asset = await db.get(MediaAsset, resource.media_asset_id)
            out.resource = ResourceOut(
                media_asset_id=resource.media_asset_id,
                filename=asset.original_filename if asset else None,
                mime_type=asset.mime_type if asset else None,
                size_bytes=asset.size_bytes if asset else None,
                downloadable=resource.downloadable,
                url=media_service.signed_url(resource.media_asset_id),
            )

    elif content.content_type == ContentType.QUIZ:
        quiz = await db.get(QuizContent, content.id)
        if quiz is not None:
            out.quiz = QuizOut(
                time_limit_seconds=quiz.time_limit_seconds,
                pass_percentage=float(quiz.pass_percentage),
                attempt_limit=quiz.attempt_limit,
                randomize_questions=quiz.randomize_questions,
                randomize_options=quiz.randomize_options,
                questions=await assessment_service.list_questions(
                    db, content.id, include_answers=for_manager
                ),
            )

    elif content.content_type == ContentType.ASSIGNMENT:
        assignment = await db.get(AssignmentContent, content.id)
        if assignment is not None:
            out.assignment = AssignmentOut.model_validate(assignment)

    return out
