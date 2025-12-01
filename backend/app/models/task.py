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
    UniqueConstraint,  # 👈 追加
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # ユーザーごとの締切順ソート用 Index（元のまま）
        Index("ix_tasks_user_deadline", "user_id", "deadline"),
        # 「同じユーザー・同じ授業・同じタイトル」は1件にするユニーク制約 👇
        UniqueConstraint(
            "user_id",
            "course_name",
            "title",
            name="uq_tasks_user_course_title",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    course_name = Column(String(255), nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=False, index=True)
    memo = Column(Text, nullable=True)
    is_done = Column(Boolean, default=False, nullable=False)
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
    notification_logs = relationship("TaskNotificationLog",back_populates="task",cascade="all, delete-orphan")