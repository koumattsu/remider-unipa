# backend/app/models/task.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base

from app.models.task_notification_override import TaskNotificationOverride
from app.models.weekly_task import WeeklyTask

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # ユーザーごとの締切順ソート用 Index（元のまま）
        Index("ix_tasks_user_deadline", "user_id", "deadline"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    course_name = Column(String(255), nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=False, index=True)
    memo = Column(Text, nullable=True)
    is_done = Column(Boolean, default=False, nullable=False)
    should_notify = Column(Boolean, nullable=False, default=True)
    weekly_task_id = Column(Integer, ForeignKey("weekly_tasks.id"), nullable=True, index=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # リレーションシップ
    user = relationship("User", back_populates="tasks")
    
    # 🔔 通知ログ
    notification_logs = relationship(
        "TaskNotificationLog",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    # 👇 1:1 のタスク別通知設定（すでにある想定）
    notification_override = relationship(
        "TaskNotificationOverride",
        back_populates="task",
        uselist=False,
    )

    weekly_task = relationship("WeeklyTask", back_populates="generated_tasks")
