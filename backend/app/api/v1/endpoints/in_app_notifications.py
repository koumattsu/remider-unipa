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
from app.db.base import is_sqlite
from app.core.security import get_current_user
from app.models.user import User
from app.models.in_app_notification import InAppNotification
from app.models.webpush_event import WebPushEvent
from app.models.webpush_delivery import WebPushDelivery

router = APIRouter()

@router.get(
    "/in-app",
    response_model=InAppNotificationListResponse,
    summary="In-app通知一覧（ベル通知）",
    description=(
        "InAppNotification を created_at 基準で取得します。\n"
        "- include_dismissed=false の場合、dismissed_at が null のみ返します\n"
        "- from/to は created_at の範囲フィルタです（ISO8601）"
    ),
    response_description="In-app通知の配列（created_at desc）",
)
async def list_in_app_notifications(
    limit: int = Query(20, ge=1, le=100, description="取得件数（最大100）"),
    include_dismissed: bool = Query(False, description="dismiss 済みも含める"),
    from_: datetime | None = Query(None, alias="from", description="created_at の下限（ISO8601）"),
    to: datetime | None = Query(None, description="created_at の上限（ISO8601）"),
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

@router.post(
    "/in-app/{notification_id}/dismiss",
    summary="In-app通知をdismiss（既読化）",
    description="対象の InAppNotification の dismissed_at を現在時刻（UTC）で埋めます。",
    response_description="dismiss 結果",
)
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

@router.get(
    "/in-app/summary",
    response_model=InAppNotificationSummaryResponse,
    summary="In-app通知の期間サマリ（read-only）",
    description=(
        "StatsView 用の read-only 集計API。\n"
        "- created_at 基準で from/to を解釈\n"
        "- dismissed は dismissed_at != null\n"
        "- webpush_events は extra.webpush.status をイベント軸で集計（sent/failed/deactivated/skipped/unknown）\n"
        "※ 全件ロードせず DB 集計で返します。"
    ),
    response_description="期間サマリ（total/dismiss_rate/webpush_events）",
)
async def summarize_in_app_notifications(
    from_: datetime | None = Query(None, alias="from", description="created_at の下限（ISO8601）"),
    to: datetime | None = Query(None, description="created_at の上限（ISO8601）"),
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

    # =========================
    # InApp（資産）集計：UI分母には使わない
    # =========================
    inapp_total = int(base.with_entities(func.count(InAppNotification.id)).scalar() or 0)
    inapp_dismissed = int(
        base.filter(InAppNotification.dismissed_at.isnot(None))
        .with_entities(func.count(InAppNotification.id))
        .scalar()
        or 0
    )
    inapp_dismiss_rate = round((inapp_dismissed / inapp_total) * 100) if inapp_total else 0

    # =========================
    # WebPush（SSOT）集計：WebPushDelivery / WebPushEvent
    # - total = sent
    # - dismissed = opened
    # - dismiss_rate = open_rate
    # =========================
    deliveries = db.query(WebPushDelivery).filter(WebPushDelivery.user_id == current_user.id)
    if from_:
        deliveries = deliveries.filter(WebPushDelivery.attempted_at >= from_)
    if to:
        deliveries = deliveries.filter(WebPushDelivery.attempted_at <= to)

    rows = (
        deliveries.with_entities(WebPushDelivery.status, func.count(WebPushDelivery.id))
        .group_by(WebPushDelivery.status)
        .all()
    )
    events = {"sent": 0, "failed": 0, "deactivated": 0, "skipped": 0, "unknown": 0}
    for st, cnt in rows or []:
        key = st if st in events else "unknown"
        events[key] += int(cnt or 0)

    opened_q = (
        db.query(WebPushEvent)
        .filter(WebPushEvent.user_id == current_user.id)
        .filter(WebPushEvent.event_type == "opened")
        .filter(WebPushEvent.notification_id.isnot(None))  # ✅ debug等のNoneを除外
    )
    if from_:
        opened_q = opened_q.filter(WebPushEvent.created_at >= from_)
    if to:
        opened_q = opened_q.filter(WebPushEvent.created_at <= to)

    # ✅ 同じ通知IDは端末が何個でも 1 カウント（ユーザ単位=通知単位）
    opened = int(
        opened_q.with_entities(func.count(func.distinct(WebPushEvent.notification_id)))
        .scalar()
        or 0
    )

    sent = int(events.get("sent", 0))
    open_rate = round((opened / sent) * 100) if sent else 0

    return {
        "range": {
            "from": from_.isoformat() if from_ else None,
            "to": to.isoformat() if to else None,
        },
        # ✅ UIの「通知反応」は WebPush に寄せる
        "total": sent,
        "dismissed": opened,
        "dismiss_rate": int(open_rate),
        "inapp": {
            "total": inapp_total,
            "dismissed": inapp_dismissed,
            "dismiss_rate": int(inapp_dismiss_rate),
        },
        "webpush_events": events,
    }