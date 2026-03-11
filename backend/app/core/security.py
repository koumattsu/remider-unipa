# backend/app/core/security.py

from typing import Optional
from fastapi import Request, Response, HTTPException, Depends
from sqlalchemy.orm import Session
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.db.session import get_db
from app.models.user import User
from app.core.config import settings

serializer = URLSafeTimedSerializer(
    settings.SESSION_SECRET,
    salt="unipa-session",
)


def _delete_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path=getattr(settings, "SESSION_COOKIE_PATH", "/"),
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.SESSION_COOKIE_SECURE,
    )
    if getattr(settings, "SESSION_COOKIE_DOMAIN", None):
        response.delete_cookie(
            key=settings.SESSION_COOKIE_NAME,
            path=getattr(settings, "SESSION_COOKIE_PATH", "/"),
            domain=settings.SESSION_COOKIE_DOMAIN,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            secure=settings.SESSION_COOKIE_SECURE,
        )


def _get_bearer_token(request: Request) -> Optional[str]:
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
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not session_token:
        session_token = _get_bearer_token(request)

    if session_token:
        try:
            data = serializer.loads(
                session_token,
                max_age=settings.SESSION_MAX_AGE_SECONDS,
            )

            user_id = data.get("user_id")
            if user_id is not None:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if not user:
                    raise HTTPException(status_code=401, detail="ユーザーが存在しません")
                return user

            line_user_id = data.get("line_user_id")
            if line_user_id:
                user = db.query(User).filter(User.line_user_id == line_user_id).first()
                if not user:
                    raise HTTPException(status_code=401, detail="ユーザーが存在しません")
                return user

            google_user_id = data.get("google_user_id")
            if google_user_id:
                user = db.query(User).filter(User.google_user_id == google_user_id).first()
                if not user:
                    raise HTTPException(status_code=401, detail="ユーザーが存在しません")
                return user

            raise HTTPException(status_code=401, detail="無効なセッションです")

        except SignatureExpired:
            _delete_session_cookie(response)
            raise HTTPException(status_code=401, detail="セッションの有効期限が切れています")
        except (BadSignature, ValueError, TypeError):
            _delete_session_cookie(response)
            raise HTTPException(status_code=401, detail="無効なセッションです")

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