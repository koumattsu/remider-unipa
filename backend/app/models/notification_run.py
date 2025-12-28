# backend/app/models/notification_run.py
from sqlalchemy import Column, Integer, DateTime, String, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base, is_sqlite

class NotificationRun(Base):
    """
    cron 実行 1回 = 1行
    M&A耐性:
    - 「通知が来た/来ない」をサーバ側の事実として追える
    - 例外時も status/error_summary が残る
    """
    __tablename__ = "notification_runs"

    id = Column(Integer, primary_key=True, index=True)

    status = Column(
        String(16),
        nullable=False,
        default="running",  # running/success/partial/fail
        index=True,
    )

    error_summary = Column(Text, nullable=True)
    users_processed = Column(Integer, nullable=False, default=0)
    due_candidates_total = Column(Integer, nullable=False, default=0)
    morning_candidates_total = Column(Integer, nullable=False, default=0)
    inapp_created = Column(Integer, nullable=False, default=0)
    webpush_sent = Column(Integer, nullable=False, default=0)
    webpush_failed = Column(Integer, nullable=False, default=0)
    webpush_deactivated = Column(Integer, nullable=False, default=0)
    line_sent = Column(Integer, nullable=False, default=0)
    line_failed = Column(Integer, nullable=False, default=0)
    started_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    # 監査/再現用スナップショット
    # - Postgres: JSONB
    # - SQLite(テスト/ローカル): JSON（JSONBがcompileできないため）
    stats = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True, index=True)