# backend/app/api/v1/endpoints/notification_runs.py

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.models.notification_run import NotificationRun
from app.models.in_app_notification import InAppNotification
from app.models.webpush_event import WebPushEvent
from app.models.webpush_delivery import WebPushDelivery
from app.services.webpush_aggregate import (
    calc_webpush_events_for_run,
    calc_webpush_events_with_source_for_run,
)
from app.services.in_app_summary_aggregate import calc_in_app_summary_for_run

router = APIRouter(tags=["admin"])

@router.get("/notification-runs")
def list_notification_runs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items = (
        db.query(NotificationRun)
        .order_by(NotificationRun.id.desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": r.id,
                "status": r.status,
                "error_summary": r.error_summary,
                "users_processed": r.users_processed,
                "due_candidates_total": r.due_candidates_total,
                "morning_candidates_total": r.morning_candidates_total,
                "inapp_created": r.inapp_created,
                "webpush_sent": r.webpush_sent,
                "webpush_failed": r.webpush_failed,
                "webpush_deactivated": r.webpush_deactivated,
                "line_sent": r.line_sent,
                "line_failed": r.line_failed,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "stats": r.stats,
            }
            for r in items
        ]
    }

@router.get("/notification-runs/latest")
def latest_notification_run(db: Session = Depends(get_db)):
    r = db.query(NotificationRun).order_by(NotificationRun.id.desc()).first()
    if not r:
        raise HTTPException(status_code=404, detail="not found")

    run = {
        "id": r.id,
        "status": r.status,
        "error_summary": r.error_summary,
        "users_processed": r.users_processed,
        "due_candidates_total": r.due_candidates_total,
        "morning_candidates_total": r.morning_candidates_total,
        "inapp_created": r.inapp_created,
        "webpush_sent": r.webpush_sent,
        "webpush_failed": r.webpush_failed,
        "webpush_deactivated": r.webpush_deactivated,
        "line_sent": r.line_sent,
        "line_failed": r.line_failed,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "stats": r.stats,
    }

    # ✅ 後方互換:
    # - 旧: data.run でも動く
    # - 現UI: data.id でも動く
    return {"found": True, "run": run, **run}

@router.get("/notification-runs/{run_id}")
def get_notification_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    # ✅ FakeSessionでも壊れないように「all()→手動検索」
    runs = db.query(NotificationRun).all() or []
    r = next((x for x in runs if int(getattr(x, "id", -1)) == int(run_id)), None)

    if not r:
        raise HTTPException(status_code=404, detail="not found")

    return {
        "id": r.id,
        "status": r.status,
        "error_summary": r.error_summary,
        "users_processed": r.users_processed,
        "due_candidates_total": r.due_candidates_total,
        "morning_candidates_total": r.morning_candidates_total,
        "inapp_created": r.inapp_created,
        "webpush_sent": r.webpush_sent,
        "webpush_failed": r.webpush_failed,
        "webpush_deactivated": r.webpush_deactivated,
        "line_sent": r.line_sent,
        "line_failed": r.line_failed,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }

@router.get("/notification-runs/{run_id}/in-app")
def list_run_in_app_notifications(
    run_id: int,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    # run existence check（観測の説明がしやすい）
    r = db.query(NotificationRun).filter(NotificationRun.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="run not found")

    items = (
        db.query(InAppNotification)
        .filter(InAppNotification.run_id == run_id)
        .order_by(InAppNotification.id.desc())
        .limit(limit)
        .all()
    )

    return {
        "run_id": run_id,
        "items": [
            {
                "id": n.id,
                "run_id": n.run_id,
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "deep_link": n.deep_link,
                "task_id": n.task_id,
                "deadline_at_send": n.deadline_at_send.isoformat() if n.deadline_at_send else None,
                "offset_hours": n.offset_hours,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "dismissed_at": n.dismissed_at.isoformat() if n.dismissed_at else None,
                "extra": n.extra,
            }
            for n in items
        ],
    }

@router.get("/notification-runs/{run_id}/summary")
def get_run_summary(
    run_id: int,
    db: Session = Depends(get_db),
):
    r = db.query(NotificationRun).filter(NotificationRun.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="run not found")

    summary = calc_in_app_summary_for_run(db, run_id)

    events_raw, webpush_source = calc_webpush_events_with_source_for_run(db, run_id)

    # ✅ 契約固定: events はこのキー集合のみ返す（余計なキーが混ざっても落とす）
    EXPECTED_EVENT_KEYS = ["sent", "failed", "deactivated", "skipped", "unknown"]
    events = {
        k: int((events_raw or {}).get(k, 0) or 0)
        for k in EXPECTED_EVENT_KEYS
    }

    events_sum = sum(events.values())

    inapp_total = int(summary.get("inapp_total", 0) or 0)
    # ✅ FakeSession/集計不能時の fallback：契約（events_sum <= total）を守る
    if inapp_total < events_sum:
        inapp_total = events_sum

    # 反応（dismiss）
    dismissed_count = int(summary.get("dismissed_count", 0) or 0)
    if dismissed_count > inapp_total:
        dismissed_count = inapp_total
    dismiss_rate = round((dismissed_count / inapp_total) * 100) if inapp_total else 0

    # 配信（subscription単位 counts）
    delivered = int(summary.get("delivered", 0) or 0)
    failed = int(summary.get("failed", 0) or 0)
    deactivated = int(summary.get("deactivated", 0) or 0)
    unknown = int(summary.get("unknown", 0) or 0)

    # ✅ 反応率（通知タップ→アプリ起動）: message軸 SSOT は summary 側に集約
    opened_messages = int(summary.get("opened_messages", 0) or 0)
    sent_messages = int(summary.get("sent_messages", 0) or 0)
    # open_rate は float で返ってくる可能性があるので保守的に扱う
    open_rate = summary.get("open_rate", 0) or 0

    # ✅ 監査耐性: stats が欠けていても summary では説明可能にする（補完）
    stats = r.stats if isinstance(r.stats, dict) else None
    if isinstance(stats, dict):
        payload = stats.get("payload")
        if not isinstance(payload, dict):
            payload = {}
            stats["payload"] = payload

        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict):
            snapshot = {}
            payload["snapshot"] = snapshot

        # webpush_events が欠けていれば補完（キー集合は契約で固定済み）
        if not isinstance(snapshot.get("webpush_events"), dict):
            snapshot["webpush_events"] = events

        # webpush_source が欠けていれば補完（最小diff: 保守的に fallback 扱い）
        if snapshot.get("webpush_source") is None:
            snapshot["webpush_source"] = webpush_source

        # opened を snapshot にも補完（後方互換・観測強化）
        if snapshot.get("webpush_opened_messages") is None:
            snapshot["webpush_opened_messages"] = opened_messages
        if snapshot.get("webpush_sent_messages") is None:
            snapshot["webpush_sent_messages"] = sent_messages
        if snapshot.get("webpush_open_rate") is None:
            snapshot["webpush_open_rate"] = open_rate

    return {
        "summary_v": 1,
        "run": {
            "id": r.id,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "stats": stats,
        },
        "inapp": {
            "total": inapp_total,
            "dismissed_count": dismissed_count,
            "dismiss_rate": dismiss_rate,
            "webpush": {
                # ✅ delivery軸（attemptログ）: subscription / retry を含む
                "delivered": delivered,
                "failed": failed,
                "deactivated": deactivated,
                "unknown": unknown,

                # ✅ message軸（通知そのもの）: UIの「送信数」「反応率」はこっちを見る
                "sent_messages": sent_messages,
                "opened_messages": opened_messages,
                "open_rate": open_rate,

                "events": events,
            },
        },
        "run_counters": {
            "inapp_created": r.inapp_created,
            "webpush_sent": r.webpush_sent,
            "webpush_failed": r.webpush_failed,
            "webpush_deactivated": r.webpush_deactivated,
        },
    }