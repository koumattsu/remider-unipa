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

def _delete_session_cookie(response: Response) -> None:
    # ① host-only cookie を消す
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path=getattr(settings, "SESSION_COOKIE_PATH", "/"),
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.SESSION_COOKIE_SECURE,
    )
    # ② domain付き cookie を消す（過去互換）
    if getattr(settings, "SESSION_COOKIE_DOMAIN", None):
        response.delete_cookie(
            key=settings.SESSION_COOKIE_NAME,
            path=getattr(settings, "SESSION_COOKIE_PATH", "/"),
            domain=settings.SESSION_COOKIE_DOMAIN,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            secure=settings.SESSION_COOKIE_SECURE,
        )

def _get_bearer_token(request: Request) -> Optional[str]:
    # ✅ Cookie が死ぬ環境向け：Authorization: Bearer <token> を許可
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    prefix = "Bearer "
    if not auth.startswith(prefix):
        return None
    token = auth[len(prefix):].strip()
    return token or None

async def get_current_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    # ✅ 0) Authorization を優先（cookieが送れない環境でも成立）
    session_token = _get_bearer_token(request)

    # 1) Cookie セッション（互換）
    if not session_token:
        session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if session_token:
        try:
            data = serializer.loads(session_token)

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

            # 互換：google_user_id が入ってるなら拾う（移行/事故復旧用）
            google_user_id = data.get("google_user_id")
            if google_user_id:
                user = db.query(User).filter(User.google_user_id == google_user_id).first()
                if not user:
                    raise HTTPException(status_code=401, detail="ユーザーが存在しません")
                return user

            raise HTTPException(status_code=401, detail="無効なセッションです")

        except (BadSignature, ValueError, TypeError):
            # Cookieは消しておく（Bearer の場合はフロント側で上書きされる）
            _delete_session_cookie(response)
            raise HTTPException(status_code=401, detail="無効なセッションです")

    # 2) CookieもBearerも無い場合のみ、開発用ダミーヘッダー
    if settings.DUMMY_AUTH_ENABLED:
        dummy_user_id = request.headers.get("X-Dummy-User-Id")
        if not dummy_user_id:
            raise HTTPException(status_code=401, detail="X-Dummy-User-Id が必要です（DUMMY_AUTH_ENABLED=true）")
        user_id = int(dummy_user_id)
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="ユーザーが存在しません")
        return user

    raise HTTPException(status_code=401, detail="認証が必要です")