# backend/app/services/webpush_sender.py

import json
import logging
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from pywebpush import webpush, WebPushException
from app.core.config import settings
from app.models.notification_setting import NotificationSetting
from app.models.webpush_subscription import WebPushSubscription
from app.models.webpush_delivery import WebPushDelivery
from app.models.in_app_notification import InAppNotification

def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

def _make_event_token(*, user_id: int, notification_id: int | None, run_id: int | None, issued_at: int) -> str:
    # payload: "user_id.notification_id.run_id.issued_at"
    nid = "" if notification_id is None else str(notification_id)
    rid = "" if run_id is None else str(run_id)
    msg = f"{user_id}.{nid}.{rid}.{issued_at}".encode("utf-8")

    secret = (getattr(settings, "WEBPUSH_EVENT_SECRET", None) or "").encode("utf-8")
    sig = hmac.new(secret, msg, hashlib.sha256).digest()
    return f"{_b64url(msg)}.{_b64url(sig)}"

logger = logging.getLogger(__name__)

class WebPushSender:
    """
    Web Push 配信（配信層）
    - 判定ロジックは持たない
    - InAppNotification（イベント資産）をそのまま push payload にする
    """
    @staticmethod
    def _utcnow():
        return datetime.now(timezone.utc)
    
    @staticmethod
    def _is_enabled_for_user(db: Session, user_id: int) -> bool:
        """
        Web Push がユーザー設定で有効かどうか
        - NotificationSetting.enable_webpush を唯一の判定源にする
        - 設定が無い場合は False（安全側）
        """
        setting = (
            db.query(NotificationSetting)
            .filter(NotificationSetting.user_id == user_id)
            .one_or_none()
        )
        if not setting:
            return False
        return bool(setting.enable_webpush)

    @staticmethod
    def _send_payload(
        db: Session,
        *,
        user_id: int,
        payload: dict,
        in_app_notification_id: int | None = None,
        run_id: int | None = None,
    ) -> dict:
        """
        任意payloadをユーザーの全subscriptionへ送る（判定は持たない）
        戻り値: {sent, failed, deactivated}
        """
        # ✅ ユーザーの許可（設定）を尊重
        if not WebPushSender._is_enabled_for_user(db, user_id):
            return {"sent": 0, "failed": 0, "deactivated": 0}

        subs = (
            db.query(WebPushSubscription)
            .filter(
                WebPushSubscription.user_id == user_id,
                WebPushSubscription.is_active.is_(True),
            )
            .all()
        )
        if not subs:
            return {"sent": 0, "failed": 0, "deactivated": 0}

        payload_json = json.dumps(payload, ensure_ascii=False)
        now = WebPushSender._utcnow()
        sent = 0
        failed = 0
        deactivated = 0
        dirty = False

        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload_json,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.VAPID_SUBJECT},
                )

                # ✅ 成功した端末は health を更新
                sub.last_seen_at = now
                db.add(sub)
                dirty = True
                sent += 1
                # ✅ attempt（成功）
                if in_app_notification_id is not None:
                    db.add(
                        WebPushDelivery(
                            run_id=run_id,
                            in_app_notification_id=in_app_notification_id,
                            user_id=user_id,
                            subscription_id=sub.id,
                            status=WebPushDelivery.STATUS_SENT,
                            http_status=201,
                            attempted_at=now,
                        )
                    )
                    dirty = True
                logger.info("[webpush] ok user_id=%s sub_id=%s", user_id, sub.id)

            except WebPushException as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                body = None
                try:
                    body = getattr(getattr(e, "response", None), "text", None)
                except Exception:
                    body = None

                # ✅ 失効(410/404)は資産を無効化して幽霊送信を防ぐ
                if status in (404, 410):
                    sub.is_active = False
                    db.add(sub)
                    dirty = True
                    deactivated += 1

                    if in_app_notification_id is not None:
                        db.add(
                            WebPushDelivery(
                                run_id=run_id,
                                in_app_notification_id=in_app_notification_id,
                                user_id=user_id,
                                subscription_id=sub.id,
                                status=WebPushDelivery.STATUS_DEACTIVATED,
                                http_status=status,
                                attempted_at=now,
                            )
                        )
                        dirty = True

                    logger.info(
                        "[webpush] deactivated user_id=%s sub_id=%s status=%s",
                        user_id,
                        sub.id,
                        status,
                    )
                    continue

                # ✅ それ以外は failed
                failed += 1
                if in_app_notification_id is not None:
                    db.add(
                        WebPushDelivery(
                            run_id=run_id,
                            in_app_notification_id=in_app_notification_id,
                            user_id=user_id,
                            subscription_id=sub.id,
                            status=WebPushDelivery.STATUS_FAILED,
                            http_status=status,
                            error_summary=str(e)[:255],
                            attempted_at=now,
                        )
                    )
                    dirty = True

                logger.warning(
                    "[webpush] failed user_id=%s sub_id=%s status=%s err=%s body=%s",
                    user_id,
                    sub.id,
                    status,
                    e,
                    (body[:300] if isinstance(body, str) else body),
                )

            except Exception as e:
                # ✅ 予期せぬ例外でも attempt を残す（監査SSOTの防波堤）
                failed += 1
                if in_app_notification_id is not None:
                    db.add(
                        WebPushDelivery(
                            run_id=run_id,
                            in_app_notification_id=in_app_notification_id,
                            user_id=user_id,
                            subscription_id=sub.id,
                            status=WebPushDelivery.STATUS_FAILED,
                            http_status=None,
                            error_summary=str(e)[:255],
                            attempted_at=now,
                        )
                    )
                    dirty = True
                logger.exception(
                    "[webpush] unexpected error user_id=%s sub_id=%s err=%s",
                    user_id,
                    sub.id,
                    str(e)[:200],
                )

        if dirty:
            db.commit()

        return {"sent": sent, "failed": failed, "deactivated": deactivated}

    @staticmethod
    def send_for_notification(
        db: Session,
        *,
        user_id: int,
        notification: InAppNotification,
    ) -> dict:
        issued_at = int(WebPushSender._utcnow().timestamp())
        event_token = _make_event_token(
            user_id=user_id,
            notification_id=notification.id,
            run_id=notification.run_id,
            issued_at=issued_at,
        )

        payload = {
            "title": notification.title,
            "body": notification.body,
            "url": notification.deep_link,
            "deep_link": notification.deep_link,
            "notification_id": notification.id,
            "run_id": notification.run_id,
            "event_token": event_token,
        }
        return WebPushSender._send_payload(
            db,
            user_id=user_id,
            payload=payload,
            in_app_notification_id=notification.id,
            run_id=notification.run_id,
        )

    @staticmethod
    def send_debug(
        db: Session,
        *,
        user_id: int,
        title: str = "UNIPA Reminder",
        body: str = "Web Push テスト送信です",
        url: str = "/dashboard?tab=today",
    ) -> dict:
        issued_at = int(WebPushSender._utcnow().timestamp())
        event_token = _make_event_token(
            user_id=user_id,
            notification_id=None,
            run_id=None,
            issued_at=issued_at,
        )

        payload = {
            "title": title,
            "body": body,
            "url": url,
            "deep_link": url,
            "notification_id": None,
            "run_id": None,
            "event_token": event_token,
        }
        return WebPushSender._send_payload(db, user_id=user_id, payload=payload)