# backend/app/api/v1/endpoints/analytics_outcomes.py

from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.outcome_analytics import build_outcome_summary, build_outcome_missed_by_course
from app.models.outcome_feature_snapshot import OutcomeFeatureSnapshot

router = APIRouter()

@router.get("/outcomes/summary", response_model=dict)
def get_outcome_summary(
    bucket: Literal["week", "month"] = Query("week"),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    OutcomeLog を唯一の真実として集計した達成率を返す（read-only）
    - from/to は deadline 基準
    - bucket は JST基準の週/月
    """
    return build_outcome_summary(
        db,
        user_id=current_user.id,
        bucket=bucket,
        from_deadline=from_,
        to_deadline=to,
    )

@router.get("/outcomes/by-course", response_model=dict)
def get_outcome_missed_by_course(
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    OutcomeLog を唯一の真実として course別 missed率 を返す（read-only）
    - from/to は deadline 基準
    - course_name は tasks からラベル参照
    """
    return build_outcome_missed_by_course(
        db,
        user_id=current_user.id,
        from_deadline=from_,
        to_deadline=to,
    )

@router.get("/outcomes/features", response_model=dict)
def list_outcome_feature_snapshots(
    version: Optional[str] = Query(None),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(OutcomeFeatureSnapshot)
        .filter(OutcomeFeatureSnapshot.user_id == current_user.id)
    )

    if version:
        q = q.filter(OutcomeFeatureSnapshot.feature_version == version)
    if from_:
        q = q.filter(OutcomeFeatureSnapshot.deadline >= from_)
    if to:
        q = q.filter(OutcomeFeatureSnapshot.deadline <= to)

    rows = (
        q.order_by(OutcomeFeatureSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "range": {
            "timezone": "Asia/Tokyo",
            "version": version,
            "from": from_,
            "to": to,
            "limit": limit,
        },
        "items": [
            {
                "task_id": r.task_id,
                "deadline": r.deadline,
                "feature_version": r.feature_version,
                "features": r.features,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }
