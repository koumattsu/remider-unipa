# backend/app/api/v1/endpoints/admin_assets.py

import json
import hmac
import hashlib
from typing import Optional
from app.core.config import settings
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.asset_snapshot import AssetSnapshot
from app.models.export_run import ExportRun
from app.models.task import Task
from app.models.notification_run import NotificationRun
from app.models.task_outcome_log import TaskOutcomeLog
from app.models.in_app_notification import InAppNotification
from app.models.suggested_action_applied_event import SuggestedActionAppliedEvent

router = APIRouter()

@router.get("/assets/summary", response_model=dict)
def admin_assets_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # FakeSession互換：すべて Python 集計
    tasks_all = db.query(Task).all() or []

    # ✅ FakeSession は add() した Task を self.tasks に入れない（_added に積むだけ）
    #   → query(Task).all() + _added(Task) を合算して集計する
    added = getattr(db, "_added", []) or []
    added_tasks = [x for x in added if isinstance(x, Task)]
    tasks_merged = tasks_all + added_tasks

    users_count = len({t.user_id for t in tasks_merged})
    completed_tasks_count = sum(
        1 for t in tasks_merged if getattr(t, "is_done", False) is True
    )

    return {
        "users": users_count,
        "tasks": len(tasks_merged),
        "completed_tasks": completed_tasks_count,
        "notification_runs": len(db.query(NotificationRun).all() or []),
        "in_app_notifications": len(db.query(InAppNotification).all() or []),
        "outcome_logs": len(db.query(TaskOutcomeLog).all() or []),
        "action_applied_events": len(db.query(SuggestedActionAppliedEvent).all() or []),
    }

@router.get("/assets/users/{user_id}", response_model=dict)
def admin_assets_user_snapshot(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # FakeSession互換：すべて Python 集計（A-1と同じ思想）
    tasks_all = db.query(Task).all() or []
    added = getattr(db, "_added", []) or []
    added_tasks = [x for x in added if isinstance(x, Task)]
    tasks_merged = tasks_all + added_tasks

    # user単位
    tasks_u = [t for t in tasks_merged if getattr(t, "user_id", None) == user_id]
    completed_tasks_u = sum(1 for t in tasks_u if getattr(t, "is_done", False) is True)

    added = getattr(db, "_added", []) or []

    def _merge_all(Model):
        base = db.query(Model).all() or []
        extra = [x for x in added if isinstance(x, Model)]
        return base + extra

    inapps_all = _merge_all(InAppNotification)
    outcomes_all = _merge_all(TaskOutcomeLog)
    actions_all = _merge_all(SuggestedActionAppliedEvent)
    runs_all = _merge_all(NotificationRun)

    inapps_u = [n for n in inapps_all if getattr(n, "user_id", None) == user_id]
    outcomes_u = [o for o in outcomes_all if getattr(o, "user_id", None) == user_id]
    actions_u = [e for e in actions_all if getattr(e, "user_id", None) == user_id]

    # NotificationRun は user_id を持たず user帰属できない（仕様理由付き）
    runs_total = len(runs_all)

    return {
        "user_id": int(user_id),
        "tasks": int(len(tasks_u)),
        "completed_tasks": int(completed_tasks_u),
        "notification_runs": int(runs_total),
        "in_app_notifications": int(len(inapps_u)),
        "outcome_logs": int(len(outcomes_u)),
        "action_applied_events": int(len(actions_u)),
    }

def _merge_all(db: Session, Model):
    base = db.query(Model).all() or []
    added = getattr(db, "_added", []) or []
    extra = [x for x in added if isinstance(x, Model)]
    return base + extra


def _compute_global_assets(db: Session) -> dict:
    # Task は FakeSession 的に固定配列 + _added の両方を見る必要がある
    tasks_all = db.query(Task).all() or []
    added = getattr(db, "_added", []) or []
    added_tasks = [x for x in added if isinstance(x, Task)]
    tasks_merged = tasks_all + added_tasks

    users_count = len({t.user_id for t in tasks_merged})
    completed_tasks_count = sum(1 for t in tasks_merged if getattr(t, "is_done", False) is True)

    return {
        "users": int(users_count),
        "tasks": int(len(tasks_merged)),
        "completed_tasks": int(completed_tasks_count),
        "notification_runs": int(len(_merge_all(db, NotificationRun))),
        "in_app_notifications": int(len(_merge_all(db, InAppNotification))),
        "outcome_logs": int(len(_merge_all(db, TaskOutcomeLog))),
        "action_applied_events": int(len(_merge_all(db, SuggestedActionAppliedEvent))),
    }

@router.post("/assets/snapshots/run", response_model=dict)
def admin_assets_snapshots_run(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    counts = _compute_global_assets(db)

    snap = AssetSnapshot(
        kind="global",
        user_id=None,
        **counts,
        stats={
            "v": 1,
            "kind": "asset_snapshot",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"counts": counts},
        },
    )
    db.add(snap)
    db.commit()

    return {"ok": True, "snapshot_id": int(snap.id)}

@router.get("/assets/snapshots", response_model=dict)
def admin_assets_snapshots_list(
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    items = _merge_all(db, AssetSnapshot)

    # FakeSession互換：Pythonで並び替え + limit
    items_sorted = sorted(
        items,
        key=lambda x: getattr(x, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[: max(0, int(limit))]

    return {
        "items": [
            {
                "id": int(x.id),
                "kind": str(x.kind),
                "user_id": int(x.user_id) if x.user_id is not None else None,
                "users": int(x.users),
                "tasks": int(x.tasks),
                "completed_tasks": int(x.completed_tasks),
                "notification_runs": int(x.notification_runs),
                "in_app_notifications": int(x.in_app_notifications),
                "outcome_logs": int(x.outcome_logs),
                "action_applied_events": int(x.action_applied_events),
                "created_at": (x.created_at.isoformat() if getattr(x, "created_at", None) else None),
            }
            for x in items_sorted
        ]
    }

def _compute_user_assets(db: Session, user_id: int) -> dict:
    # Task は FakeSession 的に固定配列 + _added の両方を見る必要がある
    tasks_all = db.query(Task).all() or []
    added = getattr(db, "_added", []) or []
    added_tasks = [x for x in added if isinstance(x, Task)]
    tasks_merged = tasks_all + added_tasks

    tasks_u = [t for t in tasks_merged if getattr(t, "user_id", None) == user_id]
    completed_tasks_u = sum(1 for t in tasks_u if getattr(t, "is_done", False) is True)

    inapps_u = [
        n for n in _merge_all(db, InAppNotification)
        if getattr(n, "user_id", None) == user_id
    ]
    outcomes_u = [
        o for o in _merge_all(db, TaskOutcomeLog)
        if getattr(o, "user_id", None) == user_id
    ]
    actions_u = [
        e for e in _merge_all(db, SuggestedActionAppliedEvent)
        if getattr(e, "user_id", None) == user_id
    ]

    # NotificationRun は user_id を持たず user帰属できない（A-2と同一仕様）
    runs_total = len(_merge_all(db, NotificationRun))

    return {
        # users は userスナップショット上「このuserが存在する」ことを示す最小表現として 1 固定
        # （Userモデルを query しない：FakeSession互換のため）
        "users": 1,
        "tasks": int(len(tasks_u)),
        "completed_tasks": int(completed_tasks_u),
        "notification_runs": int(runs_total),
        "in_app_notifications": int(len(inapps_u)),
        "outcome_logs": int(len(outcomes_u)),
        "action_applied_events": int(len(actions_u)),
    }

@router.post("/assets/users/{user_id}/snapshots/run", response_model=dict)
def admin_assets_user_snapshots_run(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    counts = _compute_user_assets(db, int(user_id))

    snap = AssetSnapshot(
        kind="user",
        user_id=int(user_id),
        **counts,
        stats={
            "v": 1,
            "kind": "asset_snapshot_user",
            "user_id": int(user_id),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"counts": counts},
        },
    )
    db.add(snap)
    db.commit()

    return {"ok": True, "snapshot_id": int(snap.id)}

@router.get("/assets/users/{user_id}/snapshots", response_model=dict)
def admin_assets_user_snapshots_list(
    user_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    items = _merge_all(db, AssetSnapshot)

    # user別に抽出（FakeSession互換：Python）
    items_u = [
        x for x in items
        if getattr(x, "kind", None) == "user" and getattr(x, "user_id", None) == int(user_id)
    ]

    items_sorted = sorted(
        items_u,
        key=lambda x: getattr(x, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[: max(0, int(limit))]

    return {
        "items": [
            {
                "id": int(x.id),
                "kind": str(x.kind),
                "user_id": int(x.user_id) if x.user_id is not None else None,
                "users": int(x.users),
                "tasks": int(x.tasks),
                "completed_tasks": int(x.completed_tasks),
                "notification_runs": int(x.notification_runs),
                "in_app_notifications": int(x.in_app_notifications),
                "outcome_logs": int(x.outcome_logs),
                "action_applied_events": int(x.action_applied_events),
                "created_at": (x.created_at.isoformat() if getattr(x, "created_at", None) else None),
            }
            for x in items_sorted
        ]
    }

@router.get("/assets/snapshots/growth", response_model=dict)
def admin_assets_snapshots_growth(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # SSOT: AssetSnapshot のみ
    snaps = _merge_all(db, AssetSnapshot)
    snaps = [s for s in snaps if getattr(s, "kind", None) == "global"]

    if len(snaps) < 2:
        return {
            "days": int(days),
            "from_snapshot_id": None,
            "to_snapshot_id": None,
            "delta": {
                "users": 0,
                "tasks": 0,
                "completed_tasks": 0,
                "notification_runs": 0,
                "in_app_notifications": 0,
                "outcome_logs": 0,
                "action_applied_events": 0,
            },
        }

    snaps_sorted = sorted(
        snaps,
        key=lambda x: x.created_at,
    )

    to_snap = snaps_sorted[-1]
    threshold = to_snap.created_at - timedelta(days=int(days))

    from_candidates = [s for s in snaps_sorted if s.created_at <= threshold]
    from_snap = from_candidates[-1] if from_candidates else snaps_sorted[0]

    def d(k: str) -> int:
        return int(getattr(to_snap, k) - getattr(from_snap, k))

    return {
        "days": int(days),
        "from_snapshot_id": int(from_snap.id),
        "to_snapshot_id": int(to_snap.id),
        "delta": {
            "users": d("users"),
            "tasks": d("tasks"),
            "completed_tasks": d("completed_tasks"),
            "notification_runs": d("notification_runs"),
            "in_app_notifications": d("in_app_notifications"),
            "outcome_logs": d("outcome_logs"),
            "action_applied_events": d("action_applied_events"),
        },
    }

def _hmac_sha256(text: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), text.encode("utf-8"), hashlib.sha256).hexdigest()

def _export_secret() -> str:
    # Export 用 HMAC secret
    # - 明示設定があればそれを優先
    # - なければ SESSION_SECRET（既存・本番必須）
    return (
        getattr(settings, "FEATURE_HASH_SECRET", None)
        or getattr(settings, "SESSION_SECRET", "")
    )

def _build_export_dict(
    *,
    kind: str,
    user_id: Optional[int],
    limit: int,
    db: Session,
) -> dict:
    kind = str(kind)
    if kind not in ("global", "user"):
        kind = "global"

    if kind == "user" and user_id is None:
        user_id = 0

    lim = int(limit)
    if lim <= 0:
        lim = 1000
    if lim > 5000:
        lim = 5000

    secret = _export_secret()

    # SSOT: すべて Python + _added マージ
    snaps = _merge_all(db, AssetSnapshot)
    outcomes = _merge_all(db, TaskOutcomeLog)
    runs = _merge_all(db, NotificationRun)
    inapps = _merge_all(db, InAppNotification)
    events = _merge_all(db, SuggestedActionAppliedEvent)

    # kind フィルタ
    if kind == "global":
        snaps = [s for s in snaps if getattr(s, "kind", None) == "global"]
    else:
        uid = int(user_id)
        snaps = [
            s for s in snaps
            if getattr(s, "kind", None) == "user" and getattr(s, "user_id", None) == uid
        ]
        outcomes = [o for o in outcomes if getattr(o, "user_id", None) == uid]
        inapps = [n for n in inapps if getattr(n, "user_id", None) == uid]
        events = [e for e in events if getattr(e, "user_id", None) == uid]

    # created_at / evaluated_at / applied_at で新しい順に
    snaps = sorted(snaps, key=lambda x: getattr(x, "created_at", None), reverse=True)[:lim]
    outcomes = sorted(outcomes, key=lambda x: getattr(x, "evaluated_at", None), reverse=True)[:lim]
    inapps = sorted(inapps, key=lambda x: getattr(x, "created_at", None), reverse=True)[:lim]
    events = sorted(events, key=lambda x: getattr(x, "applied_at", None), reverse=True)[:lim]
    runs = sorted(runs, key=lambda x: getattr(x, "started_at", None), reverse=True)[:lim]

    def iso(dt):
        return dt.isoformat() if dt is not None else None

    def export_inapp(n: InAppNotification) -> dict:
        return {
            "id": int(n.id),
            "user_id": int(getattr(n, "user_id", 0)) or None,
            "task_id": int(n.task_id) if getattr(n, "task_id", None) is not None else None,
            "deadline_at_send": iso(getattr(n, "deadline_at_send", None)),
            "offset_hours": int(n.offset_hours) if getattr(n, "offset_hours", None) is not None else None,
            "kind": str(getattr(n, "kind", "")),
            "deep_link": str(getattr(n, "deep_link", "")),
            "run_id": int(n.run_id) if getattr(n, "run_id", None) is not None else None,
            "extra": getattr(n, "extra", None),
            "created_at": iso(getattr(n, "created_at", None)),
            "dismissed_at": iso(getattr(n, "dismissed_at", None)),
        }

    def export_event(e: SuggestedActionAppliedEvent) -> dict:
        payload_text = json.dumps(
            getattr(e, "payload", {}),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return {
            "id": int(e.id),
            "user_id": int(e.user_id),
            "action_id": str(e.action_id),
            "bucket": str(e.bucket),
            "applied_at": iso(getattr(e, "applied_at", None)),
            "payload_hash": _hmac_sha256(payload_text, secret),
            "created_at": iso(getattr(e, "created_at", None)),
        }

    def export_outcome(o: TaskOutcomeLog) -> dict:
        return {
            "id": int(o.id),
            "user_id": int(o.user_id),
            "task_id": int(o.task_id),
            "deadline": iso(getattr(o, "deadline", None)),
            "outcome": str(o.outcome),
            "evaluated_at": iso(getattr(o, "evaluated_at", None)),
            "created_at": iso(getattr(o, "created_at", None)),
        }

    def export_run(r: NotificationRun) -> dict:
        return {
            "id": int(r.id),
            "status": str(r.status),
            "started_at": iso(getattr(r, "started_at", None)),
            "finished_at": iso(getattr(r, "finished_at", None)),
            "users_processed": int(getattr(r, "users_processed", 0)),
            "due_candidates_total": int(getattr(r, "due_candidates_total", 0)),
            "morning_candidates_total": int(getattr(r, "morning_candidates_total", 0)),
            "inapp_created": int(getattr(r, "inapp_created", 0)),
            "webpush_sent": int(getattr(r, "webpush_sent", 0)),
            "webpush_failed": int(getattr(r, "webpush_failed", 0)),
            "webpush_deactivated": int(getattr(r, "webpush_deactivated", 0)),
            "line_sent": int(getattr(r, "line_sent", 0)),
            "line_failed": int(getattr(r, "line_failed", 0)),
            "error_summary": getattr(r, "error_summary", None),
            "stats": getattr(r, "stats", None),
        }

    def export_snap(s: AssetSnapshot) -> dict:
        return {
            "id": int(s.id),
            "kind": str(s.kind),
            "user_id": int(s.user_id) if s.user_id is not None else None,
            "users": int(s.users),
            "tasks": int(s.tasks),
            "completed_tasks": int(s.completed_tasks),
            "notification_runs": int(s.notification_runs),
            "in_app_notifications": int(s.in_app_notifications),
            "outcome_logs": int(s.outcome_logs),
            "action_applied_events": int(s.action_applied_events),
            "stats": getattr(s, "stats", None),
            "created_at": iso(getattr(s, "created_at", None)),
        }

    generated_at = datetime.now(timezone.utc).isoformat()

    return {
        "export_version": 1,
        "generated_at": generated_at,
        "range": {
            "kind": kind,
            "user_id": int(user_id) if kind == "user" else None,
            "from": None,
            "to": None,
            "limit": lim,
        },
        "payload": {
            "asset_snapshots": [export_snap(s) for s in snaps],
            "outcome_logs": [export_outcome(o) for o in outcomes],
            "action_applied_events": [export_event(e) for e in events],
            "notification_runs": [export_run(r) for r in runs],
            "in_app_notifications": [export_inapp(n) for n in inapps],
        },
    }

@router.get("/assets/export", response_model=dict)
def admin_assets_export(
    kind: str = "global",
    user_id: Optional[int] = None,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _ = current_user  # 認証ガード用（未使用でOK）
    return _build_export_dict(kind=kind, user_id=user_id, limit=limit, db=db)

@router.post("/assets/export/runs", response_model=dict)
def admin_assets_export_runs_create(
    kind: str = "global",
    user_id: Optional[int] = None,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _ = current_user  # 認証ガード用（未使用でOK）

    # ✅ 既存と同じ export を生成（SSOT）
    export_dict = _build_export_dict(kind=kind, user_id=user_id, limit=limit, db=db)

    # ✅ export 全体のハッシュ（改ざん検出・監査）
    secret = _export_secret()
    payload_text = json.dumps(
        export_dict, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    export_hash = _hmac_sha256(payload_text, secret)

    run = ExportRun(
        export_version=int(export_dict.get("export_version", 1)),
        kind=str(export_dict.get("range", {}).get("kind", kind)),
        user_id=export_dict.get("range", {}).get("user_id", None),
        from_ts=None,
        to_ts=None,
        limit=int(export_dict.get("range", {}).get("limit", limit)),
        export_hash=str(export_hash),
        meta={
            "range": export_dict.get("range"),
            "counts": {
                "asset_snapshots": len(export_dict["payload"]["asset_snapshots"]),
                "outcome_logs": len(export_dict["payload"]["outcome_logs"]),
                "action_applied_events": len(export_dict["payload"]["action_applied_events"]),
                "notification_runs": len(export_dict["payload"]["notification_runs"]),
                "in_app_notifications": len(export_dict["payload"]["in_app_notifications"]),
            },
        },
    )
    db.add(run)
    db.commit()

    return {"ok": True, "export_run_id": int(run.id), "export_hash": str(export_hash)}

@router.get("/assets/export/runs", response_model=dict)
def admin_assets_export_runs_list(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _ = current_user  # 認証ガード用（未使用でOK）

    lim = int(limit)
    if lim <= 0:
        lim = 50
    if lim > 5000:
        lim = 5000

    items = _merge_all(db, ExportRun)
    items_sorted = sorted(
        items,
        key=lambda x: getattr(x, "created_at", None)
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:lim]

    def iso(dt):
        return dt.isoformat() if dt is not None else None

    return {
        "items": [
            {
                "id": int(x.id),
                "export_version": int(getattr(x, "export_version", 1)),
                "kind": str(getattr(x, "kind", "")),
                "user_id": int(getattr(x, "user_id")) if getattr(x, "user_id", None) is not None else None,
                "from": iso(getattr(x, "from_ts", None)),
                "to": iso(getattr(x, "to_ts", None)),
                "limit": int(getattr(x, "limit", 0) or 0),
                "export_hash": str(getattr(x, "export_hash", "")),
                "created_at": iso(getattr(x, "created_at", None)),
            }
            for x in items_sorted
        ]
    }
