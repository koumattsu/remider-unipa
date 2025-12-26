#backend/app/api/v1/endpoints/in_app_notifications.py

from datetime import datetime, timezone
from sqlalchemy import func
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.schemas.in_app_notification import (
    InAppNotificationListResponse,
    InAppNotificationSummaryResponse,
)
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.in_app_notification import InAppNotification

router = APIRouter()

@router.get("/in-app", response_model=InAppNotificationListResponse)
async def list_in_app_notifications(
    limit: int = Query(20, ge=1, le=100),
    include_dismissed: bool = Query(False),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(InAppNotification)
        .filter(InAppNotification.user_id == current_user.id)
    )

    if from_:
        q = q.filter(InAppNotification.created_at >= from_)
    if to:
        q = q.filter(InAppNotification.created_at <= to)

    if not include_dismissed:
        q = q.filter(InAppNotification.dismissed_at.is_(None))

    items = (
        q.order_by(InAppNotification.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": n.id,
                "run_id": n.run_id,
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "deep_link": n.deep_link,
                "task_id": n.task_id,
                "deadline_at_send": n.deadline_at_send.isoformat(),
                "offset_hours": n.offset_hours,
                "created_at": n.created_at.isoformat(),
                "dismissed_at": n.dismissed_at.isoformat() if n.dismissed_at else None,
                "extra": n.extra,
            }
            for n in items
        ]
    }

@router.post("/in-app/{notification_id}/dismiss")
async def dismiss_in_app_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = (
        db.query(InAppNotification)
        .filter(InAppNotification.id == notification_id)
        .filter(InAppNotification.user_id == current_user.id)
        .first()
    )
    if not n:
        raise HTTPException(status_code=404, detail="not found")

    if n.dismissed_at is None:
        n.dismissed_at = datetime.now(timezone.utc)
        db.add(n)
        db.commit()

    return {"ok": True, "dismissed_at": n.dismissed_at.isoformat()}

@router.get("/in-app/summary", response_model=InAppNotificationSummaryResponse)
async def summarize_in_app_notifications(
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    分析用：InAppNotification の期間サマリ（read only）

    - created_at 基準で from/to を解釈
    - dismissed は dismissed_at != null
    - webpush_events は extra.webpush.status を集計（イベント軸）
    """
    base = (
        db.query(InAppNotification)
        .filter(InAppNotification.user_id == current_user.id)
    )

    if from_:
        base = base.filter(InAppNotification.created_at >= from_)
    if to:
        base = base.filter(InAppNotification.created_at <= to)

    # ✅ DB集計（全件ロードしない）
    total = (
        base.with_entities(func.count(InAppNotification.id))
        .scalar()
        or 0
    )

    dismissed = (
        base.filter(InAppNotification.dismissed_at.isnot(None))
        .with_entities(func.count(InAppNotification.id))
        .scalar()
        or 0
    )

    dismiss_rate = round((dismissed / total) * 100) if total else 0

    # ✅ webpush status をDBで group by（JSONB）
    # extra->'webpush'->>'status' が取れない/NULL は unknown に寄せる
    status_expr = InAppNotification.extra["webpush"]["status"].astext

    rows = (
        base.with_entities(status_expr.label("status"), func.count(InAppNotification.id).label("cnt"))
        .group_by(status_expr)
        .all()
    )

    events = {"sent": 0, "failed": 0, "deactivated": 0, "skipped": 0, "unknown": 0}
    for status, cnt in rows:
        if status in events:
            events[status] += int(cnt or 0)
        else:
            events["unknown"] += int(cnt or 0)

    return {
        "range": {
            "from": from_.isoformat() if from_ else None,
            "to": to.isoformat() if to else None,
        },
        "total": int(total),
        "dismissed": int(dismissed),
        "dismiss_rate": int(dismiss_rate),
        "webpush_events": events,
    }
