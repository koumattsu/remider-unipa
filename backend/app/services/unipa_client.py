# app/services/unipa_client.py
from typing import List
from datetime import datetime


class UnipaTaskData:
    """
    UNIPAから取得した課題データ（DBに保存する前の中間オブジェクト）
    """
    def __init__(
        self,
        title: str,
        course_name: str,
        deadline: datetime,
        memo: str | None = None,
    ) -> None:
        self.title = title
        self.course_name = course_name
        self.deadline = deadline
        self.memo = memo


class UnipaClient:
    """
    UNIPAにログインして課題一覧を取得するクライアント。
    今はダミーデータを返すだけでOK。
    """

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    def fetch_tasks(self) -> List[UnipaTaskData]:
        """
        本番ではスクレイピング実装に差し替える。
        今は動作確認用に1件だけダミーデータを返す。
        """
        dummy_deadline = datetime(2025, 11, 25, 23, 59)

        return [
            UnipaTaskData(
                title="線形代数 レポート1",
                course_name="線形代数I",
                deadline=dummy_deadline,
                memo="第3回講義までの内容についてA4 1枚でまとめる",
            )
        ]
