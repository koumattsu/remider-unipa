# backend/app/core/security.py

from typing import Optional
from fastapi import Request, Response, HTTPException, status, Depends
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
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)

    # 1) Cookie セッション
    if session_cookie:
        try:
            data = serializer.loads(session_cookie)

            # ✅ 新方式：user_id を唯一の真実にする（無料でも成立）
            user_id = data.get("user_id")
            if user_id is not None:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if not user:
                    raise HTTPException(status_code=401, detail="ユーザーが存在しません")
                return user

            # 互換：古い/別方式で line_user_id が入ってるなら拾う（移行のため）
            line_user_id = data.get("line_user_id")
            if line_user_id:
                user = db.query(User).filter(User.line_user_id == line_user_id).first()
                if not user:
                    raise HTTPException(status_code=401, detail="ユーザーが存在しません")
                return user

            raise HTTPException(status_code=401, detail="無効なセッションです")

        except (BadSignature, ValueError, TypeError):
                        response.delete_cookie(
                            key=settings.SESSION_COOKIE_NAME,
                            path=getattr(settings, "SESSION_COOKIE_PATH", "/"),
                            domain=getattr(settings, "SESSION_COOKIE_DOMAIN", None),
                            samesite=settings.SESSION_COOKIE_SAMESITE,
                            secure=settings.SESSION_COOKIE_SECURE,
                        )
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

    # DUMMY_AUTH のみ user_id を許可（本番では DUMMY_AUTH_ENABLED=false で封じる）
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="ユーザーが存在しません")
    return user

def require_auth(func):
    """認証が必要なエンドポイント用デコレータ（簡易版）"""
    return func
