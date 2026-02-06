# backend/app/api/v1/endpoints/webpush_subscriptions.py

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.webpush_subscription import WebPushSubscription
from app.models.webpush_event import WebPushEvent
from app.schemas.webpush_subscription import (
    WebPushSubscriptionCreate,
    WebPushSubscriptionResponse,
)
from app.schemas.webpush_event import WebPushEventCreate, WebPushEventResponse
from app.services.webpush_sender import WebPushSender
from itsdangerous import URLSafeSerializer, BadSignature

router = APIRouter()

@router.get("/public-key")
def get_vapid_public_key(
    current_user: User = Depends(get_current_user),
):
    # 認証必須にしておく（運用上の雑アクセスを減らす）
    return {"publicKey": settings.VAPID_PUBLIC_KEY}

@router.get(
    "/subscriptions",
    response_model=list[WebPushSubscriptionResponse],
)
def list_my_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(WebPushSubscription)
        .filter(WebPushSubscription.user_id == current_user.id)
        .order_by(WebPushSubscription.created_at.desc())
        .all()
    )
    return rows

@router.post(
    "/subscriptions",
    response_model=WebPushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def upsert_subscription(
    payload: WebPushSubscriptionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    endpoint を唯一キーとして upsert。

    - 同一endpointが既にあれば keys 更新 + is_active=true + last_seen_at更新
    - user が違う場合でも、このブラウザが subscription を提示できている=同一端末操作なので
      user_id を付け替える（ログイン切替に強い）
    """
    now = datetime.now(timezone.utc)

    existing = (
        db.query(WebPushSubscription)
        .filter(WebPushSubscription.endpoint == payload.endpoint)
        .one_or_none()
    )

    if existing:
        existing.user_id = current_user.id
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth

        ua = request.headers.get("user-agent")
        existing.user_agent = ua or payload.user_agent

        existing.device_label = payload.device_label
        existing.is_active = True
        existing.last_seen_at = now
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    ua = request.headers.get("user-agent")

    row = WebPushSubscription(
        user_id=current_user.id,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        user_agent=ua or payload.user_agent,
        device_label=payload.device_label,
        is_active=True,
        last_seen_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@router.delete(
    "/subscriptions/by-endpoint",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deactivate_subscription_by_endpoint(
    endpoint: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    フロントが持っているのは endpoint が本体なので、
    endpoint 指定で無効化できる口も用意しておく（壊れにくい）。
    """
    row = (
        db.query(WebPushSubscription)
        .filter(WebPushSubscription.endpoint == endpoint)
        .one_or_none()
    )
    if not row:
        return

    if row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    row.is_active = False
    db.add(row)
    db.commit()
    return

@router.post("/debug-send")
def debug_send_webpush(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ログイン中ユーザーに Web Push を即送信して疎通確認する。
    cron待ちゼロで「届く/届かない」を切り分けられる。
    """
    result = WebPushSender.send_debug(db, user_id=current_user.id)
    return result

@router.post(
    "/events",
    response_model=WebPushEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def _event_serializer():
    return URLSafeSerializer(
        settings.SESSION_SECRET,
        salt="unipa-webpush-event"
    )

def record_webpush_event(
    payload: WebPushEventCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    if not payload.event_token:
        raise HTTPException(status_code=400, detail="event_token is required")

    try:
        data = _event_serializer().loads(payload.event_token)
    except BadSignature:
        raise HTTPException(status_code=400, detail="invalid event_token")

    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="invalid event_token")

    row = WebPushEvent(
        user_id=int(user_id),
        event_type=payload.type,
        notification_id=str(payload.notification_id) if payload.notification_id is not None else None,
        run_id=payload.run_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
