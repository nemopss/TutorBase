# Telegram Mini App Roadmap

## Backend API Plan

- **Стек**: FastAPI (или другой ASGI) поверх текущего асинхронного SQLAlchemy.
- **Слоистая архитектура**: `api` (роутеры) → `services` (use-case логика) → `database/crud`.
- **Аутентификация**:
  - Endpoint `/api/v1/auth/login` принимает `initData`, валидирует подпись Telegram, создаёт/обновляет пользователя.
  - Таблица `users` с полями: `id`, `role` (`admin`, `teacher`, на будущее `student`), `telegram_id`, `username`, `display_name`, `created_at`, `updated_at`.
  - Выдача короткоживущего JWT + `refresh` endpoint для продления.
- **Основные API-модули**:
  - `/packages`: CRUD пакетов, пересчёт напоминаний, фильтры (ученик, статус, дата), пагинация.
  - `/lessons`: добавление, обновление, удаление уроков; изменение статусов, заметок, длительности.
  - `/templates`: управление пресетами (создание, редактирование, копирование, удаление).
  - `/reminders`: просмотр и управление напоминаниями, повторная отправка (в перспективе).
  - `/metrics`: агрегаты по урокам, статусам, подтверждениям, отменам и напоминаниям (почасово/дневно/за период).
  - `/learners`: выбор ученика, расширение для будущего кабинета ученика.
- **DTO/Ответы**: Pydantic-модели (`LessonPackageOut`, `LessonOut`, `ReminderInstanceOut`, `TemplateOut`, `MetricsSummaryOut`), прогресс пакета `все/проведено/отменено` формируется через `_lesson_stats`.
- **Служебные задачи**:
  - Вынести логику из `handlers/admin_packages.py` в сервисы, чтобы шарить её между FSM и API.
  - Добавить аудит (кто и когда изменил урок/пакет), soft-delete при необходимости.
  - OpenAPI-документация, логирование запросов, rate limiting, unit + интеграционные тесты.
  - Готовность к расширению для роли ученика (авторизация, фильтрация по владельцу).

## Frontend Mini App Plan

- **Стек**: React + TypeScript + Vite, Ant Design, React Query, React Router, React Hook Form + Zod, Recharts.
- **Интеграция с Telegram**: `Telegram.WebApp.ready()`, использование `MainButton`/`BackButton`, обработка изменения темы, `expand()` для полноэкранного режима.
- **Auth-поток**: `AuthProvider` читает `initData`, вызывает `/auth/login`, сохраняет токен, настраивает интерцепторы, поддерживает `refresh`.
- **Роутинг и страницы**:
  - `/` Dashboard: ближайшие уроки, карточки метрик, графики.
  - `/packages` список пакетов с фильтрами и поиском.
  - `/packages/:id` карточка пакета (инфо, вкладки "Уроки", "Напоминания", "История").
  - `/templates` менеджер пресетов.
  - `/reminders` журнал напоминаний (опция).
  - `/settings` профиль, дефолтный часовой пояс, уведомления.
- **Ключевые компоненты**:
  - Таблицы пакетов и уроков с адаптивностью и быстрыми действиями.
  - Модальные формы: создание/редактирование пакета, урока, настройки напоминаний.
  - Компоненты прогресса (бейджи статусов, индикаторы `all/completed/cancelled`).
  - Общие элементы UI: Header, Sidebar/Drawer, LessonStatusBadge, StatsCards.
- **Состояние**:
  - React Query для данных (`usePackages`, `usePackage`, `useLessons`, `useTemplates`, `useMetrics`).
  - Zustand/Context для UI (фильтры, модалки, текущее меню).
  - Оптимистичные апдейты, автоматический рефетч при фокусе, "pull to refresh".
- **Формы и UX**:
  - React Hook Form + Zod для валидации дат/времени/длительности.
  - Подтверждения операций через Ant `Modal.confirm`.
  - Loader и уведомления интегрированы с Telegram WebApp (`showLoaderIndicator`, `showPopup`).
- **Адаптивность**: mobile-first, таблицы превращаются в карточки на узких экранах, BackButton синхронизирован с Router.
- **Разработка и тесты**: ESLint/Prettier, Jest/RTL для компонентов, Playwright/Cypress для e2e (моки API).
- **Дорожная карта фронта**: bootstrap → авторизация → Dashboard → Packages → формы уроков → Templates → Metrics → Reminders/Settings → интеграция с Tg UI → тестирование.
