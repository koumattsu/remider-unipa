from fastapi import APIRouter
from app.api.v1.endpoints import auth, tasks, settings, cron  # ← cron を追加

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(cron.router, prefix="/cron", tags=["cron"])  # ← これ追加
