# backend/test_import_moodle.py

import requests

def main():
    # さっき作ったサンプルHTMLファイル
    with open("moodle_sample.html", "r", encoding="utf-8") as f:
        html = f.read()

    url = "http://127.0.0.1:8000/api/v1/tasks/import-moodle-html"

    payload = {
        "html": html,
    }

    headers = {
        "X-Dummy-User-Id": "1",  # ダミーユーザーID
        "Content-Type": "application/json",
    }

    resp = requests.post(url, json=payload, headers=headers)
    print("status:", resp.status_code)
    print("body  :", resp.text)


if __name__ == "__main__":
    main()
