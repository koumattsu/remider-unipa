# backend/app/core/time.py
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ✅ JST を SSOT として提供（全コードで統一）
JST = ZoneInfo("Asia/Tokyo")


def utcnow() -> datetime:
    """UTCの aware datetime を返す（テスト注入したいときは呼び出し側で差し替え）"""
    return datetime.now(timezone.utc)
