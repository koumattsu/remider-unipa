# backend/app/api/v1/endpoints/cron.py

from datetime import datetime, timedelta, timezone
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
    send_daily_digest,
)

router = APIRouter()

# 日本時間(JST)のタイムゾーン
JST = timezone(timedelta(hours=9))

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
    """

    # ✅ 日本時間(JST)の現在時刻を使う
    now_jst = datetime.now(JST)
    print("=== run_daily_job ===")
    print("  now_jst:", now_jst)


    results: Dict[str, int] = {
        "three_hours_before": 0,
        "morning": 0,
        "users_targeted": 0,
    }

    # ★★ 追加：絶対に初期化しておく（UnboundLocalError対策）
    tasks_today = []
    tasks_3h = []

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

        # 通知設定取得
        setting = get_or_create_notification_setting(db, user_id=user_id)

        # ---------- ① 「○時間前」通知 ----------
        offsets = setting.reminder_offsets_hours or []

        for offset in offsets:
            try:
                hours = int(offset)
            except (TypeError, ValueError):
                continue

            if hours <= 0:
                continue

            tasks_3h = get_tasks_due_in_hours(db, user_id=user_id, hours=hours)
            if not tasks_3h:
                continue

            await send_deadline_reminder(
                line_user_id=line_user_id,
                tasks=tasks_3h,
                hours=hours,
            )

            for task in tasks_3h:
                mark_notification_as_sent(db, user_id, task.id, hours)

            if hours == 3:
                results["three_hours_before"] += len(tasks_3h)
            else:
                key = f"offset_{hours}"
                results[key] = results.get(key, 0) + len(tasks_3h)

        # ---------- ② 朝通知 ----------
        try:
            digest_hour, digest_minute = map(int, setting.daily_digest_time.split(":"))
        except ValueError:
            digest_hour, digest_minute = 8, 0

        if (
            setting.enable_morning_notification
            # ✅ JSTベースで「daily_digest_time ±10分」のときだけ送る
           and now_jst.hour == digest_hour
           and abs(now_jst.minute - digest_minute) <= 10
        ):
            tasks_today = get_tasks_due_today_morning(db, user_id=user_id)

            if tasks_today:
                await send_daily_digest(line_user_id=line_user_id, tasks=tasks_today)

                for task in tasks_today:
                    mark_notification_as_sent(db, user_id, task.id, 0)

                results["morning"] += len(tasks_today)

    notified = (results["three_hours_before"] > 0) or (results["morning"] > 0)

    return {"notified": notified, "detail": results}


# ここから下の debug 系は、君の元コードそのまま残してOK
@router.post("/debug-send")
async def debug_send(db: Session = Depends(get_db)):
    """
    デバッグ用:
    現在登録されているユーザー全員にテストメッセージを送る。
    LINE Messaging API の動作確認に使用。
    """
    users = (
        db.query(User)
        .filter(User.line_user_id.isnot(None))
        .all()
    )

    results = []

    for user in users:
        if not user.line_user_id:
            continue

        # テスト用メッセージ
        msg = "🔧 デバッグ通知テスト\nUNIPAリマインダーのLINE送信テストです。"

        # 実際に1件送信
        await send_simple_text(user.line_user_id, msg)

        results.append({
            "user_id": user.id,
            "line_user_id": user.line_user_id,
            "status": "sent"
        })

    return {
        "message": "debug-send executed",
        "count": len(results),
        "results": results,
    }


@router.get("/debug-users")
async def debug_users(db: Session = Depends(get_db)):
    ...
    # （元コードのまま）

@router.post("/debug-register-user")
async def debug_register_user(
    line_user_id: str,
    db: Session = Depends(get_db),
):
    """
    デバッグ用:
    手動で User を1件登録 or 取得する。
    - すでに存在する line_user_id ならそのユーザーを返す
    - 無ければ新規作成する
    ※ display_name / university / plan にデフォルトを入れて、
      NOT NULL 制約で落ちないようにしている。
    """

    try:
        # 既存ユーザー検索
        user = (
            db.query(User)
            .filter(User.line_user_id == line_user_id)
            .first()
        )

        created = False

        # なければ新規作成
        if not user:
            user = User(
                line_user_id=line_user_id,
                display_name="LINEユーザー",
                university="未設定",
                plan="free",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            created = True

        # ★ 必ず dict を return する（None を返さない）
        return {
            "created": created,
            "user": {
                "id": user.id,
                "line_user_id": user.line_user_id,
            },
        }

    except Exception as e:
        # 例外が出ても null を返さないようにする
        db.rollback()
        return {
            "created": False,
            "error": str(e),
        }
