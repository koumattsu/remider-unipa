# app/services/moodle_client.py
from __future__ import annotations

import re
from datetime import datetime
from typing import List

from bs4 import BeautifulSoup

from app.services.unipa_client import UnipaTaskData
from app.schemas.task import TaskCreate
from app.services.task_service import upsert_tasks_from_moodle_list
from sqlalchemy.ext.asyncio import AsyncSession

# 「2025年 11月 24日 00:00」みたいな文字を抜き出す用
DATETIME_RE = re.compile(
    r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日\s*(\d{2}:\d{2})"
)


def parse_moodle_timeline_html(html: str) -> List[UnipaTaskData]:
    """
    OMU Moodle の「ダッシュボード > タイムライン」HTMLから
    課題一覧を抜き出して UnipaTaskData のリストに変換する。
    """
    soup = BeautifulSoup(html, "html.parser")

    # タイムラインの1件ぶんコンテナ
    items = soup.select(
        'div.list-group-item.timeline-event-list-item[data-region="event-list-item"]'
    )

    tasks: List[UnipaTaskData] = []

    for item in items:
        # 1) タイトル
        a_tag = item.select_one("h6.event-name a")
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)

        # 2) 締切日時（aria-label から取得）
        aria = a_tag.get("aria-label") or ""
        m = DATETIME_RE.search(aria)

        if not m:
            # 日付が取れないものはとりあえずスキップ
            continue

        year_str, month_str, day_str, time_str = m.groups()

        # "2025-11-24 00:00" 形式にしてから datetime にパース
        year = int(year_str)
        month = int(month_str)
        day = int(day_str)

        deadline = datetime.strptime(
            f"{year:04d}-{month:02d}-{day:02d} {time_str}",
            "%Y-%m-%d %H:%M",
        )

        # 3) 科目名（小さい文字のところ）
        course_name = ""
        info_small = item.select_one(
            "div.event-name-container small.mb-0"
        )
        if info_small:
            text = info_small.get_text(strip=True)
            # 「課題」の提出期限 · 2025後 線形代数2B /必:工〈電ｼｽ〉_森 【火2金2】
            if "·" in text:
                course_name = text.split("·", 1)[1].strip()
            else:
                course_name = text

        # 4) メモはとりあえず aria-label 全体を突っ込んでおく（あとで変えてOK）
        memo = aria or None

        tasks.append(
            UnipaTaskData(
                title=title,
                course_name=course_name,
                deadline=deadline,
                memo=memo,
            )
        )

    return tasks


# ここから Step2 用の追加 👇
async def import_moodle_timeline_html_for_user(
    db: AsyncSession,
    *,
    user_id: int,
    html: str,
) -> int:
    """
    Moodle タイムラインHTMLをパースして Task に upsert する高レベル関数。

    1. HTML をパースして UnipaTaskData のリストを作る
    2. TaskCreate に変換
    3. upsert_tasks_from_moodle_list で DB に反映

    戻り値: 処理した件数
    """
    parsed_unipa_tasks = parse_moodle_timeline_html(html)

    task_creates: List[TaskCreate] = [
        TaskCreate(
            title=t.title,
            course_name=t.course_name,
            deadline=t.deadline,
            memo=t.memo,
        )
        for t in parsed_unipa_tasks
    ]

    # upsert して件数を返す
    return await upsert_tasks_from_moodle_list(
        db,
        user_id=user_id,
        tasks_in=task_creates,
    )
