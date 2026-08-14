import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.courses import Course, CourseInstructor
from app.models.identity import User
from app.models.rbac import Permission, Role, RolePermission, UserRoleAssignment

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
    """Grants access if the user holds any active (unexpired) role assignment
    whose role carries this permission code, at any scope."""

    async def checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        now = datetime.now(timezone.utc)
        stmt = (
            select(UserRoleAssignment.id)
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                UserRoleAssignment.user_id == current_user.id,
                Permission.code == code,
                or_(UserRoleAssignment.expires_at.is_(None), UserRoleAssignment.expires_at > now),
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        if result.first() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {code}"
            )
        return current_user

    return checker


async def _has_global_permission(db: AsyncSession, user_id: uuid.UUID, code: str) -> bool:
    now = datetime.now(timezone.utc)
    stmt = (
        select(UserRoleAssignment.id)
        .join(Role, Role.id == UserRoleAssignment.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            UserRoleAssignment.user_id == user_id,
            Permission.code == code,
            or_(UserRoleAssignment.expires_at.is_(None), UserRoleAssignment.expires_at > now),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.first() is not None


def require_course_management(permission_code: str = "course.update"):
    """Authorizes course mutation: owner, co-instructor/TA on the course,
    or a global role assignment granting the permission. Ownership is never
    inferred from enrollment (see design A.4)."""

    async def checker(
        course_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Course:
        course = await db.get(Course, course_id)
        if course is None or course.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        if course.owner_user_id == current_user.id:
            return course

        ci_stmt = select(CourseInstructor.course_id).where(
            CourseInstructor.course_id == course_id,
            CourseInstructor.user_id == current_user.id,
        )
        if (await db.execute(ci_stmt)).first() is not None:
            return course

        if await _has_global_permission(db, current_user.id, permission_code):
            return course

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to manage this course"
        )

    return checker
