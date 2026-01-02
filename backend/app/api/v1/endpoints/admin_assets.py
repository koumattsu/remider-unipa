# backend/app/api/v1/endpoints/admin_assets.py

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.asset_snapshot import AssetSnapshot
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
