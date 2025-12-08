from fastapi import APIRouter
from app.api.v1.endpoints import auth, tasks, settings, cron
from app.api.v1.endpoints import weekly_tasks  
from app.api.v1.endpoints import task_notification_override


api_router = APIRouter()

# 既存ルーター
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(cron.router, prefix="/cron", tags=["cron"])

# 毎週タスク用ルーター
api_router.include_router(
    weekly_tasks.router,
    prefix="/weekly-tasks",
    tags=["weekly_tasks"],
)

# 🔔 タスクごとの通知オーバーライド用ルーター
api_router.include_router(
    task_notification_override.router,
    prefix="/tasks",
    tags=["task_notification_override"],
)