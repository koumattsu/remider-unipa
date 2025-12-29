# backend/app/api/v1/endpoints/notification_runs.py

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.notification_run import NotificationRun
from app.models.in_app_notification import InAppNotification
from app.services.webpush_aggregate import calc_webpush_events_for_run
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
        "stats": r.stats,  # ← snapshot契約があるならここで載せる
    }
    return {"found": True, "run": run}

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

    inapp_total = summary["inapp_total"]

    # 反応（dismiss）
    dismissed_count = summary["dismissed_count"]
    dismiss_rate = round((dismissed_count / inapp_total) * 100) if inapp_total else 0

    # 配信（subscription単位 counts）
    delivered = summary["delivered"]
    failed = summary["failed"]
    deactivated = summary["deactivated"]
    unknown = summary["unknown"]

    # ✅ イベント軸（通知レコード単位）は SSOT
    events = calc_webpush_events_for_run(db, run_id)

    return {
        "summary_v": 1,
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
                "delivered": delivered,
                "failed": failed,
                "deactivated": deactivated,
                "unknown": unknown,
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