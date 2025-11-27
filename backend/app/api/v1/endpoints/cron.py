# backend/app/api/v1/endpoints/cron.py

from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.task import Task
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


@router.post("/daily")
async def run_daily_job(db: Session = Depends(get_db)):
    """
    定期実行ジョブ（Scheduler / cron 用）

    対応する通知：
    ✅ 3時間前通知
    ✅ 当日朝（8:00）通知
    """

    now = datetime.now()

    results: Dict[str, int] = {
        "three_hours_before": 0,
        "morning": 0,
        "users_targeted": 0,
    }

    # LINE連携済みユーザーを全取得
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

        # ① 3時間前通知
        tasks_3h = get_tasks_due_in_hours(db, user_id=user_id, hours=3)
        if tasks_3h:
            await send_deadline_reminder(line_user_id=line_user_id, tasks=tasks_3h)
            for task in tasks_3h:
                mark_notification_as_sent(db, user_id, task.id, 3)
            results["three_hours_before"] += len(tasks_3h)

        # ② 当日朝（8:00）通知
        if now.hour == 8 and 0 <= now.minute <= 10:
            tasks_today = get_tasks_due_today_morning(db, user_id=user_id)
            if tasks_today:
                await send_deadline_reminder(line_user_id=line_user_id, tasks=tasks_today)
                for task in tasks_today:
                    # 0 = 朝通知
                    mark_notification_as_sent(db, user_id, task.id, 0)
                results["morning"] += len(tasks_today)

    notified = (results["three_hours_before"] > 0) or (results["morning"] > 0)

    return {"notified": notified, "detail": results}


@router.post("/debug-send")
async def debug_send(db: Session = Depends(get_db)):
    """
    デバッグ用エンドポイント。

    - dummy_line_1 ではない LINE連携済みユーザーを1人取得
    - そのユーザーのタスクを全部取って送信テスト
    """

    user = (
        db.query(User)
        .filter(
            User.line_user_id.isnot(None),
            User.line_user_id != "dummy_line_1",  # ★ ダミー除外
        )
        .order_by(User.id.desc())  # ★ 新しいユーザー優先
        .first()
    )

    if not user:
        return {"detail": "実ユーザー(line_user_id != 'dummy_line_1')がいません"}

    line_user_id = user.line_user_id

    tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id)
        .all()
    )

    if not tasks:
        await send_simple_text(line_user_id, "UNIPAリマインダー: デバッグテストメッセージです。")
        return {
            "detail": {
                "user_id": user.id,
                "line_user_id": line_user_id,
                "tasks_count": 0,
                "message": "no tasks. simple debug text sent.",
            }
        }

    await send_deadline_reminder(line_user_id=line_user_id, tasks=tasks)

    return {
        "detail": {
            "user_id": user.id,
            "line_user_id": line_user_id,
            "tasks_count": len(tasks),
            "message": "debug reminder sent.",
        }
    }


@router.get("/debug-users")
async def debug_users(db: Session = Depends(get_db)):
    """
    デバッグ用:
    Userテーブルの中身をざっくり確認するためのエンドポイント。
    """
    users = db.query(User).all()

    return {
        "count": len(users),
        "users": [
            {
                "id": u.id,
                "line_user_id": u.line_user_id,
            }
            for u in users
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
    user = (
        db.query(User)
        .filter(User.line_user_id == line_user_id)
        .first()
    )

    created = False
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

    return {
        "created": created,
        "user": {
            "id": user.id,
            "line_user_id": user.line_user_id,
        },
    }
