# backend/app/api/v1/endpoints/analytics_actions.py

from datetime import datetime, timezone
from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.suggested_action_applied_event import SuggestedActionAppliedEvent
from app.models.action_effectiveness_snapshot import ActionEffectivenessSnapshot 
from app.services.outcome_analytics import (
    build_action_effectiveness,
    build_action_effectiveness_by_feature,
)

router = APIRouter()

@router.post("/actions/applied", response_model=dict)
def record_action_applied(
    action_id: str,
    bucket: Literal["week", "month"] = Query("week"),
    applied_at: Optional[datetime] = None,
    payload: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    SuggestedAction を適用した事実を保存する（資産）
    - OutcomeLog（真実）とは別レイヤ
    - payload は進化耐性のため自由dict
    """
    at = applied_at or datetime.now(timezone.utc)
    ev = SuggestedActionAppliedEvent(
        user_id=current_user.id,
        action_id=action_id,
        bucket=bucket,
        applied_at=at,
        payload=payload or {},
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    return {
        "ok": True,
        "event": {
            "id": ev.id,
            "action_id": ev.action_id,
            "bucket": ev.bucket,
            "applied_at": ev.applied_at,
            "payload": ev.payload,
            "created_at": ev.created_at,
        },
    }

@router.get("/actions/applied", response_model=dict)
def list_actions_applied(
    action_id: Optional[str] = None,
    bucket: Optional[Literal["week", "month"]] = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(SuggestedActionAppliedEvent).filter(
        SuggestedActionAppliedEvent.user_id == current_user.id
    )
    if action_id:
        q = q.filter(SuggestedActionAppliedEvent.action_id == action_id)
    if bucket:
        q = q.filter(SuggestedActionAppliedEvent.bucket == bucket)

    rows = q.order_by(SuggestedActionAppliedEvent.applied_at.desc()).limit(limit).all() or []
    return {
        "items": [
            {
                "id": r.id,
                "action_id": r.action_id,
                "bucket": r.bucket,
                "applied_at": r.applied_at,
                "payload": r.payload,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }

@router.get("/actions/effectiveness", response_model=dict)
def get_actions_effectiveness(
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    window_days: int = Query(7, ge=1, le=60),
    min_total: int = Query(5, ge=1, le=200),
    limit_events: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    SuggestedAction の効果を返す（read-only）
    - v0 は action 条件で絞らず、OutcomeLog（SSOT）だけで前後比較する
    """
    return build_action_effectiveness(
        db,
        user_id=current_user.id,
        from_applied_at=from_,
        to_applied_at=to,
        window_days=window_days,
        min_total=min_total,
        limit_events=limit_events,
    )

@router.get("/actions/effectiveness/by-feature", response_model=dict)
def get_actions_effectiveness_by_feature(
    version: str = Query("v1"),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    window_days: int = Query(7, ge=1, le=60),
    min_total: int = Query(5, ge=1, le=200),
    limit_events: int = Query(500, ge=1, le=5000),
    limit_samples_per_event: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    SuggestedAction の効果を action × feature で返す（read-only）
    - v1: applied_at 直前 window の FeatureSnapshot を「条件」として利用
    """
    return build_action_effectiveness_by_feature(
        db,
        user_id=current_user.id,
        feature_version=version,
        from_applied_at=from_,
        to_applied_at=to,
        window_days=window_days,
        min_total=min_total,
        limit_events=limit_events,
        limit_samples_per_event=limit_samples_per_event,
    )

@router.get("/actions/effectiveness/snapshots", response_model=dict)
def list_action_effectiveness_snapshots(
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    action_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ✅ ActionEffectivenessSnapshot の履歴を返す（read-only / 監査資産）
    - OutcomeLog（SSOT）から派生した「過去の評価」をそのまま参照
    - 再計算せず、履歴を壊さない
    """
    q = db.query(ActionEffectivenessSnapshot).filter(
        ActionEffectivenessSnapshot.user_id == current_user.id
    )

    if from_ is not None:
        q = q.filter(ActionEffectivenessSnapshot.captured_at >= from_)
    if to is not None:
        q = q.filter(ActionEffectivenessSnapshot.captured_at <= to)
    if action_id:
        q = q.filter(ActionEffectivenessSnapshot.action_id == action_id)

    rows = (
        q.order_by(
            ActionEffectivenessSnapshot.captured_at.desc(),
            ActionEffectivenessSnapshot.action_id.asc(),
        )
        .limit(limit)
        .all()
    ) or []

    return {
        "range": {
            "timezone": "Asia/Tokyo",
            "from": from_,
            "to": to,
            "limit": limit,
            "action_id": action_id,
        },
        "items": [
            {
                "id": r.id,
                "captured_at": r.captured_at,
                "bucket": r.bucket,
                "window_days": r.window_days,
                "min_total": r.min_total,
                "limit_events": r.limit_events,
                "action_id": r.action_id,
                "applied_count": r.applied_count,
                "measured_count": r.measured_count,
                "improved_count": r.improved_count,
                "improved_rate": r.improved_rate,
                "avg_delta_missed_rate": r.avg_delta_missed_rate,
            }
            for r in rows
        ],
    }
