# backend/app/schemas/in_app_notification.py

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from typing import Any, Optional

class InAppNotificationItem(BaseModel):
    id: int = Field(..., description="In-app notification id")
    run_id: Optional[int] = Field(
        default=None,
        description="notification_runs.id (cron execution id)",
        example=123,
    )
    kind: str = Field(..., description="Notification kind", example="task_reminder")
    title: str = Field(..., description="Short title shown in UI", example="1時間前")
    body: str = Field(..., description="Body text shown in UI", example="• レポート提出（2025-12-27T12:00:00+00:00）")
    deep_link: str = Field(..., description="Deep link for app navigation", example="/#/dashboard?tab=today")
    task_id: Optional[int] = Field(default=None, description="Related task id (nullable)", example=42)
    deadline_at_send: str = Field(
        ...,
        description="Task deadline copied at notification creation time (ISO8601, UTC)",
        example="2025-12-27T12:00:00+00:00",
    )
    offset_hours: int = Field(..., description="Reminder offset hours (0=morning digest)", example=1)
    created_at: str = Field(..., description="Notification created_at (ISO8601, UTC)", example="2025-12-26T15:09:07+00:00")
    dismissed_at: Optional[str] = Field(default=None, description="Dismissed time (ISO8601) or null", example=None)
    extra: Optional[Any] = Field(
        default=None,
        description="JSONB extra payload (e.g., webpush observation)",
        example={"webpush": {"status": "sent"}},
    )

class InAppNotificationListResponse(BaseModel):
    items: list[InAppNotificationItem] = Field(
        default_factory=list,
        description="In-app notifications (ordered by created_at desc in API)",
    )


class InAppRange(BaseModel):
    from_: Optional[str] = Field(default=None, alias="from", description="ISO8601 datetime (created_at) range start")
    to: Optional[str] = Field(default=None, description="ISO8601 datetime (created_at) range end")

    model_config = ConfigDict(populate_by_name=True)

class WebpushEvents(BaseModel):
    sent: int = Field(0, ge=0, description="extra.webpush.status == 'sent'")
    failed: int = Field(0, ge=0, description="extra.webpush.status == 'failed'")
    deactivated: int = Field(0, ge=0, description="extra.webpush.status == 'deactivated'")
    skipped: int = Field(0, ge=0, description="extra.webpush.status == 'skipped'")
    unknown: int = Field(0, ge=0, description="missing/unknown status (incl. null)")

class InAppNotificationSummaryResponse(BaseModel):
    range: InAppRange = Field(..., description="created_at range used for aggregation")
    total: int = Field(..., ge=0, description="Total number of in-app notifications in range")
    dismissed: int = Field(..., ge=0, description="Count of dismissed notifications in range (dismissed_at != null)")
    dismiss_rate: int = Field(..., ge=0, le=100, description="Dismissed / total * 100 (rounded). 0-100")
    webpush_events: WebpushEvents = Field(
        ...,
        description="Event-level status counts from extra.webpush.status (sent/failed/deactivated/skipped/unknown)",
    )