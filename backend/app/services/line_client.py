# app/services/line_client.py

from __future__ import annotations

from typing import List
import os

import httpx

from app.models.task import Task
from app.core.config import settings

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def _get_line_access_token() -> str | None:
    """
    設定から LINE チャネルアクセストークンを取得。
    なければ環境変数からもフォールバック。
    """
    token = getattr(settings, "LINE_CHANNEL_ACCESS_TOKEN", None)
    if not token:
        token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    return token or None


def _build_deadline_message(tasks: List[Task]) -> str:
    """
    明日締切の課題一覧メッセージテキストを生成。
    """
    if not tasks:
        return "明日締切の課題はありません。"

    lines: list[str] = []
    lines.append("【UNIPAリマインダー】明日締切の課題一覧")
    lines.append("")

    for task in tasks:
        deadline_str = task.deadline.strftime("%Y/%m/%d %H:%M")
        lines.append(f"・{task.title}")
        lines.append(f"　科目: {task.course_name}")
        lines.append(f"　締切: {deadline_str}")
        lines.append("")

    lines.append("がんばろう💪")
    return "\n".join(lines)


def _build_daily_digest_message(tasks: List[Task]) -> str:
    """
    日次ダイジェスト用のメッセージテキストを生成。
    """
    if not tasks:
        return "本日の課題はありません。"

    lines: list[str] = []
    lines.append("【UNIPAリマインダー】本日の課題ダイジェスト")
    lines.append(f"本日の課題数: {len(tasks)}")
    lines.append("")

    for task in tasks:
        status = "✅ 完了" if task.is_done else "⏰ 未完了"
        deadline_str = task.deadline.strftime("%Y/%m/%d %H:%M")
        lines.append(f"・{status} {task.title}")
        lines.append(f"　科目: {task.course_name}")
        lines.append(f"　締切: {deadline_str}")
        lines.append("")

    return "\n".join(lines)


async def _push_text_message(line_user_id: str, text: str) -> None:
    """
    LINE Messaging API の push メッセージを送信する共通処理。
    アクセストークンが無ければダミーモード（print）で動作。
    """
    access_token = _get_line_access_token()

    # アクセストークンが無いときはダミーモード（コンソール出力のみ）
    if not access_token:
        print("[LINE通知 ダミー] 宛先:", line_user_id)
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

    # 2xx 以外なら例外を投げておく（cron側のログで気づけるように）
    resp.raise_for_status()


async def send_deadline_reminder(line_user_id: str, tasks: List[Task]) -> None:
    """
    指定ユーザーに「明日締切」の課題リマインドを送る。

    - LINE_CHANNEL_ACCESS_TOKEN（settings or env）が未設定の時:
        → 既存と同じようにコンソールへダミーログ出力のみ
    - 設定されている時:
        → 実際に LINE Messaging API の push メッセージを送信
    """
    if not tasks:
        # 何もなければ何も送らない（従来どおり）
        return

    text = _build_deadline_message(tasks)
    await _push_text_message(line_user_id, text)


async def send_daily_digest(line_user_id: str, tasks: List[Task]) -> None:
    """
    指定ユーザーに日次ダイジェストのLINEメッセージを送る。

    - 課題が0件のときも、「課題はありません」とメッセージを送る仕様。
    """
    if not tasks:
        # 課題0件のときもメッセージ送る設計（元コードの挙動を継承）
        text = "【UNIPAリマインダー】本日の課題ダイジェスト\n本日の課題はありません。"
        await _push_text_message(line_user_id, text)
        return

    text = _build_daily_digest_message(tasks)
    await _push_text_message(line_user_id, text)
