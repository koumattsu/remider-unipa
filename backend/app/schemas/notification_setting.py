from pydantic import BaseModel, Field
from typing import List


class NotificationSettingBase(BaseModel):
    reminder_offsets_hours: List[int] = Field(default=[24, 3, 1], description="締切何時間前に通知するか")
    daily_digest_time: str = Field(default="08:00", description="日次ダイジェスト送信時間 (HH:MM)")


class NotificationSettingCreate(NotificationSettingBase):
    pass


class NotificationSettingUpdate(NotificationSettingBase):
    pass


class NotificationSettingResponse(NotificationSettingBase):
    id: int
    user_id: int
    
    class Config:
        from_attributes = True

