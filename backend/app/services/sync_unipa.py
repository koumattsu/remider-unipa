# app/services/sync_unipa.py
from sqlalchemy.orm import Session
from app.models.task import Task
from app.services.unipa_client import UnipaClient


def sync_unipa_tasks(db: Session, user_id: int, username: str, password: str) -> int:
    """
    UNIPAから課題を取得して tasks テーブルに同期する。
    ※ 今は UnipaClient.fetch_tasks() がダミーでもOK。
    """

    # UNIPAクライアントを作成
    client = UnipaClient(username=username, password=password)

    # UNIPAから課題を取得（今はまだダミー1件だけ）
    unipa_tasks = client.fetch_tasks()

    created_count = 0

    for t in unipa_tasks:
        # Taskモデルに変換してDBに保存
        task = Task(
            user_id=user_id,
            title=t.title,
            course_name=t.course_name,
            deadline=t.deadline,
            memo=t.memo,
            is_done=False,
        )
        db.add(task)
        created_count += 1

    db.commit()
    return created_count
