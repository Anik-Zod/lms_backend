import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class DiscussionThread(UUIDPKMixin, Base):
    __tablename__ = "discussion_threads"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("learning_contents.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="OPEN")
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)


class DiscussionPost(UUIDPKMixin, Base):
    __tablename__ = "discussion_posts"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discussion_threads.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    parent_post_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("discussion_posts.id", ondelete="SET NULL")
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_instructor_answer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PUBLISHED")

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )


class DiscussionVote(Base):
    __tablename__ = "discussion_votes"

    post_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discussion_posts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )

    vote_type: Mapped[str] = mapped_column(String(20), nullable=False)
