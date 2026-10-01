import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.identity import User
from app.schemas.admin import AdminUserOut, RoleAssignRequest, RoleOut
from app.services import rbac_service

router = APIRouter(prefix="/admin", tags=["admin"])


async def _to_admin_user(db: AsyncSession, user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        created_at=user.created_at,
        roles=await rbac_service.get_role_codes(db, user.id),
    )


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    _: User = Depends(require_permission("role.assign")),
    db: AsyncSession = Depends(get_db),
):
    return [
        RoleOut(
            code=role.code,
            name=role.name,
            description=role.description,
            permissions=sorted(p.code for p in role.permissions),
        )
        for role in await rbac_service.list_roles(db)
    ]


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    search: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission("user.read")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.deleted_at.is_(None))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(User.email.ilike(pattern), User.display_name.ilike(pattern)))
    stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)

    users = (await db.scalars(stmt)).all()
    return [await _to_admin_user(db, user) for user in users]


@router.post("/users/{user_id}/roles", response_model=AdminUserOut)
async def assign_role(
    user_id: uuid.UUID,
    payload: RoleAssignRequest,
    current_user: User = Depends(require_permission("role.assign")),
    db: AsyncSession = Depends(get_db),
):
    await rbac_service.assign_role(db, current_user, user_id, payload.role_code)
    return await _to_admin_user(db, await db.get(User, user_id))


@router.delete("/users/{user_id}/roles/{role_code}", response_model=AdminUserOut)
async def revoke_role(
    user_id: uuid.UUID,
    role_code: str,
    current_user: User = Depends(require_permission("role.assign")),
    db: AsyncSession = Depends(get_db),
):
    await rbac_service.revoke_role(db, current_user, user_id, role_code)
    return await _to_admin_user(db, await db.get(User, user_id))
