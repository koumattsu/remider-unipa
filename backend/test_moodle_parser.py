# backend/test_moodle_parser.py

from app.services.moodle_client import parse_moodle_timeline_html

def main():
    # サンプルHTMLを読み込み
    with open("moodle_sample.html", "r", encoding="utf-8") as f:
        html = f.read()

    tasks = parse_moodle_timeline_html(html)

    print(f"抽出できた件数: {len(tasks)}")
    for i, t in enumerate(tasks, start=1):
        print("----")
        print(f"{i}件目")
        print("タイトル   :", t.title)
        print("科目名     :", t.course_name)
        print("締切       :", t.deadline)
        print("メモ(先頭20文字):", (t.memo or "")[:20])

if __name__ == "__main__":
    main()
