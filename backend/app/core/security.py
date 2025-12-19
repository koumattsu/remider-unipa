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
    # 1) まず Cookie セッションがあればそれを優先（本番安定のため）
    session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_cookie:
        try:
            data = serializer.loads(session_cookie)
            user_id = int(data["user_id"])
        except (BadSignature, KeyError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無効なセッションです",
            )
    else:
        # 2) Cookieが無い場合のみ、開発用ダミーヘッダーを使う
        if settings.DUMMY_AUTH_ENABLED:
            dummy_user_id = request.headers.get("X-Dummy-User-Id")
            if not dummy_user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="X-Dummy-User-Id が必要です（DUMMY_AUTH_ENABLED=true）",
                )
            user_id = int(dummy_user_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="認証が必要です",
            )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザーが存在しません",
        )
    return user



def require_auth(func):
    """認証が必要なエンドポイント用デコレータ（簡易版）"""
    return func
