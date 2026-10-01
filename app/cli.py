"""Maintenance commands.

    python -m app.cli grant-role <email> <ROLE_CODE>

Use this to create the first super admin; after that, roles are managed
through the /admin API.
"""

import asyncio
import sys

from sqlalchemy import select

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


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == "grant-role":
        asyncio.run(grant_role(sys.argv[2], sys.argv[3].upper()))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
