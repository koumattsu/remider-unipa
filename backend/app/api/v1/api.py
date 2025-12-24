# backend/app/api/v1/api.py

from fastapi import APIRouter
from app.api.v1.endpoints import auth, tasks, settings, cron, admin_migrate, weekly_tasks, task_notification_override, outcomes, in_app_notifications, webpush_subscriptions

api_router = APIRouter()

# 既存ルーター
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(cron.router, prefix="/cron", tags=["cron"])
api_router.include_router(admin_migrate.router,prefix="/admin",tags=["admin"],)
api_router.include_router(outcomes.router, prefix="/outcomes", tags=["outcomes"])
api_router.include_router(
    in_app_notifications.router,
    prefix="/notifications",
    tags=["notifications"],
)

# Web Push 購読（端末資産）
api_router.include_router(
    webpush_subscriptions.router,
    prefix="/notifications/webpush",
    tags=["notifications"],
)

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