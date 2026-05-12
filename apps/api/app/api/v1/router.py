from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    feedback,
    memberships,
    notifications,
    profiles,
    public,
    records,
    uploads,
)

api_router = APIRouter(prefix='/api/v1')
api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(records.router)
api_router.include_router(memberships.router)
api_router.include_router(notifications.router)
api_router.include_router(feedback.router)
api_router.include_router(public.router)
api_router.include_router(admin.router)
api_router.include_router(uploads.router)
