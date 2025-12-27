# backend/app/api/v1/endpoints/notification_runs.py

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.notification_run import NotificationRun
from app.models.in_app_notification import InAppNotification

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


@router.get("/notification-runs/{run_id}")
def get_notification_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    r = db.query(NotificationRun).filter(NotificationRun.id == run_id).first()
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


@router.get("/notification-runs/latest")
def latest_notification_run(db: Session = Depends(get_db)):
    r = db.query(NotificationRun).order_by(NotificationRun.id.desc()).first()
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

    items = (
        db.query(InAppNotification)
        .filter(InAppNotification.run_id == run_id)
        .all()
    )

    inapp_total = len(items)

    # 反応（dismiss）
    dismissed_count = sum(1 for n in items if n.dismissed_at is not None)
    dismiss_rate = round((dismissed_count / inapp_total) * 100) if inapp_total else 0

    # 配信（subscription単位 counts）
    delivered = 0
    failed = 0
    deactivated = 0
    unknown = 0

    # 配信（イベント単位 status）
    events_sent = 0
    events_failed = 0
    events_deactivated = 0
    events_skipped = 0
    events_unknown = 0

    for n in items:
        extra = n.extra or {}
        wp = extra.get("webpush")
        if not isinstance(wp, dict):
            unknown += 1
            events_unknown += 1
            continue

        delivered += int(wp.get("sent", 0) or 0)
        failed += int(wp.get("failed", 0) or 0)
        deactivated += int(wp.get("deactivated", 0) or 0)

        st = wp.get("status")
        if st == "sent":
            events_sent += 1
        elif st == "failed":
            events_failed += 1
        elif st == "deactivated":
            events_deactivated += 1
        elif st == "skipped":
            events_skipped += 1
        else:
            events_unknown += 1

    return {
        "run": {
            "id": r.id,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "stats": r.stats,
        },
        "inapp": {
            "total": inapp_total,
            "dismissed_count": dismissed_count,
            "dismiss_rate": dismiss_rate,
            "webpush": {
                # subscription軸（件数）
                "delivered": delivered,
                "failed": failed,
                "deactivated": deactivated,
                "unknown": unknown,
                # イベント軸（通知レコード単位）
                "events": {
                    "sent": events_sent,
                    "failed": events_failed,
                    "deactivated": events_deactivated,
                    "skipped": events_skipped,
                    "unknown": events_unknown,
                },
            },
        },
        "run_counters": {
            "inapp_created": r.inapp_created,
            "webpush_sent": r.webpush_sent,
            "webpush_failed": r.webpush_failed,
            "webpush_deactivated": r.webpush_deactivated,
        },
    }
