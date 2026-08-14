from app.models.base import Base

from app.models import (  # noqa: F401  (import for side-effect: table registration)
    assessments,
    assignments,
    audit,
    certificates,
    commerce,
    content,
    coupons,
    courses,
    discussions,
    enrollment,
    identity,
    instructor,
    media,
    moderation,
    notifications,
    organizations,
    pricing,
    progress,
    rbac,
    revenue,
    reviews,
    taxonomy,
    wishlist,
)

__all__ = ["Base"]
