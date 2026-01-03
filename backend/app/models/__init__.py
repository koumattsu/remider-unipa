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
from app.models.notification_run import NotificationRun  # noqa: F401
from app.models.webpush_delivery import WebPushDelivery  # noqa: F401
from app.models.outcome_feature_snapshot import OutcomeFeatureSnapshot  # noqa: F401
from app.models.suggested_action_applied_event import SuggestedActionAppliedEvent  # noqa: F401
from app.models.action_effectiveness_snapshot import ActionEffectivenessSnapshot  # noqa: F401
from app.models.user_lifecycle_snapshot import UserLifecycleSnapshot  # noqa: F401