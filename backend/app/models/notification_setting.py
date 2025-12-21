# backend/app/models/notification_setting.py
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base

class NotificationSetting(Base):
    __tablename__ = "notification_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    # デフォルトは「3時間前通知のみ」
    reminder_offsets_hours = Column(
        JSON,
        nullable=False,
        default=lambda: [3],
    )

    # 朝通知の時刻（デフォルト 08:00）
    daily_digest_time = Column(
        String,
        nullable=False,
        default="08:00",
    )

    # ✅ 朝通知の ON / OFF フラグ（デフォルト ON）
    enable_morning_notification = Column(
        Boolean,
        nullable=False,
        default=True,
    )
    
    # リレーションシップ
    user = relationship("User", back_populates="notification_setting")
