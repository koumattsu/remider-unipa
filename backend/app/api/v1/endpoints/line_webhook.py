# backend/app/api/v1/endpoints/line_webhook.py

from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/webhook")
async def handle_line_webhook(request: Request):
    """
    LINE Messaging API からのWebhookを受け取るエンドポイント（仮実装）

    今はとりあえず:
    - リクエストボディを print
    - 200 OK + {"status": "ok"} を返すだけ
    """
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")
    print("=== LINE webhook received ===")
    print(body_str)
    print("=============================")

    return {"status": "ok"}
