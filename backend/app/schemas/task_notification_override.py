# app/schemas/task_notification_override.py
from typing import Optional, List
from pydantic import BaseModel

class TaskNotificationOverrideBase(BaseModel):
    # None = 「全体設定に従う」
    enable_morning: Optional[bool] = None
    reminder_offsets_hours: Optional[List[int]] = None

class TaskNotificationOverrideRead(TaskNotificationOverrideBase):
    task_id: int

    # ✅ Pydantic v1 で ORM から読む用
    class Config:
        orm_mode = True

class TaskNotificationOverrideUpdate(TaskNotificationOverrideBase):
    pass