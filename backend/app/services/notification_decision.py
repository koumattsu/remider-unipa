# backend/app/services/notification_decision.py

from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class NotificationDecision:
    should_send: bool
    reason: str
    effective_offsets: list[int]
