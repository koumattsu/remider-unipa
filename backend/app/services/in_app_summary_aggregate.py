# backend/app/services/in_app_summary_aggregate.py

from __future__ import annotations
from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, case, cast, Integer
from app.models.in_app_notification import InAppNotification
from app.models.webpush_delivery import WebPushDelivery

def calc_in_app_summary_for_run(db: Session, run_id: int) -> Dict[str, int]:
    """
    summary用の集計（DB集計が可能ならDBで）
    - inapp_total
    - dismissed_count
    - delivered/failed/deactivated（subscription軸の合計）
    - unknown（webpushがdictでないレコード数）
    """
    # ① DB集計（Postgres JSONB想定）
    try:
        inapp_total = int(
            db.query(func.count(InAppNotification.id))
            .filter(InAppNotification.run_id == run_id)
            .scalar()
            or 0
        )

        dismissed_count = int(
            db.query(func.count(InAppNotification.id))
            .filter(InAppNotification.run_id == run_id)
            .filter(InAppNotification.dismissed_at.isnot(None))
            .scalar()
            or 0
        )

        # ✅ SSOT: WebPushDelivery（subscription軸の合計）
        delivered = 0
        failed = 0
        deactivated = 0
        unknown = 0

        try:
            rows = (
                db.query(WebPushDelivery.status, func.count(WebPushDelivery.id))
                .filter(WebPushDelivery.run_id == run_id)
                .group_by(WebPushDelivery.status)
                .all()
            )
            for st, cnt in rows:
                c = int(cnt or 0)
                if st == WebPushDelivery.STATUS_SENT:
                    delivered += c
                elif st == WebPushDelivery.STATUS_FAILED:
                    failed += c
                elif st == WebPushDelivery.STATUS_DEACTIVATED:
                    deactivated += c
                else:
                    unknown += c
        except Exception:
            # ✅ fallback: 旧SSOT（InAppNotification.extra）
            sent_expr = cast(
                func.coalesce(
                    func.jsonb_extract_path_text(InAppNotification.extra, "webpush", "sent"),
                    "0",
                ),
                Integer,
            )
            failed_expr = cast(
                func.coalesce(
                    func.jsonb_extract_path_text(InAppNotification.extra, "webpush", "failed"),
                    "0",
                ),
                Integer,
            )
            deactivated_expr = cast(
                func.coalesce(
                    func.jsonb_extract_path_text(InAppNotification.extra, "webpush", "deactivated"),
                    "0",
                ),
                Integer,
            )

            delivered = int(
                db.query(func.coalesce(func.sum(sent_expr), 0))
                .filter(InAppNotification.run_id == run_id)
                .scalar()
                or 0
            )
            failed = int(
                db.query(func.coalesce(func.sum(failed_expr), 0))
                .filter(InAppNotification.run_id == run_id)
                .scalar()
                or 0
            )
            deactivated = int(
                db.query(func.coalesce(func.sum(deactivated_expr), 0))
                .filter(InAppNotification.run_id == run_id)
                .scalar()
                or 0
            )

            # unknown は互換のため旧定義も維持（webpushがdictじゃない通知数）
            unknown = int(
                db.query(
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    func.jsonb_typeof(
                                        func.coalesce(
                                            InAppNotification.extra["webpush"],
                                            func.cast("null", InAppNotification.extra.type),
                                        )
                                    )
                                    == "object",
                                    0,
                                ),
                                else_=1,
                            )
                        ),
                        0,
                    )
                )
                .filter(InAppNotification.run_id == run_id)
                .scalar()
                or 0
            )

        return {
            "inapp_total": inapp_total,
            "dismissed_count": dismissed_count,
            "delivered": delivered,
            "failed": failed,
            "deactivated": deactivated,
            "unknown": unknown,
        }

    except Exception:
        # ② fallback（SQLite / FakeSession向け）
        items = (
            db.query(InAppNotification)
            .filter(InAppNotification.run_id == run_id)
            .all()
        )

        inapp_total = len(items)
        dismissed_count = sum(1 for n in items if n.dismissed_at is not None)

        delivered = 0
        failed = 0
        deactivated = 0
        unknown = 0

        for n in items:
            extra = n.extra or {}
            wp = extra.get("webpush")
            if not isinstance(wp, dict):
                unknown += 1
                continue
            delivered += int(wp.get("sent", 0) or 0)
            failed += int(wp.get("failed", 0) or 0)
            deactivated += int(wp.get("deactivated", 0) or 0)

        return {
            "inapp_total": inapp_total,
            "dismissed_count": dismissed_count,
            "delivered": delivered,
            "failed": failed,
            "deactivated": deactivated,
            "unknown": unknown,
        }
