# UniPA Reminder App

大学生向けの課題管理＋LINE通知Webアプリケーション（Phase 1）

## 概要

このアプリは、大学生が課題を管理し、締切前にLINE通知を受け取れるWebアプリケーションです。

### Phase 1 の機能

- ✅ ユーザーが課題を手入力で登録
- ✅ 課題一覧の表示（今日から1週間以内）
- ✅ 課題の完了/未完了切り替え
- ✅ 課題の削除
- ✅ 通知設定（締切リマインド時間、日次ダイジェスト時間）
- ✅ LINE通知のための土台（ダミー実装）

### 将来的な拡張予定

- Moodleタイムラインから自動取得するAPI
- ブラウザ拡張機能
- 実際のLINE Messaging API連携
- LINEログイン認証

## 技術スタック

### バックエンド

- Python 3.11+
- FastAPI
- SQLAlchemy
- SQLite（開発時）、将来PostgreSQL対応可能
- Uvicorn

### フロントエンド

- React 18
- TypeScript
- Vite
- React Router

## セットアップ

### 1. バックエンドのセットアップ

```bash
cd backend

# 仮想環境の作成（推奨）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージのインストール
pip install -r requirements.txt

# 環境変数の設定
cp env.example .env
# .env ファイルを必要に応じて編集

# データベースの初期化（アプリ起動時に自動実行されます）

# サーバーの起動
uvicorn app.main:app --reload --port 8000
```

### 2. フロントエンドのセットアップ

```bash
cd frontend

# 依存パッケージのインストール
npm install

# 開発サーバーの起動
npm run dev
```

### 3. アクセス

- フロントエンド: http://localhost:5173
- バックエンドAPI: http://localhost:8000
- API ドキュメント: http://localhost:8000/docs

## プロジェクト構造

```
unipa-reminder-app/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   ├── auth.py      # 認証エンドポイント
│   │   │       │   ├── tasks.py     # 課題管理エンドポイント
│   │   │       │   └── settings.py  # 通知設定エンドポイント
│   │   │       └── api.py
│   │   ├── core/
│   │   │   ├── config.py      # 設定管理
│   │   │   └── security.py    # 認証ミドルウェア（ダミー認証）
│   │   ├── db/
│   │   │   ├── base.py        # DB接続設定
│   │   │   └── session.py     # セッション管理
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── task.py
│   │   │   └── notification_setting.py
│   │   ├── schemas/
│   │   │   ├── user.py
│   │   │   ├── task.py
│   │   │   └── notification_setting.py
│   │   ├── services/
│   │   │   └── line_client.py  # LINE通知サービス（ダミー実装）
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/          # API クライアント
│   │   ├── components/   # React コンポーネント
│   │   ├── pages/        # ページコンポーネント
│   │   ├── types/        # TypeScript 型定義
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## API エンドポイント

### 認証

- `GET /api/v1/auth/me` - 現在のユーザー情報を取得

### 課題管理

- `GET /api/v1/tasks/` - 課題一覧を取得（クエリパラメータ: `start_date`, `end_date`, `is_done`）
- `POST /api/v1/tasks/` - 課題を新規作成
- `PATCH /api/v1/tasks/{task_id}` - 課題を更新
- `DELETE /api/v1/tasks/{task_id}` - 課題を削除

### 通知設定

- `GET /api/v1/settings/notification` - 通知設定を取得
- `POST /api/v1/settings/notification` - 通知設定を作成/更新

## 認証について（開発時）

現在、ダミー認証が有効になっています。

- リクエストヘッダーに `X-Dummy-User-Id: 1` を設定すると、そのユーザーIDでログインしたことになります
- 存在しないユーザーIDの場合は、自動的にダミーユーザーが作成されます
- 将来的にLINEログイン認証に置き換える予定です

## データベーススキーマ

### users テーブル

- `id`: 主キー
- `line_user_id`: LINEユーザーID（ユニーク）
- `display_name`: 表示名
- `university`: 大学名
- `plan`: プラン（"free", "basic", "pro"）

### tasks テーブル

- `id`: 主キー
- `user_id`: ユーザーID（外部キー）
- `title`: 課題タイトル
- `course_name`: 授業名
- `deadline`: 締切日時（タイムゾーン付き）
- `memo`: メモ（任意）
- `is_done`: 完了フラグ
- `created_at`: 作成日時
- `updated_at`: 更新日時

### notification_settings テーブル

- `id`: 主キー
- `user_id`: ユーザーID（外部キー、ユニーク）
- `reminder_offsets_hours`: 締切リマインド時間（JSON配列、例: [24, 3, 1]）
- `daily_digest_time`: 日次ダイジェスト送信時間（"HH:MM"形式）

## 今後の拡張

1. **Moodle連携**: `/api/v1/moodle/import` エンドポイントを追加
2. **LINEログイン**: 実際のLINE Login APIを使用した認証
3. **LINE通知**: LINE Messaging APIを使用した実際の通知送信
4. **通知スケジューラー**: バックグラウンドでリマインド通知を送信するジョブ
5. **ブラウザ拡張**: Chrome/Firefox拡張機能の開発

## ライセンス

このプロジェクトは個人利用・教育目的で使用できます。

