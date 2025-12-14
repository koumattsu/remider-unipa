# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.api import api_router
from app.api.v1.endpoints.line_webhook import router as line_webhook_router
from app.db.base import Base, engine

def create_tables_if_needed() -> None:
    """
    ローカル(SQLite)開発ではテーブルを自動作成してOK。
    本番(PostgreSQL)では起動時 create_all は事故の元なので実行しない。
    """
    db_url = settings.DATABASE_URL or ""
    if db_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)

def get_application() -> FastAPI:
    # SQLiteのときだけ作成
    create_tables_if_needed()

    app = FastAPI(
        title="UNIPA Reminder Backend",
        description="UNIPA / Moodle 課題リマインダー用バックエンド（FastAPI）",
        version="0.1.0",
    )

    # --- CORS 設定 ---
    origins = getattr(settings, "BACKEND_CORS_ORIGINS", None)
    if not origins:
        origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://unipa-reminder-frontend.onrender.com",  # 実在するなら
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(line_webhook_router, prefix="/line", tags=["line"])

    @app.get("/")
    async def root():
        return {"message": "UNIPA Reminder Backend is running"}

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app


app = get_application()
