import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_optional, require_course_management
from app.core.security import decode_token
from app.models.content import LearningContent
from app.models.courses import Course
from app.models.identity import User
from app.models.media import MediaAsset
from app.schemas.content import (
    ArticleUpdate,
    AssignmentUpdate,
    ContentDetailOut,
    MediaAssetOut,
    QuestionIn,
    QuizSettingsUpdate,
    ResourceUpdate,
    VideoUpdate,
)
from app.schemas.course import LearningContentUpdate
from app.services import assessment_service, content_service, course_service, media_service

router = APIRouter(tags=["course content"])

manage_content = require_course_management("course.manage_content")


async def _detail(db: AsyncSession, content: LearningContent) -> ContentDetailOut:
    await db.refresh(content)
    return await content_service.build_detail(db, content, for_manager=True)


# --- Media ------------------------------------------------------------------


@router.post(
    "/courses/{course_id}/media", response_model=MediaAssetOut, status_code=status.HTTP_201_CREATED
)
async def upload_media(
    file: UploadFile,
    course: Course = Depends(manage_content),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a video, document or image for this course, then attach it to a
    lesson (or set it as the course thumbnail) by its id."""
    asset = await media_service.save_upload(db, current_user.id, course.id, file)
    return media_service.to_out(asset)


@router.get("/courses/{course_id}/media", response_model=list[MediaAssetOut])
async def list_media(
    course: Course = Depends(manage_content),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MediaAsset)
        .where(MediaAsset.course_id == course.id)
        .order_by(MediaAsset.created_at.desc())
    )
    return [media_service.to_out(asset) for asset in (await db.scalars(stmt)).all()]


@router.get("/media/{asset_id}/file")
async def download_media(asset_id: uuid.UUID, token: str, db: AsyncSession = Depends(get_db)):
    """Serves a file to whoever holds a signed URL for it. Media players and plain
    links cannot send an Authorization header, so access is granted when the URL
    is issued (see content_service.authorize_view) rather than here."""
    forbidden = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired media link"
    )
    try:
        payload = decode_token(token)
    except ValueError:
        raise forbidden
    if payload.get("type") != "media" or payload.get("sub") != str(asset_id):
        raise forbidden

    asset = await db.get(MediaAsset, asset_id)
    path = media_service.file_path(asset) if asset is not None else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return FileResponse(
        path,
        media_type=asset.mime_type or "application/octet-stream",
        filename=asset.original_filename,
        content_disposition_type="inline",
    )


# --- Lessons ----------------------------------------------------------------


@router.get("/courses/{course_id}/contents/{content_id}", response_model=ContentDetailOut)
async def get_content(
    course_id: uuid.UUID,
    content_id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """A lesson with its body. Quiz answers are only included for the course's teachers."""
    course = await db.get(Course, course_id)
    if course is None or course.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    content = await course_service.get_content(db, course_id, content_id)
    is_manager = await content_service.authorize_view(db, course, content, current_user)
    return await content_service.build_detail(db, content, for_manager=is_manager)


@router.patch("/courses/{course_id}/contents/{content_id}", response_model=ContentDetailOut)
async def update_content(
    content_id: uuid.UUID,
    payload: LearningContentUpdate,
    course: Course = Depends(manage_content),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(content, field, value)
    await db.commit()
    return await _detail(db, content)


@router.delete(
    "/courses/{course_id}/contents/{content_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_content(
    content_id: uuid.UUID,
    course: Course = Depends(manage_content),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    await course_service.hard_delete(
        db,
        LearningContent,
        content.id,
        "Students have already worked on this lesson; archive it instead",
    )


@router.put("/courses/{course_id}/contents/{content_id}/article", response_model=ContentDetailOut)
async def set_article(
    content_id: uuid.UUID,
    payload: ArticleUpdate,
    course: Course = Depends(manage_content),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    await content_service.set_article(db, content, current_user.id, payload)
    return await _detail(db, content)


@router.put("/courses/{course_id}/contents/{content_id}/video", response_model=ContentDetailOut)
async def set_video(
    content_id: uuid.UUID,
    payload: VideoUpdate,
    course: Course = Depends(manage_content),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    await content_service.set_video(db, course, content, payload)
    return await _detail(db, content)


@router.put("/courses/{course_id}/contents/{content_id}/resource", response_model=ContentDetailOut)
async def set_resource(
    content_id: uuid.UUID,
    payload: ResourceUpdate,
    course: Course = Depends(manage_content),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    await content_service.set_resource(db, course, content, payload)
    return await _detail(db, content)


@router.put(
    "/courses/{course_id}/contents/{content_id}/assignment", response_model=ContentDetailOut
)
async def set_assignment(
    content_id: uuid.UUID,
    payload: AssignmentUpdate,
    course: Course = Depends(manage_content),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    await content_service.set_assignment(db, content, payload)
    return await _detail(db, content)


# --- Quiz authoring ---------------------------------------------------------


@router.put("/courses/{course_id}/contents/{content_id}/quiz", response_model=ContentDetailOut)
async def set_quiz_settings(
    content_id: uuid.UUID,
    payload: QuizSettingsUpdate,
    course: Course = Depends(manage_content),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    await content_service.set_quiz_settings(db, content, payload)
    return await _detail(db, content)


@router.post(
    "/courses/{course_id}/contents/{content_id}/quiz/questions",
    response_model=ContentDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_question(
    content_id: uuid.UUID,
    payload: QuestionIn,
    course: Course = Depends(manage_content),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    await assessment_service.add_question(db, content, current_user.id, payload)
    return await _detail(db, content)


@router.put(
    "/courses/{course_id}/contents/{content_id}/quiz/questions/{question_id}",
    response_model=ContentDetailOut,
)
async def update_question(
    content_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: QuestionIn,
    course: Course = Depends(manage_content),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    await assessment_service.update_question(db, content, question_id, current_user.id, payload)
    return await _detail(db, content)


@router.delete(
    "/courses/{course_id}/contents/{content_id}/quiz/questions/{question_id}",
    response_model=ContentDetailOut,
)
async def delete_question(
    content_id: uuid.UUID,
    question_id: uuid.UUID,
    course: Course = Depends(manage_content),
    db: AsyncSession = Depends(get_db),
):
    content = await course_service.get_content(db, course.id, content_id)
    await assessment_service.delete_question(db, content, question_id)
    return await _detail(db, content)
