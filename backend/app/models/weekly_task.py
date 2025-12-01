# backend/app/models/weekly_task.py

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base   # ✅ ここを修正
from app.models.user import User


class WeeklyTask(Base):
    __tablename__ = "weekly_tasks"

    id = Column(Integer, primary_key=True, index=True)

    # このテンプレートを持っているユーザー
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship(User, backref="weekly_tasks")

    # 表示用の情報
    title = Column(String, nullable=False)
    course_name = Column(String, nullable=True)
    memo = Column(String, nullable=True)

    # 0=月曜, 1=火曜, ... 6=日曜
    weekday = Column(Integer, nullable=False)

    # 例: 24:00 表示 → 0:00 保存
    time_hour = Column(Integer, nullable=False, default=0)
    time_minute = Column(Integer, nullable=False, default=0)

    # 有効/無効
    is_active = Column(Boolean, nullable=False, default=True)
