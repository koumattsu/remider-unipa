from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class WebPushEvent(Base):
    __tablename__ = "webpush_events"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # "opened" だけで開始（将来: delivered/closed 等も追加可能）
    event_type = Column(String(32), nullable=False, index=True)

    # SW payload から来る識別子（無い場合もあるので nullable）
    notification_id = Column(String(128), nullable=True, index=True)
    run_id = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    user = relationship("User", backref="webpush_events")