# app/models/task_notification_override.py
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from app.db.base import Base

class TaskNotificationOverride(Base):
    __tablename__ = "task_notification_overrides"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(
        Integer,
        ForeignKey("tasks.id", ondelete="CASCADE"),  # ★ここが重要
        unique=True,
        nullable=False,
        index=True,
    )


    # None = 「全体設定に従う」
    enable_morning = Column(Boolean, nullable=True)

    # None = 「全体設定に従う」
    # 例: [1, 2, 3] なら「1h前, 2h前, 3h前」
    reminder_offsets_hours = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    task = relationship("Task", back_populates="notification_override")