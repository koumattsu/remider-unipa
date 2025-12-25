# backend/app/models/__init__.py
# ✅ Base.metadata に全モデルを登録するための集約import
from app.models.user import User  # noqa: F401
from app.models.task import Task  # noqa: F401
from app.models.weekly_task import WeeklyTask  # noqa: F401
from app.models.notification_setting import NotificationSetting  # noqa: F401
from app.models.task_notification_log import TaskNotificationLog  # noqa: F401
from app.models.task_outcome_log import TaskOutcomeLog  # noqa: F401
from app.models.in_app_notification import InAppNotification  # noqa: F401
from app.models.webpush_subscription import WebPushSubscription  # noqa: F401
