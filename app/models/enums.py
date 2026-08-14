import enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Native PostgreSQL ENUM bound to a Python str-enum, stored by .value."""
    return SAEnum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEACTIVATED = "DEACTIVATED"
    DELETION_REQUESTED = "DELETION_REQUESTED"
    ANONYMIZED = "ANONYMIZED"


class CourseStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class CourseVisibility(str, enum.Enum):
    PUBLIC = "PUBLIC"
    UNLISTED = "UNLISTED"
    PRIVATE = "PRIVATE"


class CourseLevel(str, enum.Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    ALL_LEVELS = "ALL_LEVELS"


class ContentType(str, enum.Enum):
    VIDEO = "VIDEO"
    ARTICLE = "ARTICLE"
    RESOURCE = "RESOURCE"
    QUIZ = "QUIZ"
    ASSIGNMENT = "ASSIGNMENT"


class ContentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"


class EnrollmentSource(str, enum.Enum):
    FREE = "FREE"
    PURCHASE = "PURCHASE"
    COUPON = "COUPON"
    INVITATION = "INVITATION"
    ADMIN = "ADMIN"
    SUBSCRIPTION = "SUBSCRIPTION"
    BUNDLE = "BUNDLE"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


class RoleScope(str, enum.Enum):
    PLATFORM = "PLATFORM"
    ORGANIZATION = "ORGANIZATION"
    COURSE = "COURSE"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
