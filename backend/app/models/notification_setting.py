from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base


class NotificationSetting(Base):
    __tablename__ = "notification_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    reminder_offsets_hours = Column(JSON, nullable=False, default=[24, 3, 1])  # 締切何時間前に通知するか [24, 3, 1]
    daily_digest_time = Column(String, nullable=False, default="08:00")  # "HH:MM" 形式
    
    # リレーションシップ
    user = relationship("User", back_populates="notification_setting")

