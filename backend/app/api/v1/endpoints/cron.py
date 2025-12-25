# backend/app/api/v1/endpoints/cron.py

from datetime import datetime, timedelta, timezone, time
from typing import Dict
from fastapi import APIRouter, Depends, Query
import re
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.session import get_db
from app.models.user import User
from app.models.task import Task
from app.models.in_app_notification import InAppNotification
from app.models.weekly_task import WeeklyTask
from app.models.notification_setting import NotificationSetting  # ★ 追加
from app.models.task_outcome_log import TaskOutcomeLog
from app.services.notification import (
    collect_notification_candidates,
    to_utc,
)
from app.services.line_client import (
    send_deadline_reminder,
    send_simple_text,
    send_daily_digest,
)
from app.services.weekly_materialize import materialize_weekly_tasks_for_user
from app.services.webpush_sender import WebPushSender

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
            reminder_offsets_hours=[1],       # デフォルト: 1時間前のみ
            daily_digest_time="08:00",        # デフォルト: 朝8時
            enable_morning_notification=True, # デフォルト: 朝通知ON
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
        return setting

    # 万が一どれか空なら補正しておく
    updated = False

    if setting.enable_webpush is None:
        setting.enable_webpush = False
        updated = True

    if not setting.reminder_offsets_hours:
        setting.reminder_offsets_hours = [1]
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

def _format_task_lines(tasks: list[Task]) -> str:
    # 要件：タイトル/締切/内容（箇条書き）
    # ここでは body に「箇条書き」を入れる
    lines: list[str] = []
    for t in tasks:
        # deadline は timezone aware 前提
        dl = t.deadline.astimezone(JST).strftime("%m/%d %H:%M") if t.deadline else "-"
        title = t.title or "(no title)"
        course = t.course_name or ""
        if course:
            lines.append(f"・{title}（{course} / {dl}）")
        else:
            lines.append(f"・{title}（{dl}）")
    return "\n".join(lines)

def _upsert_in_app_notification(
    db: Session,
    user_id: int,
    task: Task,
    deadline_at_send_utc: datetime,
    offset_hours: int,
    kind: str,
    title: str,
    body: str,
    deep_link: str,
) -> InAppNotification | None:
    exists = (
        db.query(InAppNotification.id)
        .filter(InAppNotification.user_id == user_id)
        .filter(InAppNotification.task_id == task.id)
        .filter(InAppNotification.deadline_at_send == deadline_at_send_utc)
        .filter(InAppNotification.offset_hours == offset_hours)
        .first()
    )
    if exists:
        return None

    n = InAppNotification(
        user_id=user_id,
        task_id=task.id,
        deadline_at_send=deadline_at_send_utc,
        offset_hours=offset_hours,
        kind=kind,
        title=title,
        body=body,
        deep_link=deep_link,
    )
    db.add(n)
    return n

@router.post("/debug-migrate-task-auto-notify-flag")
async def debug_migrate_task_auto_notify_flag(db: Session = Depends(get_db)):
    """
    一度だけ実行する想定:
    tasks テーブルに auto_notify_disabled_by_done カラムを追加する。
    """
    try:
        db.execute(text(
            "ALTER TABLE tasks "
            "ADD COLUMN IF NOT EXISTS auto_notify_disabled_by_done BOOLEAN NOT NULL DEFAULT false;"
        ))

        db.commit()
        return {"status": "ok", "message": "column added"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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

    # ✅ 朝通知を送っていい時間帯（JST）
    is_morning_window = time(5, 0) <= now_jst.time() <= time(10, 0)

    print("=== run_daily_job ===")
    print("[daily] build=2025-12-21-a")
    print("  now_utc:", now_utc)
    print("  now_jst:", now_jst)

    results: Dict[str, int] = {
        "three_hours_before": 0,
        "morning": 0,
        "users_targeted": 0,
    }

    users = db.query(User).all()

    VALID_LINE_UID = re.compile(r"^U[0-9a-f]{32}$")

    for user in users:
        user_id = user.id
        line_user_id = user.line_user_id  # NoneでもOK
        results["users_targeted"] += 1

        # 通知設定取得
        setting = get_or_create_notification_setting(db, user_id=user_id)

        # ★ weekly_tasks -> tasks の生成入口を materialize に統一（向こう7日分）
        materialize_weekly_tasks_for_user(db, user_id=user_id, days=7)

        # ✅ OutcomeLog：締切到達時点の結果を1回だけ確定保存（通知とは独立）
        evaluate_task_outcomes(db, user_id=user_id, now_utc=now_utc)

        raw_offsets = setting.reminder_offsets_hours
        offsets_hours = raw_offsets or []

        # ✅ backend側で無料/有料制約を保証（唯一の真実）
        # free: 1時間前のみ（朝は別ロジック）
        if getattr(user, "plan", "free") == "free":
            offsets_hours = [1]
        # int化 + <=0除外 + 重複排除（順序維持）
        normalized_offsets: list[int] = []
        seen: set[int] = set()
        for x in offsets_hours:
            try:
                h = int(x)
            except (TypeError, ValueError):
                continue
            if h <= 0:
                continue
            if h in seen:
                continue
            seen.add(h)
            normalized_offsets.append(h)

        print("[daily] user_id=", user_id,
            "raw_offsets=", raw_offsets,
            "offsets_hours=", offsets_hours,
            "normalized_offsets=", normalized_offsets,
            "enable_morning=", setting.enable_morning_notification,
            "digest_time=", setting.daily_digest_time)

        # ✅ 判定も送信も「正規化後 offset」で統一
        cands = collect_notification_candidates(
            db,
            user_id=user_id,
            offsets_hours=normalized_offsets,
        )
        for h in normalized_offsets:
            print("[daily] user_id=", user_id, "due_count@", h, "=", len(cands.due_in_hours.get(h, [])))

        # ---------- ① 「○時間前」通知 ----------
        # ✅ 送信ループも正規化済みのoffsetで回す（判定とズレないようにする）
        offsets = normalized_offsets

        for hours in offsets:
            tasks_3h = cands.due_in_hours.get(hours, [])
            if not tasks_3h:
                continue

            # ✅ まずベル通知を作る（無料の最低保証）
            created_inapps: list[InAppNotification] = []
            for task in tasks_3h:
                deadline_at_send = to_utc(task.deadline)
                dl_jst = task.deadline.astimezone(JST).strftime("%m/%d %H:%M") if task.deadline else "-"
                n = _upsert_in_app_notification(
                    db=db,
                    user_id=user_id,
                    task=task,
                    deadline_at_send_utc=deadline_at_send,
                    offset_hours=hours,
                    kind="task_reminder",
                    title=f"締切まで残り約{hours}時間",
                    body=f"締切: {dl_jst}\n{_format_task_lines([task])}",
                    deep_link="/#/dashboard?tab=today",
                )
                if n:
                    created_inapps.append(n)

                # ✅ イベント資産（InAppNotification）はここで確実に永続化
            if created_inapps:
                db.commit()

            # ✅ WebPush（無料/有料共通・設定ONのときだけ）
            if setting.enable_webpush:
                for n in created_inapps:
                    try:
                        WebPushSender.send_for_notification(
                            db=db,
                            user_id=user_id,
                            notification=n,
                        )
                    except Exception as e:
                        print("[CRON] webpush failed:", str(e))
                    except Exception as e:
                        # 失敗したらログは残さない（次回リトライ）
                        print("[CRON] webpush failed:", str(e))
            # ✅ LINE（有料のみ）
            try:
                if user.plan != "free" and line_user_id:
                    try:
                        await send_deadline_reminder(
                            line_user_id=line_user_id,
                            tasks=tasks_3h,
                            hours=hours,
                        )
                    except Exception as e:
                        print("[CRON] send_deadline_reminder failed:", str(e))
                        # LINE失敗でもWebPush成功分は残すので continue しない
            except Exception as e:
                print("[CRON] send_deadline_reminder failed:", str(e))

            if hours == 3:
                results["three_hours_before"] += len(tasks_3h)
            else:
                key = f"offset_{hours}"
                results[key] = results.get(key, 0) + len(tasks_3h)
      

        # ---------- ② 当日タスクの「朝通知」（時間条件を外す） ----------
        if setting.enable_morning_notification and is_morning_window:
            tasks_today = cands.morning

            # ✅ 朝ダイジェストもベルに残す（無料の最低保証）
            created_morning: list[InAppNotification] = []
            for task in tasks_today:
                deadline_at_send = to_utc(task.deadline)
                dl_jst = task.deadline.astimezone(JST).strftime("%m/%d %H:%M") if task.deadline else "-"
                n = _upsert_in_app_notification(
                    db=db,
                    user_id=user_id,
                    task=task,
                    deadline_at_send_utc=deadline_at_send,
                    offset_hours=0,
                    kind="morning_digest",
                    title="今日締切の課題まとめ",
                    body=f"締切: {dl_jst}\n{_format_task_lines([task])}",
                    deep_link="/#/dashboard?tab=today",
                )
                if n:
                    created_morning.append(n)

            if created_morning:
                db.commit()

            # ✅ WebPush（無料/有料共通）
            if setting.enable_webpush:
                for n in created_morning:
                    try:
                        WebPushSender.send_for_notification(
                            db=db,
                            user_id=user_id,
                            notification=n,
                        )
                    except Exception as e:
                        print("[CRON] webpush failed:", str(e))
            if tasks_today:
                # ✅ LINE（有料のみ・朝ダイジェスト）
                if user.plan != "free" and line_user_id:
                    try:
                        await send_daily_digest(
                            line_user_id=line_user_id,
                            tasks=tasks_today,
                        )
                    except Exception as e:
                        print("[CRON] send_daily_digest failed:", str(e))

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
    ok = 0
    ng = 0

    # テスト用メッセージ（固定）
    msg = "🔧 デバッグ通知テスト\nUNIPAリマインダーのLINE送信テストです。"

    for user in users:
        line_user_id = user.line_user_id
        if not line_user_id:
            ng += 1
            results.append({
                "user_id": user.id,
                "status": "skipped",
                "reason": "line_user_id is empty",
            })
            continue

        # フォーマット不正はスキップ（line_clientも同様にwarnしてreturnするが、結果に残す）
        if not (isinstance(line_user_id, str) and re.fullmatch(r"U[0-9a-f]{32}", line_user_id)):
            ng += 1
            results.append({
                "user_id": user.id,
                "line_user_id": line_user_id,
                "status": "skipped",
                "reason": "invalid line_user_id format (expected U + 32 hex chars)",
            })
            continue
        try:
            await send_simple_text(line_user_id, msg)
            ok += 1
            results.append({
                "user_id": user.id,
                "line_user_id": line_user_id,
                "status": "sent",
            })
        except Exception as e:
            ng += 1
            # line_client.py は RuntimeError に status/body を入れて投げてくれてるので repr(e) で十分追える
            results.append({
                "user_id": user.id,
                "line_user_id": line_user_id,
                "status": "error",
                "error": repr(e),
            })

    return {
        "message": "debug-send executed",
        "sent_ok": ok,
        "sent_ng": ng,
        "count": len(results),
        "results": results,
    }

@router.get("/debug-users")
async def debug_users(db: Session = Depends(get_db)):
    """
    デバッグ用:
    User テーブルの中身をざっくり確認するエンドポイント。
    line_user_id を持っているかどうかを中心に見る。
    """
    users = db.query(User).all()
    result = []
    for u in users:
        result.append(
            {
                "id": u.id,
                "line_user_id": u.line_user_id,
                "display_name": getattr(u, "display_name", None),
                "university": getattr(u, "university", None),
                "plan": getattr(u, "plan", None),
            }
        )
    return {
        "count": len(result),
        "users": result,
    }

@router.get("/debug-task")
async def debug_task(
    task_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    デバッグ用:
    tasks API が認証必須でも、DB上の task を確認できる観測点。
    通知が来ない時に「task の user_id / deadline / should_notify」を確定する。
    """
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        return {"found": False, "task_id": task_id}

    return {
        "found": True,
        "task": {
            "id": t.id,
            "user_id": getattr(t, "user_id", None),
            "title": getattr(t, "title", None),
            "course_name": getattr(t, "course_name", None),
            "deadline": str(getattr(t, "deadline", None)),
            "should_notify": getattr(t, "should_notify", None),
            "is_done": getattr(t, "is_done", None),
            "auto_notify_disabled_by_done": getattr(t, "auto_notify_disabled_by_done", None),
        },
    }

@router.get("/debug-tasks-recent")
async def debug_tasks_recent(
    user_id: int = 2,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    qs = (
        db.query(Task)
        .filter(Task.user_id == user_id)
        .order_by(Task.deadline.desc())
        .limit(limit)
        .all()
    )
    return {
        "user_id": user_id,
        "count": len(qs),
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "deadline": str(t.deadline),
                "should_notify": t.should_notify,
                "is_done": t.is_done,
            }
            for t in qs
        ],
    }

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
        if not re.fullmatch(r"U[0-9a-f]{32}", line_user_id):
            return {"created": False, "error": "invalid line_user_id format (expected U + 32 hex chars)"}
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

def evaluate_task_outcomes(db: Session, user_id: int, now_utc: datetime) -> int:
    """
    user_id の tasks について、
    deadline <= now_utc かつ (user_id, task_id, deadline) の OutcomeLog が無いものを評価して保存する。

    outcome 定義（設計合意）:
    - completed_at があり completed_at <= deadline → done
    - それ以外 → missed

    戻り値: 今回追加したログ件数
    """
    # ① 締切到達済みタスク（deadlineはtimezone aware想定）
    due_tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id)
        .filter(Task.deadline.isnot(None))
        .filter(Task.deadline <= now_utc)
        .all()
    )
    if not due_tasks:
        return 0

    created = 0

    for t in due_tasks:
        deadline = t.deadline

        # ② すでに評価済み（同じ締切に対して二重保存しない）
        exists = (
            db.query(TaskOutcomeLog.id)
            .filter(
                and_(
                    TaskOutcomeLog.user_id == user_id,
                    TaskOutcomeLog.task_id == t.id,
                    TaskOutcomeLog.deadline == deadline,
                )
            )
            .first()
        )
        if exists:
            continue

        # ③ outcome 判定（completed_at が deadline までにあれば done）
        completed_at = t.completed_at
        outcome = "done" if (completed_at is not None and completed_at <= deadline) else "missed"

        db.add(
            TaskOutcomeLog(
                user_id=user_id,
                task_id=t.id,
                deadline=deadline,      # tasks.deadline をコピーして固定
                outcome=outcome,
                evaluated_at=now_utc,   # cron実行時刻（UTC）
            )
        )
        created += 1

    if created:
        db.commit()

    return created
