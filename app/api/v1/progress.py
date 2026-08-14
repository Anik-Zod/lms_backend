import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.identity import User
from app.models.progress import CourseProgress
from app.schemas.progress import CourseProgressOut, LearningProgressOut, LearningProgressUpdate
from app.services import progress_service

router = APIRouter(tags=["progress"])


@router.put("/contents/{content_id}/progress", response_model=LearningProgressOut)
async def update_content_progress(
    content_id: uuid.UUID,
    payload: LearningProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await progress_service.upsert_progress(db, current_user.id, content_id, payload)


@router.get("/courses/{course_id}/progress", response_model=CourseProgressOut)
async def get_course_progress(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    progress = await db.get(CourseProgress, {"user_id": current_user.id, "course_id": course_id})
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No progress recorded")
    return progress
