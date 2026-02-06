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
import base64
import hashlib
import hmac

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

def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))

def _parse_event_token(token: str) -> dict:
    """
    webpush_sender._make_event_token と同一仕様で検証・復元する。
    token = "{b64url(msg)}.{b64url(sig)}"
    msg = "user_id.notification_id.run_id.issued_at"
    """
    try:
        msg_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid event_token")

    msg = _b64url_decode(msg_b64)
    sig = _b64url_decode(sig_b64)

    secret = (getattr(settings, "WEBPUSH_EVENT_SECRET", None) or "").encode("utf-8")
    expected = hmac.new(secret, msg, hashlib.sha256).digest()

    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=400, detail="invalid event_token")

    try:
        user_id_str, nid_str, rid_str, issued_at_str = msg.decode("utf-8").split(".", 3)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid event_token")

    if not user_id_str:
        raise HTTPException(status_code=400, detail="invalid event_token")

    return {
        "user_id": int(user_id_str),
        "notification_id": (None if nid_str == "" else nid_str),
        "run_id": (None if rid_str == "" else int(rid_str)),
        "issued_at": int(issued_at_str) if issued_at_str else None,
    }

@router.post(
    "/events",
    response_model=WebPushEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_webpush_event(
    payload: WebPushEventCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    if not payload.event_token:
        raise HTTPException(status_code=400, detail="event_token is required")

    data = _parse_event_token(payload.event_token)

    # 監査上、client payload は改ざん可能なので token 内の値を優先
    row = WebPushEvent(
        user_id=int(data["user_id"]),
        event_type=payload.type,
        notification_id=data.get("notification_id"),
        run_id=data.get("run_id"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row