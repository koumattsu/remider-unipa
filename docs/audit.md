# Audit & Data Integrity

本ドキュメントは、UNIPA Reminder App における
**データ完全性 / マルチテナント分離 / 壊れにくさ**を
第三者（監査・M&A デューデリ）に説明するための要約です。

---

## Multi-Tenant Isolation（ユーザ分離）

### 設計方針
- すべてのユーザ所有リソース（Task など）は **user_id** で分離される
- **user_id は認証コンテキスト（current_user）からのみ注入**
- クライアント入力から user_id を受け取らない（改ざん不可）

### 実装要点
- Task 作成時に `user_id = current_user.id` を強制
- 一覧取得時は必ず `Task.user_id == current_user.id` をフィルタ
- ソフトデリート（deleted_at）を採用し、分析価値を保持

---

## Test Strategy（テスト戦略）

### 方針
- 既存の契約テスト群（analytics / notification / outcome）を破壊しない
- FakeSession の制約に依存しない **安全な隔離テスト**を採用
- 実装詳細（offset / limit / order_by）に依存しない

### 代表テスト
- `backend/tests/test_tasks_tenant_isolation.py`
  - user1 / user2 として Task を作成
  - FakeSession に保存された Task を直接検査
  - user_id が混在しないことを保証

```text
test_tasks_are_isolated_by_user_id_in_db