# backend/app/models/action_effectiveness_snapshot.py

from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Float, Index
from sqlalchemy.sql import func
from app.db.base import Base

class ActionEffectivenessSnapshot(Base):
    """
    ActionEffectiveness のスナップショット（資産）
    - OutcomeLog（SSOT）から算出した read-only 集計結果を「履歴」として保存
    - M&A/監査/改善の証跡として残す
    """
    __tablename__ = "action_effectiveness_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    bucket = Column(String(16), nullable=False, index=True)  # "week" | "month"（現状は保存メタとして）

    # 集計条件（将来、条件が変わっても意味が残るように保存）
    window_days = Column(Integer, nullable=False)
    min_total = Column(Integer, nullable=False)
    limit_events = Column(Integer, nullable=False)

    # 集計対象
    action_id = Column(String(128), nullable=False, index=True)

    applied_count = Column(Integer, nullable=False)
    measured_count = Column(Integer, nullable=False)
    improved_count = Column(Integer, nullable=False)

    improved_rate = Column(Float, nullable=False)
    avg_delta_missed_rate = Column(Float, nullable=False)

    captured_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("ix_action_eff_snap_user_captured", "user_id", "captured_at"),
        Index("ix_action_eff_snap_user_action_captured", "user_id", "action_id", "captured_at"),
    )
