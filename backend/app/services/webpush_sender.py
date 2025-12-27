# backend/app/services/webpush_sender.py

import json
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from pywebpush import webpush, WebPushException
from app.core.config import settings
from app.models.notification_setting import NotificationSetting
from app.models.webpush_subscription import WebPushSubscription
from app.models.in_app_notification import InAppNotification

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
                logger.info("[webpush] ok user_id=%s sub_id=%s", user_id, sub.id)

            except WebPushException as e:
                status = getattr(getattr(e, "response", None), "status_code", None)

                # ✅ 失効(410/404)は資産を無効化して幽霊送信を防ぐ
                if status in (404, 410):
                    sub.is_active = False
                    db.add(sub)
                    dirty = True
                    deactivated += 1
                    logger.info(
                        "[webpush] deactivated user_id=%s sub_id=%s status=%s",
                        user_id,
                        sub.id,
                        status,
                    )
                    continue

                failed += 1
                logger.warning(
                    "[webpush] failed user_id=%s sub_id=%s status=%s err=%s",
                    user_id,
                    sub.id,
                    status,
                    e,
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
        # ✅ sw.js 側が url を見る想定なので url も入れる（deep_link も残す）
        payload = {
            "title": notification.title,
            "body": notification.body,
            "url": notification.deep_link,
            "deep_link": notification.deep_link,
        }
        return WebPushSender._send_payload(db, user_id=user_id, payload=payload)

    @staticmethod
    def send_debug(
        db: Session,
        *,
        user_id: int,
        title: str = "UNIPA Reminder",
        body: str = "Web Push テスト送信です",
        url: str = "/dashboard?tab=today", 
    ) -> dict:
        payload = {"title": title, "body": body, "url": url, "deep_link": url}
        return WebPushSender._send_payload(db, user_id=user_id, payload=payload)

