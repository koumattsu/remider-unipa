# backend/app/schemas/webpush_subscription.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class WebPushKeys(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)

class WebPushSubscriptionCreate(BaseModel):
    endpoint: str = Field(min_length=1)
    keys: WebPushKeys
    user_agent: Optional[str] = None
    device_label: Optional[str] = Field(default=None, max_length=64)

class WebPushSubscriptionResponse(BaseModel):
    id: int
    endpoint: str
    is_active: bool
    device_label: Optional[str] = None
    created_at: datetime
    last_seen_at: Optional[datetime] = None

    class Config:
        from_attributes = True
