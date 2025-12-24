from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.in_app_notification import InAppNotification

router = APIRouter()

@router.get("/in-app")
async def list_in_app_notifications(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    qs = (
        db.query(InAppNotification)
        .filter(InAppNotification.user_id == current_user.id)
        .filter(InAppNotification.dismissed_at.is_(None))
        .order_by(InAppNotification.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": n.id,
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "deep_link": n.deep_link,
                "task_id": n.task_id,
                "deadline_at_send": n.deadline_at_send.isoformat(),
                "offset_hours": n.offset_hours,
                "created_at": n.created_at.isoformat(),
            }
            for n in qs
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

    return {"ok": True}