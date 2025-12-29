# backend/app/services/outcome_decision.py

from __future__ import annotations
from datetime import datetime
from typing import Literal

Outcome = Literal["done", "missed"]

def decide_task_outcome(task, *, at_utc: datetime) -> Outcome:
    """
    ✅ Outcome 判定 SSOT（純関数）
    - 「締切到達時点で完了していたか」を返す
    - DB操作・commit・副作用は一切持たない

    現行仕様（TaskOutcomeLog の comment と一致）:
    - done if completed_at <= deadline else missed
    """
    deadline = getattr(task, "deadline", None)
    completed_at = getattr(task, "completed_at", None)

    if deadline is None or completed_at is None:
        return "missed"

    return "done" if completed_at <= deadline else "missed"
