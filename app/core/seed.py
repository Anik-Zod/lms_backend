from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.pricing import Currency
from app.models.rbac import Permission, Role
from app.models.enums import RoleScope

PERMISSIONS = [
    ("course", "create", "course.create"),
    ("course", "read", "course.read"),
    ("course", "update", "course.update"),
    ("course", "publish", "course.publish"),
    ("course", "archive", "course.archive"),
    ("course", "manage_content", "course.manage_content"),
    ("quiz", "grade", "quiz.grade"),
    ("assignment", "grade", "assignment.grade"),
    ("enrollment", "read", "enrollment.read"),
    ("enrollment", "suspend", "enrollment.suspend"),
    ("order", "read", "order.read"),
    ("payment", "refund", "payment.refund"),
    ("review", "moderate", "review.moderate"),
    ("user", "suspend", "user.suspend"),
    ("payout", "read", "payout.read"),
]

PLATFORM_ROLES = {
    "SUPER_ADMIN": [code for *_, code in PERMISSIONS],
    "PLATFORM_ADMIN": [
        "course.update",
        "course.publish",
        "course.archive",
        "enrollment.read",
        "enrollment.suspend",
        "order.read",
        "payment.refund",
        "review.moderate",
        "user.suspend",
        "payout.read",
    ],
    "SUPPORT_AGENT": ["order.read", "enrollment.read", "user.suspend"],
    "CONTENT_MODERATOR": ["review.moderate", "course.archive"],
}


async def ensure_base_data(db: AsyncSession) -> None:
    if await db.scalar(select(Currency).where(Currency.code == "USD")) is None:
        db.add(Currency(code="USD", name="US Dollar", minor_unit=2))

    existing_permissions = {
        p.code: p for p in (await db.scalars(select(Permission))).all()
    }
    for resource, action, code in PERMISSIONS:
        if code not in existing_permissions:
            perm = Permission(resource=resource, action=action, code=code)
            db.add(perm)
            existing_permissions[code] = perm
    await db.flush()

    existing_roles = {
        r.code: r
        for r in (await db.scalars(select(Role).options(selectinload(Role.permissions)))).all()
    }
    for role_code, perm_codes in PLATFORM_ROLES.items():
        role = existing_roles.get(role_code)
        perms = [existing_permissions[c] for c in perm_codes]
        if role is None:
            role = Role(
                name=role_code.replace("_", " ").title(),
                code=role_code,
                scope_type=RoleScope.PLATFORM,
                permissions=perms,
            )
            db.add(role)
            existing_roles[role_code] = role
        else:
            role.permissions = perms

    await db.commit()
