from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+asyncpg://lms:lms@localhost:5433/lms"

    redis_url: str = "redis://localhost:6380/0"

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    password_reset_token_expire_minutes: int = 30

    cors_origins: list[str] = ["http://localhost:3000"]
    cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1):\d+$"
    frontend_base_url: str = "http://localhost:3000"

    # When both are set and no super admin exists yet, startup creates this account
    # (or promotes it if already registered). Ignored once a super admin exists.
    admin_email: str | None = None
    admin_password: str | None = Field(default=None, min_length=8, max_length=128)

    # Uploaded lesson files go to an S3-compatible bucket ("s3", the docker-compose
    # storage service by default) or to media_root on local disk ("local"). Either
    # way they are served through signed URLs.
    storage_provider: Literal["s3", "local"] = "s3"
    # Browsers follow presigned links to this address, so it must be reachable by them.
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "lmsaccess"
    s3_secret_key: str = "lmssecret123"
    s3_bucket: str = "lms-media"
    s3_region: str = "us-east-1"
    media_root: str = "media"
    media_max_upload_mb: int = 1024
    media_url_expire_minutes: int = 360


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
