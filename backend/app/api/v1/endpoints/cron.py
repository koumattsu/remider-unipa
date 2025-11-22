from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.services.notification import (
    get_tasks_due_in_hours,
    get_tasks_due_today_morning,
    mark_notification_as_sent,
)
from app.services.line_client import send_deadline_reminder

router = APIRouter()


@router.post("/daily")
async def run_daily_job(db: Session = Depends(get_db)):
    """
    定期実行ジョブ（Scheduler / cron 用）

    対応する通知：
    ✅ 3時間前通知
    ✅ 当日朝（8:00）通知

    - 完了済み(is_done=True)は除外
    - 通知済み(Logあり)は除外
    """

    # MVPではユーザー1人だけ固定
    user_id = 1
    line_user_id = "dummy_line_1"

    results = {
        "three_hours_before": 0,
        "morning": 0,
    }

    # ===========================
    # ① 3時間前通知
    # ===========================
    tasks_3h = get_tasks_due_in_hours(db, user_id=user_id, hours=3)

    if tasks_3h:
        await send_deadline_reminder(line_user_id=line_user_id, tasks=tasks_3h)

        # 通知済みログに記録
        for task in tasks_3h:
            mark_notification_as_sent(db, user_id, task.id, 3)

        results["three_hours_before"] = len(tasks_3h)

    # ===========================
    # ② 当日朝（8:00）通知
    # ===========================
    now = datetime.now()

    # 8:00〜8:10 の間だけ当日通知を実行
    if now.hour == 8 and 0 <= now.minute <= 10:
        tasks_today = get_tasks_due_today_morning(db, user_id=user_id)

        if tasks_today:
            await send_deadline_reminder(line_user_id=line_user_id, tasks=tasks_today)

            for task in tasks_today:
                mark_notification_as_sent(db, user_id, task.id, 0)

            results["morning"] = len(tasks_today)

    # ===========================
    # 結果
    # ===========================
    if results["three_hours_before"] == 0 and results["morning"] == 0:
        return {"notified": False, "detail": results}

    return {"notified": True, "detail": results}
