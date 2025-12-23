# backend/app/models/user.py

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db.base import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    line_user_id = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    university = Column(String, nullable=True)
    plan = Column(String, default="free")  # "free", "basic", "pro"
    
    # リレーションシップ
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    notification_setting = relationship("NotificationSetting", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notification_logs = relationship("TaskNotificationLog",back_populates="user",cascade="all, delete-orphan")