import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), primary_key=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
