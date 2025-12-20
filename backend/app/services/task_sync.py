# app/services/task_sync.py
from sqlalchemy.orm import Session
from app.models.task import Task
from app.services.unipa_client import UnipaClient

def sync_unipa_tasks(
    db: Session,
    username: str,
    password: str,
    user_id: int = 1,
) -> int:
    """
    UNIPAから課題を取得してTaskテーブルに反映する。
    戻り値は「新規作成されたタスク数」。
    """
    client = UnipaClient(username=username, password=password)
    tasks_from_unipa = client.fetch_tasks()

    created_count = 0

    for t in tasks_from_unipa:
        # 同一課題かどうかを user_id + title + course_name + deadline で判定
        existing = (
            db.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.title == t.title,
                Task.course_name == t.course_name,
                Task.deadline == t.deadline,
            )
            .first()
        )
        if existing:
            # 既存ならメモだけ更新（必要に応じて拡張）
            existing.memo = t.memo
        else:
            new_task = Task(
                user_id=user_id,
                title=t.title,
                course_name=t.course_name,
                deadline=t.deadline,
                memo=t.memo,
                is_done=False,
            )
            db.add(new_task)
            created_count += 1
    db.commit()
    return created_count
