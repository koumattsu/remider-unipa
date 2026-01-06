# backend/app/models/in_app_notification.py

from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    DateTime,
    String,
    Text,
    UniqueConstraint,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base

class InAppNotification(Base):
    __tablename__ = "in_app_notifications"

    run_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="notification_runs.id (cron execution)",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "task_id",
            "deadline_at_send",
            "offset_hours",
            "channel",
            name="uq_inapp_user_task_deadline_offset",
        ),

        Index(
            "ix_inapp_user_active_created",
            "user_id",
            "dismissed_at",
            "created_at",
        ),
        Index(
            "ix_inapp_user_task",
            "user_id",
            "task_id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    # ✅ 通知チャネル（反応率の集計をWeb Pushだけに絞るため）
    # 既存データ互換のため default は "in_app"
    channel = Column(String(32), nullable=False, default="in_app", index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    task_id = Column(
        Integer,
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    deadline_at_send = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="deadline at the moment notification was created (copied from tasks.deadline, UTC)",
    )

    offset_hours = Column(Integer, nullable=False)

    kind = Column(String(32), nullable=False, default="task_reminder")
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    deep_link = Column(String(512), nullable=False)

    extra = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    dismissed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    user = relationship("User", overlaps="in_app_notifications")
    task = relationship("Task")