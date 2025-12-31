# UNIPA Reminder App

大学生向けの課題管理 + 通知（Web Push / In-app / 将来LINE）アプリ  
**M&A耐性（監査可能性）を最優先**に、通知の「事実」をサーバ側に残す設計で実装しています。

---

## Documentation

This project is designed with **auditability, explainability, and long-term M&A resilience**
as first-class requirements.

- [Analytics Architecture](docs/analytics-architecture.md)

---

## 何ができるか（現状）

### 課題管理
- ✅ 課題の手動追加・一覧表示
- ✅ 完了 / 未完了切り替え（完了タスクは通知対象外）
- ✅ 削除
- ✅（将来）Moodle / UNIPA からの自動取得・重複判定・AI理解レイヤー

### 通知（現状の主軸）
- ✅ **In-app通知（ベル通知）**  
  通知を DB に保存し、ユーザーが dismiss（既読化）できる
- ✅ **Web Push（無料プラン向け）**  
  Service Worker 経由で OS 通知（アプリ未起動でも通知）
- ✅ **通知基盤の監査ログ**
  - cron 実行 1 回 = 1 レコード（NotificationRun）
  - 重複通知防止（TaskNotificationLog）
  - 通知生成時の締切を固定保存（deadline_at_send）

※ LINE通知は将来の有料プラン想定（現在は未実装）

---

## 設計方針（M&A耐性）

### 1. 「通知が来た / 来なかった」をサーバの事実として追跡
- **NotificationRun**
  - cron 実行 1 回 = 1 行
  - status / error_summary / counters / finished_at / stats(snapshot)
- 障害時でも「なぜ通知されなかったか」を後から説明可能

### 2. 幽霊通知（重複通知）を設計で排除
- **TaskNotificationLog**
  - 「この通知は送った」という事実を保存
- **deadline_at_send**
  - 通知作成時点の締切をコピー
  - 締切変更があっても当時の事実は不変

### 3. UI 表示と分析データを分離
- **OutcomeLog（task_outcome_log）**
  - 締切到達時点で「完了 / 未完了」を記録
  - 後から状態が変わっても分析結果は変わらない

---

## 技術スタック

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy
- PostgreSQL（本番） / SQLite（開発）
- Web Push: pywebpush
- 認証: Cookie Session（itsdangerous）

### Frontend
- React
- TypeScript
- Vite
- Service Worker（Web Push）

---

## セットアップ（ローカル）

### Backend
```bash
cd backend

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp env.example .env
# DATABASE_URL / SESSION_SECRET / FRONTEND_URL 等を設定

uvicorn app.main:app --reload --port 8000

## API（抜粋）

### In-app 通知
- GET /api/v1/notifications/in-app
- POST /api/v1/notifications/in-app/{id}/dismiss
- GET /api/v1/notifications/in-app/summary?from=&to=

### Web Push
- POST /api/v1/notifications/webpush/subscribe
- POST /api/v1/notifications/webpush/unsubscribe

### 監査（NotificationRun）
- GET /api/v1/admin/notification-runs/latest
- GET /api/v1/admin/notification-runs/{run_id}/summary


## 認証（現状）

- Cookie セッション（HttpOnly）
- 開発時のみ `DUMMY_AUTH_ENABLED=true` の場合、
  `X-Dummy-User-Id` ヘッダを許可