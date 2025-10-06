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
   - [ ] Set up FastAPI app with router structure `/api/v1`.
   - [ ] Configure logging, error handling, OpenAPI docs.
   - [ ] Integrate DB session dependency (shared with bot).

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
   - [x] `POST /packages` (from template or manual).
   - [x] `GET /packages/{id}`, `PATCH /packages/{id}`, `DELETE /packages/{id}`.
   - [x] `POST /packages/{id}/regenerate`.
3. Lessons API
   - [x] `GET /packages/{id}/lessons`.
   - [x] `POST /packages/{id}/lessons`.
   - [x] `GET /lessons/{id}`, `PATCH /lessons/{id}`, `DELETE /lessons/{id}`.
4. Templates API
   - [x] CRUD endpoints + `/templates/{id}/duplicate`.
5. Reminders API
   - [x] `GET /packages/{id}/reminders`.
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
    - [ ] Create `mini-app` directory.
    - [ ] Initialize project using Vite (React + TypeScript).
    - [ ] Install dependencies: `antd`, `react-query`, `axios`, `react-router-dom`, `zustand`.
    - [ ] Configure folder structure (`pages`, `components`, `services`, `hooks`).

2.  **Authentication & API Client:**
    - [ ] Implement `AuthProvider` to read `initData` and call `/api/v1/auth/login`.
    - [ ] Configure `axios` with interceptors for JWT and refresh tokens.

3.  **Layout & Navigation:**
    - [ ] Create main app layout (header, sidebar) with Ant Design.
    - [ ] Configure routing for pages: `/`, `/packages`, `/packages/:id`, `/templates`, `/settings`.

4.  **Dashboard:**
    - [ ] Display key metrics from `/metrics/summary`.
    - [ ] Show a list of upcoming lessons.

5.  **Packages Module:**
    - [ ] Implement package list page: table with pagination, filters, and search.
    - [ ] Implement package detail page: info, "Lessons" and "Reminders" tabs.
    - [ ] Implement modals for creating/editing lessons and packages.

6.  **Templates Module:**
    - [ ] Implement template list page.
    - [ ] Add forms for CRUD operations on templates.

7.  **Telegram UI Integration:**
    - [ ] Connect and manage native Telegram buttons (`MainButton`, `BackButton`).
    - [ ] Implement theme change handling (light/dark).
    - [ ] Ensure responsive, mobile-first design.

8.  **Testing:**
    - [ ] Write unit tests for key components using Jest/RTL.
    - [ ] Create an e2e smoke test (login -> create package) with Playwright.

## Stage 3 – Enhancements
1. Reminders page with filters/actions.
2. Settings page (profile, default timezone, notifications toggles).
3. Advanced analytics (additional charts, breakdown by learner).
4. Audit log/history display in package detail.
5. WebSockets or polling strategy for real-time updates (optional).

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
