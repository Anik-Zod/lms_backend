"""Maintenance commands.

    python -m app.cli create-admin <email> <password> [display_name]
    python -m app.cli grant-role <email> <ROLE_CODE>

Use create-admin to make the first super admin on a fresh install; after that,
roles are managed through the /admin API.
"""

import asyncio
import sys

from sqlalchemy import select

from app.core import seed
from app.core.database import AsyncSessionLocal
from app.core.seed import ensure_base_data
from app.models.identity import User
from app.services import rbac_service


async def grant_role(email: str, role_code: str) -> None:
    async with AsyncSessionLocal() as db:
        await ensure_base_data(db)
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            sys.exit(f"No user with email {email}. Register the account first.")
        await rbac_service.grant_role(db, user.id, role_code)
        await db.commit()
        print(f"Granted {role_code} to {email}")


async def create_admin(email: str, password: str, display_name: str) -> None:
    if len(password) < 8:
        sys.exit("Password must be at least 8 characters.")
    async with AsyncSessionLocal() as db:
        await ensure_base_data(db)
        if await seed.create_admin(db, email, password, display_name):
            print(f"Created account {email}")
        else:
            print(f"Account {email} already exists; password left unchanged")
        print(f"Granted {rbac_service.SUPER_ADMIN_ROLE_CODE} to {email}")


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "grant-role":
        asyncio.run(grant_role(args[1], args[2].upper()))
    elif len(args) in (3, 4) and args[0] == "create-admin":
        display_name = args[3] if len(args) == 4 else args[1].split("@")[0]
        asyncio.run(create_admin(args[1], args[2], display_name))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
