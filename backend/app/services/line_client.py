# backend/app/services/line_client.py

from __future__ import annotations

from typing import List
import os
import httpx

from app.models.task import Task
from app.core.config import settings

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

# ============================================
# アクセストークン取得（settings or env）
# ============================================
def _get_line_access_token() -> str | None:
    token = getattr(settings, "LINE_CHANNEL_ACCESS_TOKEN", None)
    if not token:
        token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    return token or None

# ============================================
# メッセージ生成（◯時間前通知用）
# ============================================
def _build_daily_digest_message(tasks: List[Task]) -> str:
    # 今日締切がゼロ件のとき
    if not tasks:
        return "🌅 今日締切の課題はありません。\n余裕のある一日にしよう✨"

    lines: list[str] = []

    # タイトルと件数
    lines.append("🌅 今日締切の課題まとめ")
    lines.append(f"本日の締切は {len(tasks)}件あります。\n")

    # 課題一覧
    for i, task in enumerate(tasks, start=1):
        deadline_str = task.deadline.strftime("%m/%d %H:%M")
        lines.append(f"{i}. 【科目】{task.course_name}")
        lines.append(f"   【課題】{task.title}")
        lines.append(f"   【締切】{deadline_str}")

        if i != len(tasks):
            lines.append("")

    # 一言
    lines.append("")
    lines.append("今日のうちに片付けて、明日以降をラクにしよう💪")

    return "\n".join(lines)


# ============================================
# メッセージ生成（朝のダイジェスト）
# ============================================
def _build_daily_digest_message(tasks: List[Task]) -> str:
    # 今日締切がゼロ件のとき
    if not tasks:
        return "🌅 今日締切の課題はありません。\n余裕のある一日にしよう✨"

    lines: list[str] = []

    # タイトルと件数
    lines.append("🌅 今日締切の課題まとめ")
    lines.append(f"本日の締切は {len(tasks)}件あります。\n")

    # 課題一覧
    for i, task in enumerate(tasks, start=1):
        deadline_str = task.deadline.strftime("%m/%d %H:%M")
        lines.append(f"{i}. {task.title}")
        lines.append(f"   科目: {task.course_name}")
        lines.append(f"   締切: {deadline_str}\n")

    # 一言
    lines.append("今日のうちに片付けて、明日以降をラクにしよう💪")

    return "\n".join(lines)

def _build_deadline_message(tasks, hours: int) -> str:
    """
    〇時間前通知用のメッセージ文を組み立てる
    """
    lines = [f"⏰ 締切まで残り約 {hours} 時間の課題があります！\n"]

    for task in tasks:
        lines.append(f"・{task.title}")

    return "\n".join(lines)



# ============================================
# 実際の LINE送信（Push API）
# ============================================
async def _push_text_message(line_user_id: str, text: str) -> None:
    access_token = _get_line_access_token()

    if not access_token:
        print("[LINE通知: ダミー出力] →", line_user_id)
        print(text)
        return

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    body = {
        "to": line_user_id,
        "messages": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(LINE_PUSH_URL, headers=headers, json=body)

    if resp.status_code >= 400:
        print("[LINE ERROR]", resp.status_code, resp.text)
    else:
        print("[LINE PUSH OK]", resp.status_code)


# ============================================
# 外部向け: ◯時間前通知
# ============================================
async def send_deadline_reminder(
    line_user_id: str,
    tasks: List[Task],
    hours: int,
) -> None:
    if not tasks:
        return

    text = _build_deadline_message(tasks, hours)
    await _push_text_message(line_user_id, text)


# ============================================
# 外部向け: 朝8時通知
# ============================================
async def send_daily_digest(line_user_id: str, tasks: List[Task]) -> None:
    text = _build_daily_digest_message(tasks)
    await _push_text_message(line_user_id, text)


# ============================================
# 任意テキスト送信用（デバッグ用）
# ============================================
async def send_simple_text(line_user_id: str, text: str) -> None:
    await _push_text_message(line_user_id, text)
