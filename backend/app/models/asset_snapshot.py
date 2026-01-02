# backend/app/models/asset_snapshot.py

from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.sql import func
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base

class AssetSnapshot(Base):
    """
    資産スナップショット（M&A/監査用）
    - 「資産が増えている証拠」を時系列で固定保存する
    - 主要カウントはカラムで保持（集計/表示/輸出しやすい）
    - 追加情報は stats(JSON) にバージョン付きで格納
    """
    __tablename__ = "asset_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    kind = Column(String(32), nullable=False, default="global", index=True)  # global | user
    user_id = Column(Integer, nullable=True, index=True)

    users = Column(Integer, nullable=False, default=0)
    tasks = Column(Integer, nullable=False, default=0)
    completed_tasks = Column(Integer, nullable=False, default=0)
    notification_runs = Column(Integer, nullable=False, default=0)
    in_app_notifications = Column(Integer, nullable=False, default=0)
    outcome_logs = Column(Integer, nullable=False, default=0)
    action_applied_events = Column(Integer, nullable=False, default=0)

    # 監査/再現用スナップショット（NotificationRunと同じ運用方針）
    stats = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
