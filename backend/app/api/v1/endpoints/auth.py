# backend/app/api/v1/endpoints/auth.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import secrets
import httpx
from urllib.parse import urlencode
from itsdangerous import URLSafeSerializer
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse
from app.core.config import settings

router = APIRouter(tags=["auth"])

def _frontend_base_url() -> str:
    base = settings.FRONTEND_URL or "http://localhost:5173"
    base = base.strip()
    if not (base.startswith("http://") or base.startswith("https://")):
        # ここが壊れてるとChromeでERR_INVALID_REDIRECTになる
        raise HTTPException(status_code=500, detail=f"Invalid FRONTEND_URL: {base}")
    return base.rstrip("/")

def _serializer():
    return URLSafeSerializer(settings.SESSION_SECRET, salt="unipa-session")

def _make_cookie_opts():
    return {
        "httponly": True,
        "secure": settings.SESSION_COOKIE_SECURE,
        "samesite": settings.SESSION_COOKIE_SAMESITE,
    }

def _make_oauth_state_cookie_opts():
    # LINE -> backend の「トップレベル遷移」で確実に返ってくる設定
    # SESSION_COOKIE_* とは分ける（ここがポイント）
    return {
        "httponly": True,
        "secure": True,     # Render本番は https 前提
        "samesite": "lax",  # OAuth state は Lax が安定
        "path": "/",        # 念のため明示
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)

@router.get("/line/authorize")
async def line_authorize():
    if not settings.LINE_LOGIN_CHANNEL_ID or not settings.LINE_LOGIN_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="LINE Login settings are missing")

    state = secrets.token_urlsafe(24)

    params = {
        "response_type": "code",
        "client_id": settings.LINE_LOGIN_CHANNEL_ID,
        "redirect_uri": settings.LINE_LOGIN_REDIRECT_URI,
        "state": state,
        "scope": "profile openid",
    }
    url = "https://access.line.me/oauth2/v2.1/authorize"

    redirect_url = f"{url}?{urlencode(params)}"
    resp = RedirectResponse(url=redirect_url, status_code=302)

    # state をcookieに保存（CSRF対策）
    resp.set_cookie("line_login_state", state, max_age=600, **_make_oauth_state_cookie_opts())
    return resp

@router.get("/line/callback")
async def line_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    saved_state = request.cookies.get("line_login_state")

    if not code or not state or not saved_state or state != saved_state:
        # 次の試行で詰まらないよう、先に消す
        resp = RedirectResponse(url=_frontend_base_url() + "/login", status_code=302)
        resp.delete_cookie("line_login_state", path="/")
        return resp

    # code -> access_token
    token_url = "https://api.line.me/oauth2/v2.1/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.LINE_LOGIN_REDIRECT_URI,
        "client_id": settings.LINE_LOGIN_CHANNEL_ID,
        "client_secret": settings.LINE_LOGIN_CHANNEL_SECRET,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        token_res = await client.post(token_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        if token_res.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_res.text}")
        token_json = token_res.json()
        access_token = token_json.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access_token returned")

        # LINE profile 取得
        prof_res = await client.get(
            "https://api.line.me/v2/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if prof_res.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Profile fetch failed: {prof_res.text}")
        prof = prof_res.json()

    line_user_id = prof.get("userId")
    display_name = prof.get("displayName") or "LINE User"
    if not line_user_id:
        raise HTTPException(status_code=400, detail="LINE userId missing")

    # user upsert
    user = db.query(User).filter(User.line_user_id == line_user_id).first()
    if not user:
        user = User(
            line_user_id=line_user_id,
            display_name=display_name,
            university="",
            plan="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # 表示名更新したいなら
        user.display_name = display_name
        db.commit()

    # セッションcookie発行（user_id を署名して入れる）
    session_token = _serializer().dumps({"user_id": user.id})

    redirect_to = _frontend_base_url() + "/dashboard"
    resp = RedirectResponse(url=redirect_to, status_code=302)

    cookie_opts = _make_cookie_opts()
    resp.set_cookie(settings.SESSION_COOKIE_NAME, session_token, max_age=60 * 60 * 24 * 30, **cookie_opts)
    # state cookie消す
    resp.delete_cookie("line_login_state",  path="/")
    return resp

@router.post("/logout")
async def logout():
    resp = RedirectResponse(url=_frontend_base_url() + "/login", status_code=302)
    resp.delete_cookie(settings.SESSION_COOKIE_NAME, **_make_cookie_opts())
    return resp
