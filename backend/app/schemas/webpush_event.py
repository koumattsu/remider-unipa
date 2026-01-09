# backend/app/schemas/webpush_event.py

from pydantic import BaseModel
from typing import Optional, Literal

class WebPushEventCreate(BaseModel):
    type: Literal["opened"]
    notification_id: Optional[int] = None
    run_id: Optional[int] = None
    opened_at: Optional[str] = None  # 受け取るだけ（保存は created_at を正にする）

class WebPushEventResponse(BaseModel):
    id: int
    event_type: str
    notification_id: Optional[str]
    run_id: Optional[int]

    class Config:
        from_attributes = True