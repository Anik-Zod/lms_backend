from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import User, UserProfile
from app.schemas.user import UserProfileOut, UserProfileUpdate

PROFILE_FIELDS = (
    "first_name",
    "last_name",
    "bio",
    "headline",
    "country_code",
    "timezone",
    "website_url",
    "language",
    "facebook_url",
    "instagram_url",
    "linkedin_url",
    "tiktok_url",
    "twitter_url",
    "youtube_url",
)


def _merge(user: User, profile: UserProfile | None) -> UserProfileOut:
    profile_data = {field: getattr(profile, field) for field in PROFILE_FIELDS} if profile else {}
    return UserProfileOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        created_at=user.created_at,
        **profile_data,
    )


async def get_profile(db: AsyncSession, user: User) -> UserProfileOut:
    profile = await db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    return _merge(user, profile)


async def update_profile(db: AsyncSession, user: User, data: UserProfileUpdate) -> UserProfileOut:
    profile = await db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)

    # Keep the account's display name in sync when the user edits their name.
    if "first_name" in updates or "last_name" in updates:
        full_name = " ".join(part for part in (profile.first_name, profile.last_name) if part)
        if full_name:
            user.display_name = full_name

    await db.commit()
    await db.refresh(profile)
    await db.refresh(user)
    return _merge(user, profile)
