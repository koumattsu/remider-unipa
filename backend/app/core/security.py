# backend/app/core/security.py

from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from itsdangerous import URLSafeSerializer, BadSignature
from app.db.session import get_db
from app.models.user import User
from app.core.config import settings

serializer = URLSafeSerializer(
    settings.SESSION_SECRET,
    salt="unipa-session",
)

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)

    # 1) Cookie セッション
    if session_cookie:
        try:
            data = serializer.loads(session_cookie)

            # ✅ 新方式：line_user_id を唯一の真実にする
            line_user_id = data.get("line_user_id")
            if line_user_id:
                user = (
                    db.query(User)
                    .filter(User.line_user_id == line_user_id)
                    .first()
                )
                if not user:
                    raise HTTPException(status_code=401, detail="ユーザーが存在しません")
                return user

            # 🟡 互換：旧方式 user_id が入ってるcookieも一応読める
            user_id = data.get("user_id")
            if user_id is None:
                raise HTTPException(status_code=401, detail="無効なセッションです")
            user_id = int(user_id)

        except (BadSignature, ValueError, TypeError):
            raise HTTPException(status_code=401, detail="無効なセッションです")

    else:
        # 2) Cookieが無い場合のみ、開発用ダミーヘッダー
        if settings.DUMMY_AUTH_ENABLED:
            dummy_user_id = request.headers.get("X-Dummy-User-Id")
            if not dummy_user_id:
                raise HTTPException(status_code=401, detail="X-Dummy-User-Id が必要です（DUMMY_AUTH_ENABLED=true）")
            user_id = int(dummy_user_id)
        else:
            raise HTTPException(status_code=401, detail="認証が必要です")

    # 旧方式 fallback（互換）
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="ユーザーが存在しません")
    return user

def require_auth(func):
    """認証が必要なエンドポイント用デコレータ（簡易版）"""
    return func
