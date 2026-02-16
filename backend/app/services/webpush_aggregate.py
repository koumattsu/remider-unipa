# backend/app/services/webpush_aggregate.py

from __future__ import annotations
from typing import Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.in_app_notification import InAppNotification
from app.models.webpush_delivery import WebPushDelivery

DEFAULT_EVENTS = {"sent": 0, "failed": 0, "deactivated": 0, "skipped": 0, "unknown": 0}

def calc_webpush_events_with_source_for_run(
    db: Session, run_id: int
) -> Tuple[Dict[str, int], str]:
    """
    SSOT（分母側）: WebPushDelivery を唯一の真実として集計する（attemptログ）
    - この集計は「送信attemptの結果（sent/failed/deactivated...）」のみを扱う
    - 「通知タップ→アプリ起動(opened)」は WebPushEvent 側の別SSOTであり、ここでは扱わない
    - 可能ならDB集計（delivery）
    - 無理なら fallback で InAppNotification.extra に戻す（FakeSession/SQLite）
    戻り値: (events, source) where source in {"delivery", "inapp_extra"}
    """
    events = dict(DEFAULT_EVENTS)

    # ① delivery 集計（最優先SSOT）
    try:
        rows = (
            db.query(WebPushDelivery.status, func.count(WebPushDelivery.id))
            .filter(WebPushDelivery.run_id == run_id)
            .group_by(WebPushDelivery.status)
            .all()
        )
        for st, cnt in rows:
            key = st if st in events else "unknown"
            events[key] += int(cnt or 0)
        return events, "delivery"
    except Exception:
        pass

    # ② fallback（SQLite/FakeSession向け）: InAppNotification.extra
    events = dict(DEFAULT_EVENTS)
    try:
        status_expr = func.jsonb_extract_path_text(
            InAppNotification.extra,
            "webpush",
            "status",
        )
        rows = (
            db.query(status_expr.label("status"), func.count(InAppNotification.id))
            .filter(InAppNotification.run_id == run_id)
            .group_by(status_expr)
            .all()
        )
        for st, cnt in rows:
            key = st if st in events else "unknown"
            events[key] += int(cnt or 0)
        return events, "inapp_extra"
    except Exception:
        items = (
            db.query(InAppNotification)
            .filter(InAppNotification.run_id == run_id)
            .all()
        )
        for n in items:
            extra = n.extra or {}
            wp = extra.get("webpush")
            if not isinstance(wp, dict):
                events["unknown"] += 1
                continue
            st = wp.get("status")
            key = st if st in events else "unknown"
            events[key] += 1
        return events, "inapp_extra"

def calc_webpush_events_for_run(db: Session, run_id: int) -> Dict[str, int]:
    """
    互換API（既存呼び出し用）: events dict だけ返す
    """
    events, _src = calc_webpush_events_with_source_for_run(db, run_id)
    return events