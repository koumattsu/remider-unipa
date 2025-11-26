# backend/app/api/v1/endpoints/line_webhook.py

import base64
import hashlib
import hmac
from typing import Any, Dict

from fastapi import APIRouter, Request, Header, HTTPException

from app.core.config import settings
from app.services import line_client  # ★ 追加：LINE返信用クライアント

router = APIRouter()


def verify_line_signature(body: bytes, signature: str | None) -> None:
    """
    LINE Messaging API の署名チェック。
    LINE_CHANNEL_SECRET が設定されている場合のみ検証する。
    """
    channel_secret = settings.LINE_CHANNEL_SECRET
    if not channel_secret:
        # 開発中に SECRET 未設定のままでも動くようにしておく
        print("[WARN] LINE_CHANNEL_SECRET not set. Skip signature verification.")
        return

    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature header")

    mac = hmac.new(
        channel_secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    )
    expected_signature = base64.b64encode(mac.digest()).decode("utf-8")

    if not hmac.compare_digest(expected_signature, signature):
        print("[ERROR] Invalid LINE signature")
        print("  expected:", expected_signature)
        print("  got     :", signature)
        raise HTTPException(status_code=400, detail="Invalid signature")


@router.post("/webhook")
async def handle_line_webhook(
    request: Request,
    x_line_signature: str | None = Header(default=None),
):
    """
    LINE Messaging API からの Webhook 受信エンドポイント。

    - 署名検証（LINE_CHANNEL_SECRET 使用）
    - events をパースして type / userId をログ出力
    - テキストメッセージが来たらオウム返し
    """
    body_bytes = await request.body()

    # 署名検証
    verify_line_signature(body_bytes, x_line_signature)

    # JSONとしてパース
    body_json: Dict[str, Any] = await request.json()

    print("=== LINE webhook received ===")
    print(body_json)
    print("=============================")

    events = body_json.get("events", [])
    for event in events:
        event_type = event.get("type")
        reply_token = event.get("replyToken")
        source = event.get("source", {})
        user_id = source.get("userId")

        print(f"[EVENT] type={event_type}, user_id={user_id}")

        # メッセージイベント（テキスト）のときだけオウム返し
        if event_type == "message":
            message = event.get("message", {})
            if message.get("type") == "text":
                text = message.get("text", "")
                if reply_token:
                    reply_text = f"『{text}』って言った？ UNIPAリマインダーBotです👋"
                    await line_client._push_text_message(  # 既存の共通関数を使う
                        line_user_id=user_id,
                        text=reply_text,
                    )

        # 友だち追加イベントなど
        if event_type == "follow":
            print(f"[FOLLOW] user_id={user_id}")
            # ★ 将来ここで user_id を DB に保存する
            #   例: user_service.save_line_user(user_id)

    return {"status": "ok"}
