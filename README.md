# DueFlow

DueFlow は、大学生が課題の提出期限を見逃さないようにするために設計されたタスク・締切管理アプリケーションです。

大学の授業では多くの情報があり、課題の締切を確実に管理することが難しくなることがあります。  
DueFlow はタスク管理を一元化し、適切なタイミングで通知を送ることで提出忘れのリスクを減らします。

このプロジェクトは監査性（auditability）、データ整合性（data integrity）、長期的なシステム信頼性（long-term system reliability）を重視して設計されています。

---

# Project Status

DueFlow は現在も開発を継続している個人プロジェクトです。  
このリポジトリには、タスク管理機能、通知ロジック、Web Push 対応、バックエンドのシステム設計など、現在の実装内容が含まれています。

認証フローやデプロイ周りの改善を進めているため、現時点では公開デモは提供していません。

# Key Features

## Task Management

DueFlow は大学の課題管理に特化したシンプルなタスク管理機能を提供します。

- タスクの作成と管理
- 期限が近い課題の一覧表示
- タスクの完了処理
- タスクの削除
- 週次の繰り返しタスク

タスクは分かりやすいリスト形式で表示され、ユーザーが現在の作業量をすぐに把握できるようになっています。

---

## Notification System

DueFlow の主な目的は、締切の見逃しを防ぐことです。

現在、以下の通知機能をサポートしています。

### In-App Notifications

アプリケーション内で表示される通知です。  
通知はデータベースに保存されます。

Features

- 通知の永続保存
- ユーザーによる既読・非表示操作
- 通知のサマリー表示

---

### Web Push Notifications

DueFlow は Service Worker を利用した Web Push 通知に対応しています。  
アプリを開いていない状態でも OS レベルで通知を受け取ることができます。

Features

- ブラウザレベルの通知
- アプリが閉じていても通知可能
- Service Worker によるバックグラウンド Push

---

## Notification Logging

DueFlow では通知に関するイベントをサーバー側で記録しています。

Examples

- 通知が作成されたタイミング
- どのタスクが通知のトリガーになったか
- 通知処理（notification run）が実行された時間

これらのログにより、なぜ通知が送信されたのか、または送信されなかったのかを後から確認できるようになっています。

---

# System Design

DueFlow は長期的な保守性と信頼性を重視して設計されています。

アーキテクチャは主に以下の2つの原則に基づいています。

---

## Single Source of Truth (SSOT)

重要なデータは一つの正しいデータソースにのみ保存されます。

これにより次の問題を防ぎます。

- 通知の重複
- タスク状態の不整合
- 信頼性の低い分析データ

---

## Auditability

通知イベントは後から確認できるように保存されています。

Examples

- notification run records
- notification logs
- outcome logs

この設計により、開発者はシステムの挙動を検証し、通知ロジックの判断を追跡できます。

---

# Architecture Overview

Frontend  
React + TypeScript

Backend  
FastAPI + SQLAlchemy

Database  
PostgreSQL

Deployment  
Render

Notifications  
Web Push (Service Worker)

---

# Tech Stack

## Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- pywebpush

---

## Frontend

- React
- TypeScript
- Vite
- Service Worker

---

# Local Development

## Backend

cd backend

python -m venv .venv  
source .venv/bin/activate  

pip install -r requirements.txt  

cp env.example .env  

uvicorn app.main:app --reload --port 8000

## Frontend

cd frontend

npm install  
npm run dev  

---

# API Examples

In-App Notifications

GET /api/v1/notifications/in-app  
POST /api/v1/notifications/in-app/{id}/dismiss  

Web Push

POST /api/v1/notifications/webpush/subscribe  
POST /api/v1/notifications/webpush/unsubscribe  

---

# Future Development

今後の予定機能

- 大学システムからの課題自動同期
- 通知タイミングアルゴリズムの改善
- 学習行動分析の強化
- UI / UX 改善

最終的には、DueFlow を学生の学習ワークフローを支援するプラットフォームへ発展させることを目標としています。