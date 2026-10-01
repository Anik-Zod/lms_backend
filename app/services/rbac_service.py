import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.identity import User
from app.models.rbac import Permission, Role, RolePermission, UserRoleAssignment

DEFAULT_ROLE_CODE = "STUDENT"
SUPER_ADMIN_ROLE_CODE = "SUPER_ADMIN"


def _active_platform_assignment(user_id: uuid.UUID):
    """Filters for a user's unexpired, platform-wide (not org/course scoped) assignments."""
    now = datetime.now(timezone.utc)
    return (
        UserRoleAssignment.user_id == user_id,
        UserRoleAssignment.organization_id.is_(None),
        UserRoleAssignment.course_id.is_(None),
        or_(UserRoleAssignment.expires_at.is_(None), UserRoleAssignment.expires_at > now),
    )


async def get_role_codes(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    stmt = (
        select(Role.code)
        .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
        .where(*_active_platform_assignment(user_id))
        .order_by(Role.code)
    )
    return list((await db.scalars(stmt)).all())


async def get_permission_codes(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    stmt = (
        select(Permission.code)
        .distinct()
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRoleAssignment, UserRoleAssignment.role_id == RolePermission.role_id)
        .where(*_active_platform_assignment(user_id))
        .order_by(Permission.code)
    )
    return list((await db.scalars(stmt)).all())


async def has_permission(db: AsyncSession, user_id: uuid.UUID, code: str) -> bool:
    stmt = (
        select(UserRoleAssignment.id)
        .join(RolePermission, RolePermission.role_id == UserRoleAssignment.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(*_active_platform_assignment(user_id), Permission.code == code)
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


async def list_roles(db: AsyncSession) -> list[Role]:
    stmt = select(Role).options(selectinload(Role.permissions)).order_by(Role.code)
    return list((await db.scalars(stmt)).all())


async def _get_role(db: AsyncSession, role_code: str) -> Role:
    role = await db.scalar(
        select(Role).where(Role.code == role_code).options(selectinload(Role.permissions))
    )
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


async def _get_platform_assignment(
    db: AsyncSession, user_id: uuid.UUID, role_id: uuid.UUID
) -> UserRoleAssignment | None:
    return await db.scalar(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id,
            UserRoleAssignment.organization_id.is_(None),
            UserRoleAssignment.course_id.is_(None),
        )
    )


async def _assert_can_manage_role(db: AsyncSession, actor: User, role: Role) -> None:
    """Nobody can hand out (or take away) a role that carries permissions they
    don't hold themselves, so an admin can't promote anyone above their own level."""
    actor_permissions = set(await get_permission_codes(db, actor.id))
    missing = {p.code for p in role.permissions} - actor_permissions
    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot manage the {role.code} role",
        )


async def grant_role(
    db: AsyncSession, user_id: uuid.UUID, role_code: str, assigned_by: uuid.UUID | None = None
) -> None:
    """Adds a platform-wide role to a user. Does not commit or check who is asking."""
    role = await _get_role(db, role_code)
    assignment = await _get_platform_assignment(db, user_id, role.id)
    if assignment is None:
        db.add(UserRoleAssignment(user_id=user_id, role_id=role.id, assigned_by=assigned_by))
    else:
        # Re-granting revives an expired assignment.
        assignment.expires_at = None
        assignment.assigned_by = assigned_by
    await db.flush()


async def assign_role(db: AsyncSession, actor: User, user_id: uuid.UUID, role_code: str) -> None:
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    role = await _get_role(db, role_code)
    await _assert_can_manage_role(db, actor, role)
    await grant_role(db, user_id, role_code, assigned_by=actor.id)
    await db.commit()


async def revoke_role(db: AsyncSession, actor: User, user_id: uuid.UUID, role_code: str) -> None:
    role = await _get_role(db, role_code)
    await _assert_can_manage_role(db, actor, role)

    assignment = await _get_platform_assignment(db, user_id, role.id)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User does not have this role"
        )

    if role.code == SUPER_ADMIN_ROLE_CODE:
        holders = await db.scalars(
            select(UserRoleAssignment.id).where(UserRoleAssignment.role_id == role.id)
        )
        if len(holders.all()) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the last super admin",
            )

    await db.delete(assignment)
    await db.commit()
