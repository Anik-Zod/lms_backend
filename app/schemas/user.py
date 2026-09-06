import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    status: str
    created_at: datetime

    first_name: str | None = None
    last_name: str | None = None
    bio: str | None = None
    headline: str | None = None
    country_code: str | None = None
    timezone: str | None = None
    website_url: str | None = None
    language: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    linkedin_url: str | None = None
    tiktok_url: str | None = None
    twitter_url: str | None = None
    youtube_url: str | None = None


class UserProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    bio: str | None = None
    headline: str | None = Field(default=None, max_length=255)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    timezone: str | None = Field(default=None, max_length=64)
    website_url: str | None = None
    language: str | None = Field(default=None, max_length=30)
    facebook_url: str | None = None
    instagram_url: str | None = None
    linkedin_url: str | None = None
    tiktok_url: str | None = None
    twitter_url: str | None = None
    youtube_url: str | None = None
