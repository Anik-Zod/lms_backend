import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class CertificateTemplate(UUIDPKMixin, Base):
    __tablename__ = "certificate_templates"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    template_uri: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ACTIVE")

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class CertificateIssuance(UUIDPKMixin, Base):
    __tablename__ = "certificate_issuances"

    certificate_number: Mapped[str] = mapped_column(String(60), nullable=False)
    verification_code: Mapped[str] = mapped_column(String(60), nullable=False)

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("certificate_templates.id", ondelete="RESTRICT"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    issued_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    expires_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]

    pdf_media_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("certificate_number", name="uq_certificate_number"),
        UniqueConstraint("verification_code", name="uq_certificate_verification_code"),
    )
