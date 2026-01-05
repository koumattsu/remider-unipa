# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.api.v1.endpoints.line_webhook import router as line_webhook_router
from app.db.base import init_db

def create_tables_if_needed() -> None:
    # ✅ 起動時DDLは本番で事故りやすいのでデフォOFF（必要時のみON）
    if settings.AUTO_INIT_DB:
        init_db()

def get_application() -> FastAPI:
    create_tables_if_needed()

    app = FastAPI(
        title="UNIPA Reminder Backend",
        description="UNIPA / Moodle 課題リマインダー用バックエンド（FastAPI）",
        version="0.1.0",
    )

    # ✅ config.py の validator で list[str] になってる前提
    origins = settings.CORS_ORIGINS

    # 念のため FRONTEND_URL も許可に入れておく（入ってなければ追加）
    frontend_origin = (settings.FRONTEND_URL or "").strip().rstrip("/")
    if frontend_origin and frontend_origin not in origins:
        origins = [*origins, frontend_origin]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(line_webhook_router, prefix="/line", tags=["line"])

    @app.get("/health")
    async def health_check():
        return {"ok": True}

    @app.get("/build")
    async def build_info():
        # ここは落ちてもサービス死なない（ヘルスとは分離）
        return {
            "env": settings.ENV,
            "build": settings.BUILD_ID,
            "version": settings.APP_VERSION,
        }
    return app

app = get_application()