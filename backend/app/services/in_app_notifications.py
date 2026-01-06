# backend/app/services/in_app_notifications.py

from datetime import datetime
from typing import List, Optional
from app.models.task import Task
from app.models.in_app_notification import InAppNotification

TODAY_DEEPLINK = "/#/dashboard?tab=today"

def build_inapp_title(offset_hours: int) -> str:
    return "朝通知" if offset_hours == 0 else f"{offset_hours}時間前"

def build_inapp_body(tasks: List[Task]) -> str:
    # “長すぎたらうざい”要件：箇条書きで短く
    # 例：• タイトル（締切）- メモ先頭
    lines = []
    for t in tasks:
        deadline = t.deadline.isoformat()
        memo = (t.memo or "").strip()
        memo_short = (memo[:40] + "…") if len(memo) > 40 else memo
        if memo_short:
            lines.append(f"• {t.title}（{deadline}）- {memo_short}")
        else:
            lines.append(f"• {t.title}（{deadline}）")
    return "\n".join(lines)

def make_inapp_records(
    user_id: int,
    tasks: List[Task],
    offset_hours: int,
    now_utc: datetime,
    *,
    run_id: Optional[int] = None,
) -> List[InAppNotification]:
    title = build_inapp_title(offset_hours)
    body = build_inapp_body(tasks)
    if not tasks:
        return []

    # ✅ 1回の通知 = 1レコード（= 1 Push）
    # deadline_at_send は「この通知が代表する締切」として最短締切を採用（監査・集計の軸になる）
    earliest_deadline = min(t.deadline for t in tasks if t.deadline is not None)

    task_ids = [int(t.id) for t in tasks if t.id is not None]
    extra = {
        "task_ids": task_ids,
        "task_count": len(task_ids),
        "generated_at": now_utc.isoformat(),
    }

    return [
        InAppNotification(
            user_id=user_id,
            task_id=None,  # ✅ アプリ内通知UI前提を捨てる（OS Push 用のメッセージ資産）
            deadline_at_send=earliest_deadline,
            offset_hours=offset_hours,
            kind="task_reminder",
            title=title,
            body=body,
            deep_link=TODAY_DEEPLINK,
            extra=extra,
            run_id=run_id,
        )
    ]
