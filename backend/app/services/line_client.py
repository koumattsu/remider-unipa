from typing import List
from app.models.task import Task
from app.core.config import settings


async def send_deadline_reminder(line_user_id: str, tasks: List[Task]) -> None:
    """
    指定ユーザーに締切リマインドのLINEメッセージを送る。
    
    ここではまだ実際のHTTPリクエストはダミーでよい（printでも可）。
    後からLINE Messaging API連携コードを差し替えられるように設計してほしい。
    
    Args:
        line_user_id: LINEユーザーID
        tasks: リマインド対象の課題リスト
    """
    if not tasks:
        return
    
    # TODO: 実際のLINE Messaging API連携を実装
    # 現時点ではダミー実装
    print(f"[LINE通知 ダミー] ユーザー {line_user_id} にリマインドを送信:")
    for task in tasks:
        print(f"  - {task.title} ({task.course_name}) - 締切: {task.deadline}")
    
    # 将来の実装例:
    # from linebot import LineBotApi
    # from linebot.models import TextSendMessage
    # 
    # line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
    # messages = [TextSendMessage(text=f"【課題リマインド】\n{task.title}\n締切: {task.deadline}") for task in tasks]
    # line_bot_api.push_message(line_user_id, messages)


async def send_daily_digest(line_user_id: str, tasks: List[Task]) -> None:
    """
    指定ユーザーに日次ダイジェストのLINEメッセージを送る。
    
    Args:
        line_user_id: LINEユーザーID
        tasks: 本日の課題リスト
    """
    if not tasks:
        print(f"[LINE通知 ダミー] ユーザー {line_user_id} への日次ダイジェスト: 課題はありません")
        return
    
    # TODO: 実際のLINE Messaging API連携を実装
    print(f"[LINE通知 ダミー] ユーザー {line_user_id} に日次ダイジェストを送信:")
    print(f"  本日の課題数: {len(tasks)}")
    for task in tasks:
        status = "✅ 完了" if task.is_done else "⏰ 未完了"
        print(f"  - {status} {task.title} ({task.course_name}) - 締切: {task.deadline}")

