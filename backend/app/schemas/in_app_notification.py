# backend/app/schemas/in_app_notification.py

from pydantic import BaseModel, Field
from typing import Any, Optional


class InAppNotificationItem(BaseModel):
    id: int
    run_id: Optional[int] = None
    kind: str
    title: str
    body: str
    deep_link: str
    task_id: Optional[int] = None
    deadline_at_send: str
    offset_hours: int
    created_at: str
    dismissed_at: Optional[str] = None
    extra: Optional[Any] = None


class InAppNotificationListResponse(BaseModel):
    items: list[InAppNotificationItem]


class InAppRange(BaseModel):
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None

    class Config:
        populate_by_name = True


class WebpushEvents(BaseModel):
    sent: int = 0
    failed: int = 0
    deactivated: int = 0
    skipped: int = 0
    unknown: int = 0


class InAppNotificationSummaryResponse(BaseModel):
    range: InAppRange
    total: int
    dismissed: int
    dismiss_rate: int  # 0-100
    webpush_events: WebpushEvents
