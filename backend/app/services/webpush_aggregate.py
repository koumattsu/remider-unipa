# backend/app/services/webpush_aggregate.py

from __future__ import annotations
from typing import Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.in_app_notification import InAppNotification

DEFAULT_EVENTS = {"sent": 0, "failed": 0, "deactivated": 0, "skipped": 0, "unknown": 0}

def calc_webpush_events_for_run(db: Session, run_id: int) -> Dict[str, int]:
    """
    SSOT: InAppNotification.extra["webpush"]["status"] を唯一の真実として集計する
    - 可能ならDB集計（Postgres JSONB）
    - 無理なら fallback で全件ロードしてPython集計（テストFakeSessionでも動く）
    """
    events = dict(DEFAULT_EVENTS)

    # ① DB集計（Postgres想定）
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
        return events
    except Exception:
        # ② fallback（SQLite/FakeSession向け）
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

        return events
