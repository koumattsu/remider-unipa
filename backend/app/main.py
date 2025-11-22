from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.api import api_router
from app.db.base import init_db

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
)


@app.on_event("startup")
def on_startup() -> None:
    """アプリ起動時に一度だけDB初期化."""
    init_db()


# CORS設定
app.add_middleware(
    CORSMiddleware,
    # ローカル開発用：どこからでも許可（file:// → null も含めて通す）
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# APIルーター
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": "UniPA Reminder App API",
        "version": settings.APP_VERSION,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
