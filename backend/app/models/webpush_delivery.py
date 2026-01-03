# backend/app/models/webpush_delivery.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base import Base

class WebPushDelivery(Base):
    """
    WebPush 配信試行の最終SSOT（attemptログ）
    - InAppNotification に紐づく外部配信の事実
    - 監査/M&A耐性のため正規化
    """
    __tablename__ = "webpush_deliveries"

    # ✅ 監査で説明できる正規 status（契約）
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_DEACTIVATED = "deactivated"
    STATUS_SKIPPED = "skipped"
    STATUS_UNKNOWN = "unknown"

    STATUS_SET = {
        STATUS_SENT,
        STATUS_FAILED,
        STATUS_DEACTIVATED,
        STATUS_SKIPPED,
        STATUS_UNKNOWN,
    }

    id = Column(Integer, primary_key=True)

    # 監査の軸
    run_id = Column(Integer, ForeignKey("notification_runs.id"), nullable=True, index=True)
    in_app_notification_id = Column(
        Integer, ForeignKey("in_app_notifications.id"), nullable=False, index=True
    )
    user_id = Column(Integer, nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("webpush_subscriptions.id"), nullable=False, index=True)

    # 結果
    status = Column(String(16), nullable=False)  # sent/failed/deactivated/skipped/unknown
    http_status = Column(Integer, nullable=True)
    error_summary = Column(String(255), nullable=True)

    attempted_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "in_app_notification_id",
            "subscription_id",
            name="uq_webpush_delivery_run_notif_sub",
        ),
    )
