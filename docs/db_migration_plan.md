# Database Migration Plan for Mini App

## 1. Users Table
- **New table**: `users`
  - `id` (PK, autoincrement)
  - `telegram_id` (BigInt, unique) — chat/user ID из Telegram.
  - `username` (String, nullable)
  - `display_name` (String) — имя, показываемое в UI.
  - `role` (String, length 32) — `admin`, `teacher`, `student` (на будущее).
  - `created_at`, `updated_at` (DateTime timezone=True, default `_utc_now`).
  - `last_login_at` (DateTime timezone=True, nullable).
- **Purpose**: авторизация мини-приложения, связь с преподавателем/админом, аудит изменений.

## 2. Linking Users to Domain Models
- **LessonPackage**: добавить `updated_by_user_id` (FK → users.id, nullable).
- **Lesson**: добавить `updated_by_user_id` (FK → users.id, nullable).
- В сервисах при изменении пакета/урока писать `updated_by_user_id` + `updated_at`.
- На этапе создания можно записывать `created_by_user_id` (опционально, если потребуется).

## 3. Additional Indexes
- `lessons`: индекс `ix_lessons_package_id_scheduled_at` (если ещё нет) — ускоряет выборку уроков по пакету + сортировке.
- `lesson_packages`: индекс по `learner_id` и `status` для фильтров в списке пакетов.
- `reminder_instances`: убедиться в наличии индекса `package_id` + `status` (для API напоминаний).

## 4. Data Migration Steps
1. Создать Alembic-миграцию `add_users_table_and_audit_fields`.
   - Создать таблицу `users`.
   - Добавить столбцы и внешние ключи в `lesson_packages` и `lessons`.
   - Создать индексы (если отсутствуют).
2. Backfill (если требуется):
   - Для существующих записей `lesson_packages`/`lessons` можно оставить `updated_by_user_id = NULL`.
   - При появлении пользователей вручную заполнить пользователя-админа (через SQL скрипт или сервис).
3. Обновить модели в `database/models.py`:
   - Добавить модель `User`. — ✅
   - Связи `User` ↔ `LessonPackage`/`Lesson` (relationship `updated_by`). — TODO (логика планируется позже)
4. Обновить CRUD/сервисы для поддержки полей `updated_by_user_id`. — TODO (сейчас поля добавлены, запись пользователя реализуется позже)

## 5. Future Considerations
- **Student role**: позже добавим связку `Learner.user_id` для доступа учеников.
- **Auditing**: при необходимости можно расширить до `created_by`, `deleted_at`, `soft-delete`.
- **Permissions**: после появления `users` можно использовать их в фильтрах API (например, преподаватель видит только свои пакеты).
