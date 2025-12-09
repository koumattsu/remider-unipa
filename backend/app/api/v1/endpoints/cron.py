# backend/app/api/v1/endpoints/cron.py

from datetime import datetime, timedelta, timezone
from typing import Dict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.task import Task
from app.models.weekly_task import WeeklyTask
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

def ensure_today_tasks_from_weekly(db: Session, user_id: int) -> None:
    """
    そのユーザーの WeeklyTask から、
    「今日分の Task レコード」を自動生成する。

    すでに同じ title / course_name / deadline の Task があれば作らない。
    """
    # 今日の日付（JST）と曜日 (0=月〜6=日)
    today_jst = datetime.now(JST).date()
    today_weekday = today_jst.weekday()

    # 対象ユーザーの有効な WeeklyTask 一覧
    templates = (
        db.query(WeeklyTask)
        .filter(
            WeeklyTask.user_id == user_id,
            WeeklyTask.is_active == True,  # noqa: E712
        )
        .all()
    )

    for tpl in templates:
        # DB上の weekday は 0=月〜6=日 を想定
        # 「今日の曜日」のテンプレだけ今日分を作る
        if tpl.weekday != today_weekday:
            continue

        hour = tpl.time_hour or 0
        minute = tpl.time_minute or 0

        # JST基準の締切を naive datetime で作る
        # （DB では「JSTとして解釈される naive」として保存）
        deadline = datetime(
            year=today_jst.year,
            month=today_jst.month,
            day=today_jst.day,
            hour=hour,
            minute=minute,
        )

        # すでに同じ Task があればスキップ（重複防止）
        existing = (
            db.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.title == tpl.title,
                Task.course_name == tpl.course_name,
                Task.deadline == deadline,
            )
            .first()
        )
        if existing:
            continue

        new_task = Task(
            user_id=user_id,
            title=tpl.title,
            course_name=tpl.course_name,
            memo=tpl.memo,
            deadline=deadline,
            should_notify=True,
            is_done=False,
        )
        db.add(new_task)

    db.commit()


@router.post("/daily")
async def run_daily_job(db: Session = Depends(get_db)):
    """
    定期実行ジョブ（Scheduler / GitHub Actions 用）

    - 「○時間前」通知：reminder_offsets_hours に従って毎回チェック
    - 「当日タスクの朝通知」：get_tasks_due_today_morning に任せる（時間条件は外し、1日1回だけLogで制御）
    """

    # 内部の基準はUTC、ログ表示はJST
    now_utc = datetime.now(timezone.utc)
    now_jst = now_utc.astimezone(JST)

    print("=== run_daily_job ===")
    print("  now_utc:", now_utc)
    print("  now_jst:", now_jst)

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

        # 通知設定取得
        setting = get_or_create_notification_setting(db, user_id=user_id)

        # ★ 追加：今日分の WeeklyTask から Task を自動生成
        ensure_today_tasks_from_weekly(db, user_id=user_id)

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

            # 3時間前などのまとめ通知
            await send_deadline_reminder(
                line_user_id=line_user_id,
                tasks=tasks_3h,
                hours=hours,
            )

            for task in tasks_3h:
                # offset=hours でログ（3, 24, 1 など）
                mark_notification_as_sent(db, user_id, task.id, hours)

            if hours == 3:
                results["three_hours_before"] += len(tasks_3h)
            else:
                key = f"offset_{hours}"
                results[key] = results.get(key, 0) + len(tasks_3h)

        # ---------- ② 当日タスクの「朝通知」（時間条件を外す） ----------
        if setting.enable_morning_notification:
            tasks_today = get_tasks_due_today_morning(db, user_id=user_id)

            if tasks_today:
                # 当日タスクのダイジェスト（1日1回だけ送られるイメージ）
                await send_daily_digest(line_user_id=line_user_id, tasks=tasks_today)

                for task in tasks_today:
                    # offset=0 を「当日朝送った」ログとして扱う
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
