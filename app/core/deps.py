import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.courses import Course, CourseInstructor
from app.models.identity import User
from app.services import rbac_service

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_exception
    token = credentials.credentials

    try:
        payload = decode_token(token)
    except ValueError:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = await db.get(User, uuid.UUID(user_id))
    if user is None or user.deleted_at is not None:
        raise credentials_exception
    if user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_permission(code: str):
    """Grants access if the user holds an active, platform-wide role assignment
    whose role carries this permission code."""

    async def checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if not await rbac_service.has_permission(db, current_user.id, code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {code}"
            )
        return current_user

    return checker


async def can_manage_course(
    db: AsyncSession, user: User, course: Course, permission_code: str = "course.update"
) -> bool:
    """Owner, co-instructor/TA on the course, or a global role assignment granting
    the permission. Ownership is never inferred from enrollment (see design A.4)."""
    if course.owner_user_id == user.id:
        return True

    ci_stmt = select(CourseInstructor.course_id).where(
        CourseInstructor.course_id == course.id,
        CourseInstructor.user_id == user.id,
    )
    if (await db.execute(ci_stmt)).first() is not None:
        return True

    return await rbac_service.has_permission(db, user.id, permission_code)


def require_course_management(permission_code: str = "course.update"):
    """Authorizes course mutation; see can_manage_course for who qualifies."""

    async def checker(
        course_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Course:
        course = await db.get(Course, course_id)
        if course is None or course.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        if not await can_manage_course(db, current_user, course, permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to manage this course"
            )
        return course

    return checker
