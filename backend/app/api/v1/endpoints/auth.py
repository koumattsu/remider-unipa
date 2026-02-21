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
from app.models.notification_setting import NotificationSetting  # ✅ 追加（パスは実ファイルに合わせて）
from app.schemas.user import UserResponse
from app.core.config import settings
from uuid import uuid4
from fastapi.responses import JSONResponse

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
    opts = {
        "httponly": True,
        "secure": settings.SESSION_COOKIE_SECURE,
        "samesite": settings.SESSION_COOKIE_SAMESITE,
        "path": settings.SESSION_COOKIE_PATH,
    }
    # ✅ 事故防止：Domain は付けない（host-only cookie に固定）
    # Render / Cloudflare / onrender サブドメインで Domain mis-match が起きると
    # 「保存されてるのに送られない」事故になるため
    return opts

def _make_oauth_state_cookie_opts():
    # LINE -> backend の「トップレベル遷移」で確実に返ってくる設定
    # SESSION_COOKIE_* とは分ける（ここがポイント）
    return {
        "httponly": True,
        # dev(http://localhost) でも動くよう固定しない
        "secure": settings.SESSION_COOKIE_SECURE,
        # OAuth callback はトップレベルGETなので Lax が最も安定
        "samesite": "lax",
        "path": "/",        # 念のため明示
    }

@router.post("/guest")
async def guest_login():
    # ✅ ゲストログイン廃止（最終方針）
    # - 旧フロント/古いSW/手動リクエストが残っていても事故らないように
    # - DBにGuestが増殖して資産価値を汚さないように
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Guest login has been discontinued. Please login with LINE or Google.",
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)

@router.get("/line/authorize")
async def line_authorize():
    if not settings.LINE_LOGIN_CHANNEL_ID or not settings.LINE_LOGIN_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="LINE Login settings are missing")

    state = secrets.token_urlsafe(24)
    redirect_uri = settings.LINE_LOGIN_REDIRECT_URI

    params = {
        "response_type": "code",
        "client_id": settings.LINE_LOGIN_CHANNEL_ID,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "profile openid",
    }
    url = "https://access.line.me/oauth2/v2.1/authorize"

    redirect_url = f"{url}?{urlencode(params)}"
    resp = RedirectResponse(url=redirect_url, status_code=302)

    # state をcookieに保存（CSRF対策）
    resp.set_cookie("line_login_state", state, max_age=600, **_make_oauth_state_cookie_opts())
    return resp

@router.get("/google/authorize")
async def google_authorize(request: Request):
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth settings are missing")

    state = secrets.token_urlsafe(24)

    # ✅ SSOT: 実際の公開URLから callback を生成（envミスで壊れない）
    redirect_uri = str(request.url_for("google_callback"))

    params = {
        "response_type": "code",
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth"
    redirect_url = f"{url}?{urlencode(params)}"

    resp = RedirectResponse(url=redirect_url, status_code=302)
    resp.set_cookie("google_login_state", state, max_age=600, **_make_oauth_state_cookie_opts())
    return resp

@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    saved_state = request.cookies.get("google_login_state")

    if not code or not state or not saved_state or state != saved_state:
        resp = RedirectResponse(url=_frontend_base_url() + "/#/login", status_code=302)
        resp.delete_cookie("google_login_state", path="/")
        return resp

    token_url = "https://oauth2.googleapis.com/token"
    # ✅ authorize と同一の redirect_uri を使う（OAuth契約）
    redirect_uri = str(request.url_for("google_callback"))

    data = {
        "code": code,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        token_res = await client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_res.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_res.text}")

        token_json = token_res.json()
        id_token = token_json.get("id_token")
        if not id_token:
            raise HTTPException(status_code=400, detail=f"id_token missing: {token_res.text}")

        # ✅ 最小diffの検証：tokeninfo で id_token を検証して sub を取得
        info_res = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
        )
        if info_res.status_code != 200:
            raise HTTPException(status_code=400, detail=f"tokeninfo failed: {info_res.text}")

        info = info_res.json()
        aud = info.get("aud")
        sub = info.get("sub")
        name = info.get("name") or info.get("email") or "Google User"

        if aud != settings.GOOGLE_OAUTH_CLIENT_ID:
            raise HTTPException(status_code=400, detail="Invalid token audience")
        if not sub:
            raise HTTPException(status_code=400, detail="Google sub missing")

    # user upsert（google_user_id）
    user = db.query(User).filter(User.google_user_id == sub).first()
    if not user:
        user = User(
            google_user_id=sub,
            display_name=name,
            university="",
            plan="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.display_name = name
        db.commit()

    # NotificationSetting 自動修復（LINEと同じ）
    ns = db.query(NotificationSetting).filter(NotificationSetting.user_id == user.id).first()
    if not ns:
        ns = NotificationSetting(
            user_id=user.id,
            reminder_offsets_hours=[3],
            daily_digest_time="08:00",
            enable_morning_notification=True,
            enable_webpush=False,
        )
        db.add(ns)
        db.commit()

    session_token = _serializer().dumps({
        "user_id": user.id,
        "google_user_id": sub,  # ✅ 監査/互換用（security.pyはuser_id優先なので影響なし）
    })

    redirect_to = _frontend_base_url() + "/#/dashboard"
    resp = RedirectResponse(url=redirect_to, status_code=302)

    resp.set_cookie(
        settings.SESSION_COOKIE_NAME,
        session_token,
        max_age=60 * 60 * 24 * 30,
        **_make_cookie_opts(),
    )

    resp.delete_cookie("google_login_state", path="/")
    return resp

@router.get("/line/callback")
async def line_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    saved_state = request.cookies.get("line_login_state")
    redirect_uri = settings.LINE_LOGIN_REDIRECT_URI

    if not code or not state or not saved_state or state != saved_state:
        # 次の試行で詰まらないよう、先に消す
        resp = RedirectResponse(url=_frontend_base_url() + "/#/login", status_code=302)
        resp.delete_cookie("line_login_state", path="/")
        return resp

    # code -> access_token
    token_url = "https://api.line.me/oauth2/v2.1/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
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
            raise HTTPException(
                status_code=400,
                detail=f"Token exchange failed: {token_res.text} (redirect_uri={redirect_uri!r})"
            )

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
        user.display_name = display_name
        db.commit()

    # ✅ NotificationSetting を必ず1行持たせる（欠損自動修復）
    ns = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.user_id == user.id)
        .first()
    )
    if not ns:
        ns = NotificationSetting(
            user_id=user.id,
            reminder_offsets_hours=[3],
            daily_digest_time="08:00",
            enable_morning_notification=True,
            enable_webpush=False,
        )
        db.add(ns)
        db.commit()

    session_token = _serializer().dumps({
        "user_id": user.id,          # ✅ 唯一の真実（無料でも成立）
        "line_user_id": line_user_id # ✅ 互換/監査用（なくてもOK）
    })

    redirect_to = _frontend_base_url() + "/#/dashboard"
    resp = RedirectResponse(url=redirect_to, status_code=302)

    cookie_opts = _make_cookie_opts()
    resp.set_cookie(settings.SESSION_COOKIE_NAME, session_token, max_age=60 * 60 * 24 * 30, **cookie_opts)
    # state cookie消す
    resp.delete_cookie("line_login_state",  path="/")
    return resp

@router.post("/logout")
async def logout():
    resp = RedirectResponse(url=_frontend_base_url() + "/#/login", status_code=302)

    # ① host-only cookie を消す
    resp.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path=settings.SESSION_COOKIE_PATH,
    )

    # ② domain 付き cookie を消す（過去互換）
    if settings.SESSION_COOKIE_DOMAIN:
        resp.delete_cookie(
            key=settings.SESSION_COOKIE_NAME,
            path=settings.SESSION_COOKIE_PATH,
            domain=settings.SESSION_COOKIE_DOMAIN,
        )

    return resp

@router.get("/logout")
async def logout_get():
    return await logout()
