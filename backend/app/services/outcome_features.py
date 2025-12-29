from __future__ import annotations

import hmac
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.task import Task


FEATURE_VERSION = "v1"


def _hmac_sha256(text: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), text.encode("utf-8"), hashlib.sha256).hexdigest()


def extract_outcome_features(task: Task) -> dict:
    """
    特徴量抽出SSOT（v1）
    - 生テキストは保持しない
    - deadline由来と構造フラグ中心
    - course_nameは HMAC で匿名化（同一文字列は同一hashになる）
    """
    jst = ZoneInfo("Asia/Tokyo")
    d = task.deadline.astimezone(jst)

    title_len = len(task.title or "")
    if title_len <= 20:
        title_len_bucket = "0-20"
    elif title_len <= 60:
        title_len_bucket = "21-60"
    else:
        title_len_bucket = "61+"

    # course_name は匿名化（復元不能。secret漏洩を前提にしない）
    # もし将来 "courseは保存しない" にするならここを削るだけで済むよう分離しておく
    secret = getattr(settings, "FEATURE_HASH_SECRET", None) or settings.SECRET_KEY
    course_hash = _hmac_sha256(task.course_name or "", secret)

    return {
        "deadline_dow_jst": int(d.weekday()),          # 0=Mon..6
        "deadline_hour_jst": int(d.hour),             # 0..23
        "deadline_is_weekend": bool(d.weekday() >= 5),
        "title_len_bucket": title_len_bucket,
        "has_memo": bool(task.memo),
        "is_weekly_task": bool(task.weekly_task_id is not None),
        "course_hash": course_hash,
    }
