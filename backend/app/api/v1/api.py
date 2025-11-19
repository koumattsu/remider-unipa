from fastapi import APIRouter
from app.api.v1.endpoints import auth, tasks, settings

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["認証"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["課題"])
api_router.include_router(settings.router, prefix="/settings", tags=["設定"])

