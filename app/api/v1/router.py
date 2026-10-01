from fastapi import APIRouter

from app.api.v1 import (
    admin,
    assessments,
    auth,
    commerce,
    contents,
    courses,
    enrollments,
    progress,
    teaching,
    users,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(courses.router)
api_router.include_router(contents.router)
api_router.include_router(assessments.router)
api_router.include_router(teaching.router)
api_router.include_router(enrollments.router)
api_router.include_router(commerce.router)
api_router.include_router(progress.router)
api_router.include_router(admin.router)
