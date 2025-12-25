# backend/app/models/notification_run.py
from sqlalchemy import Column, Integer, DateTime, String, Index
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base

class NotificationRun(Base):
    __tablename__ = "notification_runs"

    id = Column(Integer, primary_key=True, index=True)

    run_id = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(16), nullable=False, default="running")  # running/success/partial/fail
    trigger = Column(String(32), nullable=True)  # github_actions/manual/render

    stats = Column(JSONB, nullable=True)   # 集計結果
    errors = Column(JSONB, nullable=True)  # 例外要約

    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_notif_runs_started_at", "started_at"),
    )
