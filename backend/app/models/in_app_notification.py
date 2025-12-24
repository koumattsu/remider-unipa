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
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base

class InAppNotification(Base):
    __tablename__ = "in_app_notifications"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "task_id",
            "deadline_at_send",
            "offset_hours",
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

    extra = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    dismissed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    user = relationship("User")
    task = relationship("Task")
