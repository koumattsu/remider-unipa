# backend/app/services/webpush_sender.py

import json
import logging
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
    def _is_enabled_for_user(db: Session, user_id: int) -> bool:
        ns = (
            db.query(NotificationSetting)
            .filter(NotificationSetting.user_id == user_id)
            .one_or_none()
        )
        return bool(ns and ns.enable_webpush)

    @staticmethod
    def send_for_notification(
        db: Session,
        *,
        user_id: int,
        notification: InAppNotification,
    ) -> None:
        # ✅ ユーザーの許可（設定）を尊重
        if not WebPushSender._is_enabled_for_user(db, user_id):
            return

        # ✅ 端末資産（subscription）を取得
        subs = (
            db.query(WebPushSubscription)
            .filter(
                WebPushSubscription.user_id == user_id,
                WebPushSubscription.is_active.is_(True),
            )
            .all()
        )
        if not subs:
            return

        # ✅ イベント資産（InAppNotification）を配信
        payload = {
            "title": notification.title,
            "body": notification.body,
            "deep_link": notification.deep_link,
        }
        payload_json = json.dumps(payload, ensure_ascii=False)

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
                logger.info("[webpush] ok user_id=%s sub_id=%s", user_id, sub.id)

            except WebPushException as e:
                status = getattr(getattr(e, "response", None), "status_code", None)

                # ✅ 失効(410/404)は資産を無効化して幽霊送信を防ぐ
                if status in (404, 410):
                    sub.is_active = False
                    db.add(sub)
                    db.commit()
                    logger.info(
                        "[webpush] deactivated user_id=%s sub_id=%s status=%s",
                        user_id,
                        sub.id,
                        status,
                    )
                    continue

                logger.warning(
                    "[webpush] failed user_id=%s sub_id=%s status=%s err=%s",
                    user_id,
                    sub.id,
                    status,
                    e,
                )
