from fastapi import APIRouter

from app.api.v1 import auth, commerce, courses, enrollments, progress

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(courses.router)
api_router.include_router(enrollments.router)
api_router.include_router(commerce.router)
api_router.include_router(progress.router)
