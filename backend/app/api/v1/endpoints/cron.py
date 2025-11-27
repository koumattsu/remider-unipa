# backend/app/api/v1/endpoints/cron.py

from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.task import Task
from app.models.notification_setting import NotificationSetting  # ★ 追加
from app.services.notification import (
    get_tasks_due_in_hours,
    get_tasks_due_today_morning,
    mark_notification_as_sent,
)
from app.services.line_client import (
    send_deadline_reminder,
    send_simple_text,
)

router = APIRouter()

from sqlalchemy import text

@router.post("/debug-migrate-notification-setting")
async def debug_migrate_notification_setting(db: Session = Depends(get_db)):
    """
    一度だけ実行する想定のマイグレーション用エンドポイント。
    Render本番の notification_settings テーブルに
    enable_morning_notification カラムを追加する。
    """
    try:
        db.execute(
            text(
                "ALTER TABLE notification_settings "
                "ADD COLUMN enable_morning_notification BOOLEAN NOT NULL DEFAULT 1;"
            )
        )
        db.commit()
        return {"status": "ok", "message": "column added"}
    except Exception as e:
        # すでにカラムがある場合などはここに来る
        return {"status": "error", "message": str(e)}



# ユーザーごとの通知設定を取得 or デフォルトで作成
def get_or_create_notification_setting(db: Session, user_id: int) -> NotificationSetting:
    setting = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.user_id == user_id)
        .first()
    )

    if setting is None:
        setting = NotificationSetting(
            user_id=user_id,
            reminder_offsets_hours=[3],       # デフォルト: 3時間前のみ
            daily_digest_time="08:00",        # デフォルト: 朝8時
            enable_morning_notification=True, # デフォルト: 朝通知ON
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
        return setting

    # 万が一どれか空なら補正しておく
    updated = False

    if not setting.reminder_offsets_hours:
        setting.reminder_offsets_hours = [3]
        updated = True

    if not setting.daily_digest_time:
        setting.daily_digest_time = "08:00"
        updated = True

    if setting.enable_morning_notification is None:
        setting.enable_morning_notification = True
        updated = True

    if updated:
        db.add(setting)
        db.commit()
        db.refresh(setting)

    return setting


@router.post("/daily")
async def run_daily_job(db: Session = Depends(get_db)):
    """
    定期実行ジョブ（Scheduler / GitHub Actions 用）

    対応する通知：
    - NotificationSetting.reminder_offsets_hours による「○時間前」通知
      （デフォルト: 3時間前）
    - NotificationSetting.daily_digest_time & enable_morning_notification による朝通知
      （デフォルト: 08:00 & ON）
    """

    now = datetime.now()

    results: Dict[str, int] = {
        "three_hours_before": 0,
        "morning": 0,
        "users_targeted": 0,
    }

    users = (
        db.query(User)
        .filter(User.line_user_id.isnot(None))
        .all()
    )

    for user in users:
        user_id = user.id
        line_user_id = user.line_user_id
        if not line_user_id:
            continue

        results["users_targeted"] += 1

        # ユーザーごとの設定取得
        setting = get_or_create_notification_setting(db, user_id=user_id)

        # ---------- ① 「○時間前」通知（3時間前ON/OFF含む） ----------
        offsets = setting.reminder_offsets_hours or []

        for offset in offsets:
            try:
                hours = int(offset)
            except (TypeError, ValueError):
                continue

            if hours <= 0:
                continue

            tasks = get_tasks_due_in_hours(db, user_id=user_id, hours=hours)
            if not tasks:
                continue

            await send_deadline_reminder(line_user_id=line_user_id, tasks=tasks)

            for task in tasks:
                mark_notification_as_sent(db, user_id, task.id, hours)

            if hours == 3:
                results["three_hours_before"] += len(tasks)
            else:
                key = f"offset_{hours}"
                results[key] = results.get(key, 0) + len(tasks)

        # ---------- ② 朝通知（enable_morning_notification でON/OFF） ----------
        try:
            digest_hour, digest_minute = map(int, setting.daily_digest_time.split(":"))
        except ValueError:
            digest_hour, digest_minute = 8, 0

        if (
            setting.enable_morning_notification                    # ★ フラグ
            and now.hour == digest_hour
            and abs(now.minute - digest_minute) <= 10             # 多少の遅延許容
        ):
            tasks_today = get_tasks_due_today_morning(db, user_id=user_id)
            if tasks_today:
                await send_deadline_reminder(line_user_id=line_user_id, tasks=tasks_today)
                for task in tasks_today:
                    # 0 = 朝通知
                    mark_notification_as_sent(db, user_id, task.id, 0)
                results["morning"] += len(tasks_today)

    notified = (results["three_hours_before"] > 0) or (results["morning"] > 0)

    return {"notified": notified, "detail": results}


# ここから下の debug 系は、君の元コードそのまま残してOK

@router.post("/debug-send")
async def debug_send(db: Session = Depends(get_db)):
    ...
    # （ここは君の元コードをそのまま使ってOK）

@router.get("/debug-users")
async def debug_users(db: Session = Depends(get_db)):
    ...
    # （元コードのまま）

@router.post("/debug-register-user")
async def debug_register_user(
    line_user_id: str,
    db: Session = Depends(get_db),
):
    ...
    # （元コードのまま）
