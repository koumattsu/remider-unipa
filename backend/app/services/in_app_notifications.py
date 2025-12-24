# backend/app/services/in_app_notifications.py

from datetime import datetime
from typing import List
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

def make_inapp_records(user_id: int, tasks: List[Task], offset_hours: int, now_utc: datetime) -> List[InAppNotification]:
    title = build_inapp_title(offset_hours)
    body = build_inapp_body(tasks)
    recs: List[InAppNotification] = []
    for t in tasks:
        recs.append(
            InAppNotification(
                user_id=user_id,
                task_id=t.id,
                deadline_at_send=t.deadline,  # “送った瞬間の締切”として固定
                offset_hours=offset_hours,
                kind="task_reminder",
                title=title,
                body=body,  # まとめを全件に同じ本文で持たせる（UIはthread化せず簡単に）
                deep_link=TODAY_DEEPLINK,
                metadata=None,
            )
        )
    return recs
