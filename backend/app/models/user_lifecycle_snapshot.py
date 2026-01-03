# backend/app/models/user_lifecycle_snapshot.py

from sqlalchemy import Column, Integer, DateTime, Float, Boolean, Index, Date
from sqlalchemy.sql import func
from app.db.base import Base

class UserLifecycleSnapshot(Base):
    """
    User Lifecycle Snapshot（M&A/DD用の資産）
    - captured_at 時点のユーザ状態を固定保存
    - 後から export/再集計可能な “履歴資産”
    """
    __tablename__ = "user_lifecycle_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, nullable=False, index=True)

    captured_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # ✅ 重複防止用（日単位・JST 기준）
    captured_day = Column(Date, nullable=False, index=True)

    registered_at = Column(DateTime(timezone=True), nullable=True, index=True)

    first_task_created_at = Column(DateTime(timezone=True), nullable=True, index=True)
    first_task_completed_at = Column(DateTime(timezone=True), nullable=True, index=True)

    last_active_at = Column(DateTime(timezone=True), nullable=True, index=True)

    tasks_total = Column(Integer, nullable=False, default=0)
    completed_total = Column(Integer, nullable=False, default=0)

    done_rate = Column(Float, nullable=False, default=0.0)

    active_7d = Column(Boolean, nullable=False, default=False)
    active_30d = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_user_lifecycle_user_captured", "user_id", "captured_at"),
        Index(
            "uq_user_lifecycle_user_day",
            "user_id",
            "captured_day",
            unique=True,
        ),
    )
