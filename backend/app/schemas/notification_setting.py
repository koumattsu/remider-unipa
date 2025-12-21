# backend/app/schemas/notification_setting.py
from pydantic import BaseModel, Field
from typing import List

class NotificationSettingBase(BaseModel):
    # デフォルトは 3時間前のみ
    reminder_offsets_hours: List[int] = Field(
        default=[3],
        description="締切何時間前に通知するか（1時間刻みで自由に設定可能）",
    )
    daily_digest_time: str = Field(
        default="08:00",
        description="日次ダイジェスト送信時間 (HH:MM)",
    )
    # ✅ 朝通知 ON/OFF
    enable_morning_notification: bool = Field(
        default=True,
        description="朝のダイジェスト通知を送るかどうか",
    )

class NotificationSettingCreate(NotificationSettingBase):
    pass

class NotificationSettingUpdate(NotificationSettingBase):
    pass

class NotificationSettingResponse(NotificationSettingBase):
    id: int
    user_id: int
    
    class Config:
        from_attributes = True
