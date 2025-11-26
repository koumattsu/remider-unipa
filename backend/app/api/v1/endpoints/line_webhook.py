# backend/app/api/v1/endpoints/line_webhook.py

import base64
import hashlib
import hmac
from typing import Any, Dict

from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db          # ★ いつもの get_db（パス違ったらここだけ直せばOK）
from app.models.user import User
from app.services import line_client

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


def get_or_create_user_by_line_id(
    db: Session,
    line_user_id: str,
    display_name: str | None = None,
) -> User:
    """
    line_user_id から User を取得。いなければ作成して返す。
    display_name は LINE側からまだ取っていないので、とりあえず仮の名前を入れておく。
    """
    user = db.query(User).filter(User.line_user_id == line_user_id).first()
    if user:
        return user

    # display_name は NOT NULL なので、None のときは仮名を入れておく
    if not display_name:
        display_name = "LINEユーザー"

    user = User(
        line_user_id=line_user_id,
        display_name=display_name,
        university=None,
        plan="free",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"[USER] created new user: id={user.id}, line_user_id={user.line_user_id}")
    return user


@router.post("/webhook")
async def handle_line_webhook(
    request: Request,
    x_line_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),   # ★ DB セッションをDI
):
    print("🔥 NEW WEBHOOK VERSION RUNNING 🔥")

    """
    LINE Messaging API からの Webhook 受信エンドポイント。

    - 署名検証（LINE_CHANNEL_SECRET 使用）
    - events をパースして type / userId をログ出力
    - User を users テーブルに保存（なければ作成）
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
        line_user_id = source.get("userId")

        print(f"[EVENT] type={event_type}, line_user_id={line_user_id}")

        user: User | None = None
        if line_user_id:
            # ここで DB に users レコードを確実に作る / 取得する
            user = get_or_create_user_by_line_id(db, line_user_id=line_user_id)

        # メッセージイベント（テキスト）のときだけオウム返し
        if event_type == "message":
            message = event.get("message", {})
            if message.get("type") == "text":
                text = message.get("text", "")
                if reply_token and line_user_id:
                    reply_text = f"『{text}』って言った？ UNIPAリマインダーBotです👋"
                    # 返信（reply）は replyToken を使うのが正道だけど、
                    # ここでは既存の push 用クライアントを流用してもOK。
                    await line_client._push_text_message(
                        line_user_id=line_user_id,
                        text=reply_text,
                    )

        # 友だち追加イベントなど
        if event_type == "follow":
            print(f"[FOLLOW] line_user_id={line_user_id}, user_id_in_db={getattr(user, 'id', None)}")
            # 将来: ここで「初回挨拶メッセージ」や「大学選択フロー」などを送る

    return {"status": "ok"}
