# backend/app/schemas/webpush_event.py

from pydantic import BaseModel
from typing import Optional, Literal

class WebPushEventCreate(BaseModel):
    type: Literal["opened"]
    notification_id: Optional[int] = None
    run_id: Optional[int] = None
    opened_at: Optional[str] = None 
    event_token: Optional[str] = None

class WebPushEventResponse(BaseModel):
    id: int
    event_type: str
    notification_id: Optional[str]
    run_id: Optional[int]

    class Config:
        from_attributes = True