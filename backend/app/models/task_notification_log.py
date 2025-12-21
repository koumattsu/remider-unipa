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

    ✅ 幽霊通知対策：
    - 同じ user_id + task_id + deadline + offset_hours の組み合わせには
      一度しか通知を送らない。
    """

    __tablename__ = "task_notification_logs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "task_id",
            "deadline",
            "offset_hours",
            name="uq_task_notification_user_task_deadline_offset",
        ),
        Index(
            "ix_task_notif_user_task_deadline_offset",
            "user_id",
            "task_id",
            "deadline",
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

    # ✅ どの締切(deadline)に対する通知か（UTCで保存）
    # 最初は既存データ互換のため nullable=True にしておく（後で NOT NULL に締める）
    deadline = Column(DateTime(timezone=True), nullable=True, index=True)

    # 何時間前の通知か
    offset_hours = Column(Integer, nullable=False)

    # いつ送ったか
    sent_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="notification_logs")
    task = relationship("Task", back_populates="notification_logs")
