# backend/app/db/base.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# SQLite用の設定（PostgreSQLに移行しやすいようURLを設定から取得）
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    """データベースを初期化（テーブル作成）"""
    # ✅ ここで models を import して Base.metadata に登録させる
    # （import しないと create_all に含まれず、テーブルが作られない）
    from app.models.user import User  # noqa: F401
    from app.models.task import Task  # noqa: F401
    from app.models.weekly_task import WeeklyTask  # noqa: F401
    from app.models.notification_setting import NotificationSetting  # noqa: F401
    from app.models.task_notification_log import TaskNotificationLog  # noqa: F401
    from app.models.task_outcome_log import TaskOutcomeLog  # noqa: F401  # ★今回追加
    from app.models.in_app_notification import InAppNotification  # noqa: F401  # ★in-app通知
    from app.models.webpush_subscription import WebPushSubscription  # noqa: F401
    
    Base.metadata.create_all(bind=engine)

