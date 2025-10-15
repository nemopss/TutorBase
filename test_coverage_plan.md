# План покрытия проекта тестами

Документ описывает целевое покрытие тестами для трёх основных частей системы: FastAPI‑сервиса, мини‑приложения (React/Vite) и Telegram‑бота на Aiogram. Для каждой подсистемы указаны уровни тестирования, приоритетные сценарии и вспомогательная инфраструктура.

## 1. API (FastAPI + SQLAlchemy)

### 1.1 Юнит‑тесты (pytest, asyncio)
- **Сервисы (`services/*.py`)**
  - `package_service` – сценарии создания/обновления/удаления пакетов, пересчёт метрик, генерация уроков из шаблонов, обработка NotFound/ValidationError.
  - `lesson_service` – CRUD, пересчёт метрик пакета, фильтрация по статусу/поиску.
  - `template_service` – CRUD, дублирование.
  - `package_scheduler` – генерация правил и инстансов напоминаний для разных типов уроков/таймингов (boundary cases: прошедшие уроки, отсутствующие learner/chat, нестандартные тайм‑зоны после доработок).
  - `utils.timezone` и `utils.datetime` – конвертации, parse/format, работа с `None`.
- **Хелперы (`api/security.py`, `api/dependencies.py`)**
  - Верификация Telegram initData, генерация токенов, роль‑чекеры.
  - Поведение при отсутствии/невалидном токене (TokenVerificationError).

### 1.2 Интеграционные тесты (pytest + httpx AsyncClient + тестовая БД)
- **Авторизация**
  - `POST /api/v1/auth/login` – happy path, неправильный `init_data`, пользователь без `id`.
  - `POST /api/v1/auth/refresh` – валидный/просроченный/поддельный refresh.
- **Пакеты (`/packages`)**
  - Список с фильтрами `status`, `search`, `learner_id`, пагинация.
  - Создание напрямую и из шаблона, обязательность `start_date`.
  - Обновление: изменение статуса, заметок, дат (в т.ч. очистка до `null`), регенерация напоминаний (проверить, что созданы инстансы).
  - Удаление (403 для не‑админа, 404 для несуществующего).
- **Уроки (`/lessons`)**
  - Список/по пакету, создание с авто‑индексом, обновление статуса, удаление с пересчётом метрик.
- **Шаблоны (`/templates`)**
  - CRUD, дубликат, валидация `lesson_count`.
- **Напоминания (`/reminders`)**
  - Листинг с фильтрами, обновление статуса `active/comment`, проверка 404.
- **Learners / Users / Metrics**
  - Включая роль‑бэйз доступ и метрики с разными типами дат (проверка фикса `_coerce_row_to_date`).
- **Health/metrics**
  - `/health`, `/ready`, `/live`, `/metrics` (Prometheus).

*Инфраструктура*: отдельная временная SQLite (или Postgres в CI), миграции alembic, фикстуры для фабрик моделей и токенов.

### 1.3 Контрактные/снапшот тесты
- Pydantic схемы vs. OpenAPI – тест на отсутствие регресса сериализации (`response_model` + `jsonable_encoder`).
- Swagger/OpenAPI генерация – `fastapi.testclient` для smoke.

### 1.4 Статический анализ
- mypy (async aware), Ruff/flake8, sqlfluff для SQL (опционально).

## 2. Mini-App (React/Vite + Ant Design)

### 2.1 Юнит‑тесты (Jest + React Testing Library)
- Хуки: `useAuth`, `useTelegram`, `useDebounce`, `useResponsiveStyles`.
- Компоненты форм: `PackageForm`, `LessonForm`, `LearnerForm`, `TemplateForm` – проверка валидации, преобразования даты (в т.ч. отправка `null` на очистку).
- Общие компоненты: `PageHeader`, `AppLayout` – рендеринг в светлой/тёмной теме, навигация.

### 2.2 Интеграционные тесты (Jest + MSW)
- Сценарии страниц: `Packages`, `Lessons`, `Reminders`, `Dashboard`, `Analytics`, `Admin`.
- Энд‑ту‑энд авторизации через `useAuth`: имитация `initData`, успешный и ошибочный логин, автоматическое обновление токена.
- Обработка ошибок API (message/error states), фильтры и пагинация.

### 2.3 E2E (Playwright)
- Smoke на ключевые пользовательские потоки (десктоп/мобайл):
  1. Авторизация в мини‑аппе.
  2. Создание пакета из шаблона + переход на `PackageDetail`.
  3. Редактирование урока, переключение на календарь.
  4. Управление напоминанием (изменение статуса, комментария).
  5. Управление статом (Admin: смена роли).
- Проверка отображения ошибок (offline, 401 → logout).

### 2.4 Линтинг/типизация
- ESLint (TypeScript config), Stylelint (если стили), TypeScript strict mode (постепенное ужесточение).

## 3. Telegram Bot (Aiogram v3)

### 3.1 Юнит‑тесты
- **Handlers**
  - `start`, `application`, `funnel`, `reminders`, `admin`, `admin_packages`, `cases`.
  - Проверка FSM переходов, инлайн клавиатур, формируемых текстов.
  - Исключительные ситуации (`TelegramBadRequest`, пустые данные, DB ошибки).
- **Middlewares**
  - `DbSessionMiddleware` – коммит/ролбек.
  - `RateLimitMiddleware` – превышение лимита + fail-open при отключенном Redis.
  - `UserTrackingMiddleware` – upsert bot_user.
- **Services**
  - `ReminderScheduler` – обработка due инстансов, поведение при `pending`, ручлент логирования.

### 3.2 Интеграционные тесты (AIOTelegramBotApi или aiogram testkit)
- Поднятие тестового бота с моками Telegram API (aiogram’s `MockedBot`) и in-memory Redis.
- Сквозные сценарии: подача заявки, запись на диагностику, подтверждение/отказ напоминания, панель администратора (ролевая проверка).
- Параллельный прогон нескольких обновлений для проверки rate limiting.

### 3.3 E2E (по возможности)
- Использование Telegram Bot API Sandbox или локального `aiogram` mocker для smoke‑check деплоя (запуск бота, отправка `/start`, получение reply).

## 4. Инфраструктура и процессы

- **CI pipeline**
  - Линтеры и юнит‑тесты (Python + TypeScript) на каждом PR.
  - Интеграционные тесты API на пред‑мерже.
  - E2E (Playwright) в nightly или перед релизом (можно параллелизировать).
  - Покрытие (coverage.py + Jest) с порогами и отчётами (Codecov/Sonar).
- **Фабрики/фикстуры**
  - Общий пакет фикстур для БД, Redis (fakeredis), Telegram пользователей, токенов.
  - Seed‑скрипт для Playwright (через REST API).
- **Набор тестовых данных**
  - Шаблонные JSON/CSV для воспроизведения сценариев (applications, packages, reminders).

## 5. Приоритизация внедрения

1. **Короткий цикл**: юнит‑тесты сервисов API + утилит, хуки React, middleware бота; запуск линтеров в CI.
2. **Среднесрочно**: интеграционные тесты API + MSW тесты мини‑аппа; smoke сценарии ReminderScheduler, auth flow mini‑аппа.
3. **Долгосрочно**: полные E2E (Playwright, aiogram testkit), покрытия администратора и сложных FSM‑флоу, нагрузочные проверки (по мере необходимости).

Документ следует актуализировать после внедрения каждой группы тестов и отражать покрытие/пробелы в отдельном отчёте CI.
