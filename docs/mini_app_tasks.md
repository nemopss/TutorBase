# Mini App Implementation Tasks

## Stage 0 – Preparation
1. Extract business logic into service layer
   - [x] Create `services/package_service.py` with CRUD operations (create/update/delete packages, regenerate reminders).
   - [x] Create `services/lesson_service.py` for lesson CRUD and status changes.
   - [x] Create `services/template_service.py` for preset operations.
   - [x] Update FSM handlers to call the service layer.
2. Database migrations
   - [x] Add `users` table with roles and Telegram identifiers.
   - [x] Add `updated_by_user_id` / `updated_at` fields to packages and lessons.
   - [x] Ensure indices on `lessons` (package_id + scheduled_at).
3. API skeleton
   - [x] Set up FastAPI app with router structure `/api/v1`.
   - [x] Configure logging, error handling, OpenAPI docs.
   - [x] Integrate DB session dependency (shared with bot).

## Stage 1 – Backend API
0. API skeleton
   - [x] Set up FastAPI app with router structure `/api/v1`.
   - [x] Introduce shared DB session dependency.
1. Authentication & roles
   - [x] Implement Telegram initData validation.
   - [x] `/auth/login` endpoint returning JWT + refresh token.
   - [x] `/auth/refresh` endpoint.
   - [x] Role-based dependency (`admin`, `teacher`, future `student`).
2. Packages API
   - [x] `GET /packages` with filtering, pagination, stats.
   - [x] `POST /packages/create` (from template or manual).
   - [x] `GET /packages/{id}`, `PATCH /packages/{id}`, `DELETE /packages/{id}`.
   - [x] `POST /packages/{id}/regenerate`.
3. Lessons API
   - [x] `GET /lessons/packages/{id}` (lessons for package).
   - [x] `POST /lessons/packages/{id}` (create lesson in package).
   - [x] `GET /lessons/{id}`, `PATCH /lessons/{id}`, `DELETE /lessons/{id}`.
   - [x] `GET /lessons` (all lessons with filters).
4. Templates API
   - [x] `GET /templates`, `GET /templates/{id}`.
   - [x] `POST /templates/create`, `PATCH /templates/{id}`, `DELETE /templates/{id}`.
   - [x] `POST /templates/{id}/duplicate`.
5. Reminders API
   - [x] `GET /reminders/packages/{id}` (reminders for package).
   - [x] `GET /reminders` (general reminders list with pagination and filters).
   - [x] `PATCH /reminders/{id}` (activate/deactivate, reschedule).
6. Metrics API
   - [x] `GET /metrics/summary?from=&to=`.
   - [x] `GET /metrics/lessons/daily`, `GET /metrics/reminders/daily`.
7. Testing & docs
   - [ ] Unit tests for services.
   - [ ] Integration tests for API.
   - [ ] Update OpenAPI schema, generate client types.

## Stage 2 – Frontend MVP

1.  **Project setup:**
    - [x] Create `mini-app` directory.
    - [x] Initialize project using Vite (React + TypeScript).
    - [x] Install dependencies: `antd`, `react-query`, `axios`, `react-router-dom`, `zustand`.
    - [x] Configure folder structure (`pages`, `components`, `services`, `hooks`).

2.  **Authentication & API Client:**
    - [x] Implement `AuthProvider` to read `initData` and call `/api/v1/auth/login`.
    - [x] Configure `axios` with interceptors for JWT and refresh tokens.

3.  **Layout & Navigation:**
    - [x] Create main app layout (header, sidebar) with Ant Design.
    - [x] Configure routing for pages: `/`, `/packages`, `/packages/:id`, `/templates`, `/reminders`.

4.  **Dashboard:**
    - [x] Display key metrics from `/metrics/summary`.
    - [x] Show a list of upcoming lessons.

5.  **Packages Module:**
    - [x] Implement package list page: table with pagination, filters, and search.
    - [x] Implement package detail page: info, "Lessons" and "Reminders" tabs.
    - [x] Implement modals for creating/editing lessons and packages.

6.  **Templates Module:**
    - [x] Implement template list page.
    - [x] Add forms for CRUD operations on templates.

7.  **Telegram UI Integration:**
    - [x] Connect and manage native Telegram buttons (`MainButton`, `BackButton`).
    - [x] Implement theme change handling (light/dark).
    - [x] Ensure responsive, mobile-first design.

8.  **Testing:**
    - [x] Write unit tests for key components using Jest/RTL.
    - [x] Create an e2e smoke test (login -> create package) with Playwright.

## Stage 3 – Enhancements
1. [x] Reminders page with filters/actions (status, type, package filters).
2. [x] Settings page (profile, default timezone, notifications toggles).
3. [x] Advanced analytics (additional charts, breakdown by learner).
4. [x] Enhanced Dashboard with graphs and statistics.
5. [x] PackageDetail with tabs (lessons/reminders) and progress visualization.
6. [ ] Audit log/history display in package detail.
7. [ ] WebSockets or polling strategy for real-time updates (optional).

## Recent Fixes & Improvements
1. [x] **Fixed Reminders API**: Added missing general `/reminders` endpoint with pagination and filtering.
2. [x] **Fixed Reminders Filters**: Updated status options to match real system data (scheduled, sent, responded, failed, cancelled).
3. [x] **Added Reminder Type Filter**: Implemented filtering by reminder types (lesson_confirm, lesson_day_before, payment_week, etc.).
4. [x] **Fixed API Limits**: Increased packages API limit from 100 to 1000 to support frontend requirements.
5. [x] **Enhanced CRUD Functions**: Added `fetch_reminder_instances_paginated` with support for status, type, and package filtering.
6. [x] **Updated Frontend Components**: Fixed status colors, icons, and form validation in Reminders page.
7. [x] **Fixed Reminders Count Bug**: Fixed total count calculation when filtering by `reminder_type` - now count query includes proper joins.
8. [x] **Enhanced Reminders Search**: Search now works across comment, package title, and learner name (not just comment).
9. [x] **Updated API Documentation**: Aligned endpoint paths in docs to match implementation (`/create` suffix for POST operations).

## Stage 4 – Integration & Release
1. Bot integration
   - [ ] Add button/command в FSM для открытия мини-приложения (deep link).
   - [ ] Уведомления/оповещения о релизе.
2. Deployment pipeline
   - [ ] Dockerfiles для bot/api/frontend.
   - [ ] CI/CD scripts (lint/test/build/deploy).
   - [ ] Staging окружение.
3. QA & rollout
   - [ ] Регресс бота и API.
   - [ ] Финальные e2e тесты (bot ↔ mini app).
   - [ ] Постепенное включение пользователей.
4. Документация
   - [ ] User guide для преподавателя.
   - [ ] Техническая документация по API и архитектуре.
