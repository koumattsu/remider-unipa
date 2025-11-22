# app/models/task_notification_log.py

from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class TaskNotificationLog(Base):
    """
    タスクごとの通知履歴を残すテーブル。

    - 同じ user_id + task_id + offset_hours の組み合わせには
      一度しか通知を送らないようにするためのログ。
    """

    __tablename__ = "task_notification_logs"
    __table_args__ = (
        # 同じユーザー・同じタスク・同じオフセット（何時間前）は一度だけ
        UniqueConstraint(
            "user_id",
            "task_id",
            "offset_hours",
            name="uq_task_notification_user_task_offset",
        ),
        Index(
            "ix_task_notif_user_task_offset",
            "user_id",
            "task_id",
            "offset_hours",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id = Column(
        Integer,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 何時間前の通知か
    # 例: 24, 3, 1, 0（当日朝）, など
    offset_hours = Column(Integer, nullable=False)

    # いつ送ったか
    sent_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # リレーション
    user = relationship("User", back_populates="notification_logs")
    task = relationship("Task", back_populates="notification_logs")
