# app/schemas/task_notification_override.py
from typing import Optional
from pydantic import BaseModel, ConfigDict

class TaskNotificationOverrideBase(BaseModel):
    # None = 「全体設定に従う」
    enable_morning: Optional[bool] = None
    reminder_offsets_hours: Optional[list[int]] = None

class TaskNotificationOverrideRead(TaskNotificationOverrideBase):
    task_id: int
    model_config = ConfigDict(from_attributes=True)

class TaskNotificationOverrideUpdate(TaskNotificationOverrideBase):
    pass