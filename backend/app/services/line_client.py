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
# メッセージ生成（3時間前通知用）
# ============================================
def _build_deadline_message(tasks: List[Task]) -> str:
    if not tasks:
        return "締切が近い課題はありません。"

    lines: list[str] = []
    lines.append("🔔【締切リマインダー】（3時間前）\n")

    for task in tasks:
        deadline_str = task.deadline.strftime("%Y/%m/%d %H:%M")
        lines.append(f"・{task.title}")
        lines.append(f"　科目: {task.course_name}")
        lines.append(f"　締切: {deadline_str}\n")

    return "\n".join(lines)


# ============================================
# メッセージ生成（朝8時のダイジェスト）
# ============================================
def _build_daily_digest_message(tasks: List[Task]) -> str:
    if not tasks:
        return "【UNIPAリマインダー】\n本日の締切課題はありません。"

    lines: list[str] = []
    lines.append("📘【本日の締切課題ダイジェスト】")
    lines.append(f"本日の課題数: {len(tasks)}\n")

    for task in tasks:
        deadline_str = task.deadline.strftime("%Y/%m/%d %H:%M")
        status = "⏰ 未完了" if not task.is_done else "✅ 完了"
        lines.append(f"・{status} {task.title}")
        lines.append(f"　科目: {task.course_name}")
        lines.append(f"　締切: {deadline_str}\n")

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
# 外部向け: 3時間前通知
# ============================================
async def send_deadline_reminder(line_user_id: str, tasks: List[Task]) -> None:
    if not tasks:
        return

    text = _build_deadline_message(tasks)
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
