from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.notification_run import NotificationRun

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
