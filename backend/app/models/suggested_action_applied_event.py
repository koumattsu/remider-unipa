# backend/app/models/suggested_action_applied_event.py

from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Index, JSON
from sqlalchemy.sql import func
from app.db.base import Base

class SuggestedActionAppliedEvent(Base):
    """
    提案（SuggestedAction）をユーザーが適用した事実を保存する（資産）
    - OutcomeLog は真実（SSOT）
    - これは「人間が何をしたか」の監査資産（read/write）
    """
    __tablename__ = "suggested_action_applied_events"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # フロント側の action_id（例: "reduce-missed-course:xxxx" みたいな識別子でもOK）
    action_id = Column(String(128), nullable=False, index=True)

    # 週 / 月（フロントの bucket と揃える）
    bucket = Column(String(16), nullable=False, index=True)  # "week" | "month"

    # 適用時刻（UTCで保存）
    applied_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # 何を変更したか（TaskUpdate payload など。将来進化OK）
    payload = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_action_applied_user_action_appliedat", "user_id", "action_id", "applied_at"),
    )
