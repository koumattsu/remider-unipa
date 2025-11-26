# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.api import api_router
from app.api.v1.endpoints.line_webhook import router as line_webhook_router
from app.db.base import Base, engine  # ★ engine を base からインポート


def create_tables() -> None:
    """
    アプリ起動時にDBテーブルを自動作成するヘルパー。
    既にテーブルがある場合は何もしない。
    """
    Base.metadata.create_all(bind=engine)


def get_application() -> FastAPI:
    # まずテーブルを作成（なければ作る）
    create_tables()

    app = FastAPI(
        title="UNIPA Reminder Backend",
        description="UNIPA / Moodle 課題リマインダー用バックエンド（FastAPI）",
        version="0.1.0",
    )

    # --- CORS 設定 ---
    if getattr(settings, "BACKEND_CORS_ORIGINS", None):
        origins = settings.BACKEND_CORS_ORIGINS
    else:
        origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 既存の v1 API
    app.include_router(api_router, prefix="/api/v1")

    # 追加: LINE Webhook (/line/webhook)
    app.include_router(line_webhook_router, prefix="/line", tags=["line"])

    @app.get("/")
    async def root():
        return {"message": "UNIPA Reminder Backend is running"}

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app


app = get_application()
