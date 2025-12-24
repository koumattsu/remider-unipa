# backend/app/models/webpush_subscription.py

from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    DateTime,
    String,
    Boolean,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class WebPushSubscription(Base):
    __tablename__ = "webpush_subscriptions"

    __table_args__ = (
        # endpoint はブラウザ側でユニーク（subscriptionの唯一の真実）
        # ※同一端末でユーザーが切り替わる場合は API の upsert で user_id を付け替える
        UniqueConstraint("endpoint", name="uq_webpush_endpoint"),
        Index("ix_webpush_user_active", "user_id", "is_active"),
        Index("ix_webpush_user_created", "user_id", "created_at"),
        Index("ix_webpush_endpoint_active", "endpoint", "is_active"),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # PushSubscription.endpoint
    endpoint = Column(Text, nullable=False)

    # PushSubscription.keys.p256dh / auth
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)

    # 端末識別の補助情報（将来: 複数端末UI / デバッグ / M&A説明で効く）
    user_agent = Column(Text, nullable=True)
    device_label = Column(String(64), nullable=True)

    is_active = Column(Boolean, nullable=False, server_default="true")

    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User")
