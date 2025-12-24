# backend/app/models/task_outcome_log.py

from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    DateTime,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class TaskOutcomeLog(Base):
    """
    タスクの「締切到達時点」の結果を保存するテーブル。

    ✅ 分析の唯一の真実：
    - 締切（deadline）に対して「その時点で完了していたか」を1回だけ確定保存する
    - 締切後の完了/締切延長/復活があっても、このログは不変
    """

    __tablename__ = "task_outcome_logs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "task_id",
            "deadline",
            name="uq_task_outcome_user_task_deadline",
        ),
        Index(
            "ix_task_outcome_user_task_deadline",
            "user_id",
            "task_id",
            "deadline",
        ),
        Index(
            "ix_task_outcome_user_deadline",
            "user_id",
            "deadline",
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

    # 評価対象の締切（UTC想定。tasks.deadlineの値をコピーして固定保存）
    deadline = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="evaluated deadline (copied from tasks.deadline at evaluation time, UTC)",
    )

    # 'done' | 'missed'
    outcome = Column(
        String(16),
        nullable=False,
        index=True,
        comment="done if completed_at <= deadline else missed",
    )

    # 評価した時刻（UTC）
    evaluated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="when this outcome was evaluated (UTC)",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="outcome_logs")
    task = relationship("Task", back_populates="outcome_logs")