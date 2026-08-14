import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class MediaAsset(UUIDPKMixin, Base):
    __tablename__ = "media_assets"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE")
    )
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="CASCADE")
    )

    storage_provider: Mapped[str] = mapped_column(String(30), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum: Mapped[str | None] = mapped_column(String(128))

    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="PENDING")

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    __table_args__ = (
        Index("ix_media_assets_owner", "owner_user_id"),
        Index("ix_media_assets_course", "course_id"),
        Index("ix_media_assets_content", "content_id"),
    )


class MediaVariant(UUIDPKMixin, Base):
    __tablename__ = "media_variants"

    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )

    variant_type: Mapped[str] = mapped_column(String(30), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="PENDING")
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
