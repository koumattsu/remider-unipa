# DueFlow

**DueFlow** is a task and deadline management application designed to help university students avoid missing assignment submissions.

University courses often provide a large amount of information across different systems, making it difficult for students to manage deadlines reliably.  
DueFlow centralizes task management and sends notifications at appropriate times to reduce the risk of missed submissions.

This project is built with a strong emphasis on **auditability**, **data integrity**, and **long-term system reliability**.

---

# Demo

Frontend  
https://your-frontend-url

Backend API  
https://your-backend-url

---

# Key Features

## Task Management

DueFlow provides simple task management designed specifically for academic assignments.

- Create and manage tasks
- View upcoming deadlines
- Mark tasks as completed
- Delete tasks
- Weekly recurring tasks

Tasks are presented in a clear list format to help users quickly understand their workload.

---

## Notification System

Preventing missed deadlines is the primary goal of DueFlow.

The system currently supports the following notifications:

### In-App Notifications

Notifications stored in the database and displayed inside the application.

Features

- Persistent notification storage
- User-controlled dismiss
- Notification summaries

---

### Web Push Notifications

DueFlow supports **Web Push notifications via Service Workers**, enabling OS-level notifications even when the application is not open.

Features

- Browser-level notifications
- Works when the app is closed
- Background push via Service Worker

---

## Notification Logging

DueFlow records notification-related events on the server side.

Examples

- When a notification was created
- Which task triggered the notification
- When the notification run occurred

These logs allow the system to explain **why a notification was sent or not sent**, improving system transparency.

---

# System Design

DueFlow is designed with long-term maintainability and reliability in mind.

Two major principles guide the architecture.

---

## Single Source of Truth (SSOT)

Important data is stored in a single authoritative location.

This prevents

- duplicated notifications
- inconsistent task states
- unreliable analytics

---

## Auditability

Notification events are stored so that system behavior can be explained later.

Examples

- notification run records
- notification logs
- outcome logs

This design allows developers to inspect system behavior and verify notification decisions.

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

```bash
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

API Examples
In-App Notifications

GET /api/v1/notifications/in-app
POST /api/v1/notifications/in-app/{id}/dismiss

Web Push

POST /api/v1/notifications/webpush/subscribe
POST /api/v1/notifications/webpush/unsubscribe

Future Development

Planned improvements include

Automatic assignment synchronization from university systems

Improved notification timing algorithms

Enhanced analytics for learning behavior

UI/UX improvements

The long-term goal is to evolve DueFlow into a platform that helps students manage their academic workflow more effectively.
