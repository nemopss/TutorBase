# Service Layer Refactor Plan

## Goals
- Изолировать бизнес-логику пакетов/уроков/пресетов от FSM-обработчиков.
- Обеспечить переиспользование логики между Telegram-ботом и будущим REST API.
- Подготовить кодовую базу к добавлению авторизации и аудита (кто изменил данные).

## Модули и области ответственности

### `services/package_service.py`
- `create_package(session, *, learner_id, title, template_id=None, status='draft', start_date=None, end_date=None, timezone=None, total_lessons=None, notes=None, created_by=None)`
  - Валидирует входные данные, загружает связанные сущности (learner/template), создаёт пакет через `crud.create_lesson_package`.
  - При необходимости создаёт уроки из шаблона, возвращает DTO/модель.
- `update_package(session, package_id, *, title=None, status=None, timezone=None, notes=None, start_date=None, end_date=None, total_lessons=None, updated_by=None)`
  - Меняет поля пакета, вызывает `_sync_package_metrics`, `regenerate_package_reminders` при изменениях расписания/статуса.
- `delete_package(session, package_id)`
  - Проверяет наличие, выполняет удаление, очищает зависимые данные.
- `list_packages(session, *, filters, pagination)`
  - Роутер над `crud.fetch_lesson_packages_paginated`, доп. фильтры по ученику, статусу, периоду.
- `get_package(session, package_id)`
  - Возвращает пакет с уроками/статистикой.
- `regenerate_reminders(session, package_id)`
  - Оборачивает `regenerate_package_reminders`, обрабатывает ошибки.
- Хелперы: `_compute_progress(lessons)`, `_build_package_dto(package)`.

### `services/lesson_service.py`
- `create_lesson(session, package_id, *, scheduled_at, duration=None, status='scheduled', notes=None, homework_due_at=None, created_by=None)`
  - Сохраняет урок, пересчитывает метрики, триггерит регенерацию напоминаний.
- `update_lesson(session, lesson_id, *, scheduled_at=None, duration=None, status=None, notes=None, homework_due_at=None, updated_by=None)`
  - Обновляет поля, при изменении времени/статуса пересчитывает пакет/напоминания.
- `delete_lesson(session, lesson_id)`
  - Удаляет урок, обновляет метрики пакета, напоминания.
- `list_by_package(session, package_id)`
  - Возвращает упорядоченный список уроков.
- `get_lesson(session, lesson_id)`, `set_status(...)`, `set_notes(...)` — обёртки для FSM.

### `services/template_service.py`
- `list_templates(session)`
- `get_template(session, template_id)`
- `create_template(session, data, created_by=None)`
- `update_template(session, template_id, data, updated_by=None)`
- `delete_template(session, template_id)`
- `duplicate_template(session, template_id, *, name=None)`
- Доп. хелперы по парсингу расписания (`parse_weekly_schedule`, `format_weekly_schedule`).

### `services/reminder_service.py`
- Обёртки над `regenerate_package_reminders`, управление отдельными инстансами/правилами.
- Подготовка DTO напоминаний для API/фронта.

## Общие компоненты
- DTO в `services/dto.py` (pydantic models): `PackageDTO`, `LessonDTO`, `TemplateDTO`, `ReminderDTO`.
- `services/exceptions.py` — собственные исключения (`NotFound`, `ValidationError`, `Conflict`). FSM и API будут преобразовывать их в пользовательские сообщения/HTTP-ответы.
- `services/utils.py` — общие функции (например, `_lesson_stats`, `_sync_package_metrics`).

## Интеграция с существующим кодом
- Переместить `_sync_package_metrics`, `_lesson_stats`, `_parse_lesson_datetime`, `_compute_auto_end_date` из `handlers/admin_packages.py` в сервисы/утилиты.
- Обновить `services/package_scheduler.py`, чтобы он пользовался DTO или напрямую ORM, но вызвался через сервис.
- Обновить FSM:
  - В обработчиках оставить только парсинг параметров, вызов функции сервиса, ответ пользователю.
  - Обработать исключения сервисов → соответствующие `texts`/alert.

## План рефакторинга
1. Добавить новые модули `services/package_service.py`, `services/lesson_service.py`, `services/template_service.py`, `services/dto.py`, `services/exceptions.py` (пустые заглушки с TODO). — ✅ выполнено
2. Постепенно переносить функции из `handlers/admin_packages.py`:
   - Сначала пакетные операции (создание, обновление, удаление).
   - Затем CRUD уроков.
   - Затем пресеты.
3. После переноса обновить импорт в обработчиках, удалить дублирующийся код. — ✅ (основные обработчики переведены)
4. Добавить unit-тесты на сервисы (pytest + async fixtures). — TODO
5. Обновить документацию (mini_app_tasks, architecture doc) по завершении шага. — частично (обновлено `mini_app_tasks.md`)

## Интеграция с FSM (Stage 0.3)
1. Создать адаптер `handlers/admin_packages_service.py` (или обновить существующий модуль), где каждое действие FSM вызывает соответствующий метод сервиса.
2. Для каждого сценария:
   - Считать входящие данные из состояния.
   - Вызвать метод сервиса (`package_service.create_package`, `lesson_service.update_lesson` и т.д.).
   - Обработать исключения (`ServiceError`, `NotFound`, `ValidationError`) и отобразить нужный текст из `utils.texts`.
   - По результату подготовить UI (тексты/клавиатуры) на основе DTO, а не ORM объектов.
3. Удалить из `handlers/admin_packages.py` вспомогательные функции, перенесённые в сервисы (`_sync_package_metrics`, `_lesson_stats`, разбор дат/расписаний).
4. Проверить, что все FSM состояния (создание пакета, изменение урока, статус, заметка, удаление и т.п.) используют сервисы.
5. Прогнать smoke-тест: ручной сценарий через бота (создание пакета, добавление урока, смена статуса) для валидации.

## Вопросы / Зависимости
- Требуется ли аудит (кто изменил) с первого этапа? — Пока достаточно опционального `updated_by` в параметрах.
- Нужно ли поддерживать транзакции на уровне сервиса (commit/rollback) или оставляем ответственность на вызывающем коде? — Предлагается оставить контроль транзакций в обработчиках/роутерах (перед вызовом сервисов), сервисы принимают активную сессию.
- Как обрабатывать сериализацию дат/времени и часовых поясов? — Сервисы работают с `datetime` в UTC, DTO форматируют под потребности API/UI.
