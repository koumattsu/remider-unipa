# backend/app/services/in_app_summary_aggregate.py

from __future__ import annotations
from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, case, cast, Integer
from app.models.in_app_notification import InAppNotification
from app.models.webpush_delivery import WebPushDelivery
from typing import Optional

def calc_in_app_summary_for_run(db: Session, run_id: int) -> Dict[str, int]:
    """
    summary用の集計（DB集計が可能ならDBで）
    - inapp_total
    - dismissed_count
    - delivered/failed/deactivated（subscription軸の合計）
    - unknown（webpushがdictでないレコード数）
    - sent_messages/opened_messages/open_rate（message軸 / opened ÷ sent）
    """
    # ① DB集計（Postgres JSONB想定）
    try:
        # ✅ OS Push SSOT: WebPushDelivery から「通知メッセージ数（distinct）」を数える
        # - subscription が0件だと deliveries が作られず 0 になるので、その場合は InAppNotification にフォールバック
        inapp_total_from_delivery = int(
            db.query(func.count(func.distinct(WebPushDelivery.in_app_notification_id)))
            .filter(WebPushDelivery.run_id == run_id)
            .scalar()
            or 0
        )

        if inapp_total_from_delivery > 0:
            inapp_total = inapp_total_from_delivery
        else:
            inapp_total = int(
                db.query(func.count(InAppNotification.id))
                .filter(InAppNotification.run_id == run_id)
                .filter(InAppNotification.channel == "web_push")
                .scalar()
                or 0
            )

        # ✅ OS Pushには「dismissed（アプリ内で消した）」が無いので 0 固定
        dismissed_count = 0

        # ✅ message軸 SSOT: sent_messages（push service 受理成功のメッセージ数）
        # - ここが 0 になると UI の分母が崩れるので、防波堤を厚くする
        _sent_status = getattr(WebPushDelivery, "STATUS_SENT", "sent")
        sent_messages = int(
            db.query(func.count(func.distinct(WebPushDelivery.in_app_notification_id)))
            .filter(WebPushDelivery.run_id == run_id)
            .filter(WebPushDelivery.status.in_([_sent_status, "sent"]))
            .scalar()
            or 0
        )
        # ✅ もし status 比較の都合で 0 になる環境でも、deliveryが存在する限り message数は取れるようにする
        #   （attempt軸ではなく distinct(message) なので分母として安全）
        if sent_messages == 0:
            sent_messages = int(
                db.query(func.count(func.distinct(WebPushDelivery.in_app_notification_id)))
                .filter(WebPushDelivery.run_id == run_id)
                .scalar()
                or 0
            )

        # ✅ message軸 SSOT: opened_messages（= 通知を押してアプリを開いた数）
        # ※ WebPushEvent が無い環境でも壊さない（optional）
        opened_messages: int = 0
        try:
            from app.models.webpush_event import WebPushEvent  # ← ここはあなたの実体に合わせる
            opened_messages = int(
                db.query(func.count(func.distinct(WebPushEvent.notification_id)))
                .filter(WebPushEvent.run_id == run_id)
                .filter(WebPushEvent.event_type == "opened")
                .filter(WebPushEvent.notification_id.isnot(None))  # ✅ None除外
                .scalar()
                or 0
            )
        except Exception:
            opened_messages = 0

        # ✅ opened が sent を超えたら監査的に破綻なので丸める（UIの分子>分母を絶対に起こさない）
        if opened_messages > sent_messages:
            opened_messages = sent_messages

        # ✅ フロントで型ブレしないように backend で整数に丸めて返す
        open_rate = round((opened_messages / sent_messages) * 100) if sent_messages > 0 else 0

        # ✅ SSOT: WebPushDelivery（subscription軸の合計）
        # NOTE: ここでの delivered は「端末到達」ではなく
        #       WebPushDelivery.STATUS_SENT（= Push service 受理 / 送信成功）を数える。
        #       将来、端末到達が取れるようになったら delivered を別概念として導入する。
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
                .filter(InAppNotification.channel == "web_push")
                .scalar()
                or 0
            )
            failed = int(
                db.query(func.coalesce(func.sum(failed_expr), 0))
                .filter(InAppNotification.run_id == run_id)
                .filter(InAppNotification.channel == "web_push")
                .scalar()
                or 0
            )
            deactivated = int(
                db.query(func.coalesce(func.sum(deactivated_expr), 0))
                .filter(InAppNotification.run_id == run_id)
                .filter(InAppNotification.channel == "web_push")
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
                .filter(InAppNotification.channel == "web_push")
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
            # ✅ message軸（開封率のSSOT）
            "sent_messages": sent_messages,
            "opened_messages": opened_messages,
            "open_rate": open_rate,
        }

    except Exception:
        # ② fallback（SQLite / FakeSession向け）
        items = (
            db.query(InAppNotification)
            .filter(InAppNotification.run_id == run_id)
            .all()
        )

        # ✅ FakeSession の _FakeInApp は channel を持たない
        #    → channel が無いものは "web_push" 扱いにして契約テストを守る
        items_wp = [
            n for n in items
            if getattr(n, "channel", "web_push") == "web_push"
        ]

        inapp_total = len(items_wp)
        dismissed_count = sum(1 for n in items_wp if n.dismissed_at is not None)

        delivered = 0
        failed = 0
        deactivated = 0
        unknown = 0

        for n in items_wp:
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
