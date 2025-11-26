# backend/app/api/v1/endpoints/line_webhook.py

import base64
import hashlib
import hmac
from fastapi import APIRouter, Request, Header, HTTPException

from app.core.config import settings

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
    LINE Messaging API からの Webhook 受信エンドポイント（暫定版）

    - 署名検証（LINE_CHANNEL_SECRET 使用）
    - ボディをログに出して {"status": "ok"} を返すだけ
    """
    body_bytes = await request.body()

    # 署名検証
    verify_line_signature(body_bytes, x_line_signature)

    body_str = body_bytes.decode("utf-8")
    print("=== LINE webhook received ===")
    print(body_str)
    print("=============================")

    return {"status": "ok"}
