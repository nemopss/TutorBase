# Notification System: Production Pilot Runbook

## Цель

Этот runbook описывает безопасный порядок первого production rollout новой notification-системы TutorBase на сервере Timeweb.

Документ рассчитан на сценарий:

- deploy идёт через GitHub Actions на `master`;
- production stack живёт в `/srv/tutorbase/current`;
- teacher-facing управление делается через страницу `Уведомления NEW`;
- автоматический Celery Beat для новой системы ещё не включён глобально;
- реальный pilot запускается вручную через UI-кнопки `Обработать pending jobs` и `Запустить delivery tick`.

## Важное ограничение

Текущий workflow [`deploy.yml`](../.github/workflows/deploy.yml) **не выполняет `alembic upgrade head` явно**.

Из кода репозитория следует только это:

- образы собираются и публикуются;
- сервер делает `git pull`;
- `docker compose pull` и `docker compose up -d` перезапускают нужные сервисы.

Вывод:

- если на production миграции действительно применяются автоматически, это происходит **вне кода этого репозитория**;
- перед первым rollout новой notification-системы нужно **проверить этот факт отдельно**;
- если такой автоматизации нет, миграция `20260407_notifications` должна быть применена вручную.

## Что должно быть уже готово до rollout

Перед первым production pilot должны быть выполнены все пункты:

1. Ветка `feat/notification-system-redesign` слита в `master`.
2. На production доступна новая страница `Уведомления NEW`.
3. На production доступна страница `Группы`.
4. Есть хотя бы один тестовый или низкорисковый ученик для первого pilot.
5. Teacher понимает, что:
   - `Старая система` = работают только legacy reminders;
   - `Тестовый режим` = новая система строит план, но не должна становиться основным каналом для всех;
   - `Новая система` = для выбранного ученика или глобально legacy reminders подавляются.

## Преддеплойная проверка

Перед merge/push в `master`:

1. Пройти backend tests:
   ```bash
   .venv/bin/pytest tests/notifications tests/services/test_reminder_scheduler.py
   ```
2. Пройти frontend smoke:
   ```bash
   cd mini-app
   npm test -- --runInBand Notifications.test.tsx
   npm run build
   ```
3. Проверить, что worktree не содержит случайных файлов в commit.
4. Убедиться, что design doc `docs/notification-system-redesign.md` не попадёт в commit.

## Миграционная проверка на production

### Вариант A. Миграции реально применяются автоматически

Если у вас вне репозитория уже настроен автоматический `alembic upgrade head`, после deploy нужно только подтвердить факт:

1. Проверить текущую head revision.
2. Проверить наличие новых таблиц:
   - `notification_categories`
   - `notification_templates`
   - `notification_rules`
   - `notification_instances`
   - `notification_delivery_attempts`
   - `notification_jobs`
   - `learner_groups`
   - `group_members`
   - `lesson_participant_states`
3. Проверить новые поля в `lessons`:
   - `has_homework`
   - `homework_text`

### Вариант B. Автомата нет

Если автомата нет, после deploy выполнить вручную:

```bash
ssh <server>
cd /srv/tutorbase/current
docker compose exec api alembic upgrade head
```

После этого проверить:

```bash
docker compose exec api alembic current
```

Ожидаемо: текущая revision должна совпадать с head, включающей notification migration.

## Постдеплойная smoke-проверка

Сразу после production deploy:

1. Открыть mini-app.
2. Перейти на страницу `Уведомления NEW`.
3. Проверить, что страница открывается без 500/422.
4. Открыть `Настройки` и убедиться, что:
   - общий режим не стал `Новая система` автоматически;
   - виден блок `Текущий статус пилота`;
   - виден `Чеклист безопасного rollout`;
   - видны `Ручной запуск пилота`;
   - виден `Пилот по ученикам`.
5. Открыть `Шаблоны` и убедиться, что seeded system templates появились.
6. Открыть `Правила` и убедиться, что recommended draft rules появились.
7. Открыть `Напоминания LEGACY` и убедиться, что старая страница доступна.

## Безопасный порядок первого pilot

### Этап 1. Оставить global mode безопасным

В `Уведомления NEW -> Настройки`:

1. Оставить общий режим `Старая система` или `Тестовый режим`.
2. Не включать `Новая система` глобально.

Причина:

- глобальный `new` сразу подавит legacy reminders для всех учеников;
- first pilot должен быть точечным.

### Этап 2. Собрать план новой системы

В `Уведомления NEW -> Настройки`:

1. Нажать `Обработать pending jobs`.
2. Если нужно, перейти в `Правила` и нажать `Обновить план уведомлений`.
3. Открыть `Очередь`.

Что проверить:

- появились planned/test instances;
- нет неожиданной пустой очереди;
- warnings читаемы;
- нет массовых `missing_contact`, если pilot ученик уже должен получать сообщения;
- нет неожиданных конфликтов уроков.

### Этап 3. Выбрать одного pilot learner

В `Уведомления NEW -> Настройки -> Пилот по ученикам`:

1. Найти одного низкорискового ученика.
2. Перевести его в `Новая система`.
3. Подтвердить modal.

Проверка после этого:

- у ученика effective mode = `Новая система`;
- для этого ученика legacy scheduler больше не должен отправлять старые reminders;
- для остальных учеников всё остаётся по старой схеме.

### Этап 4. Дождаться или подготовить due instance

Перед реальной отправкой нужно убедиться, что:

- у pilot learner есть due notification;
- `delivery_enabled = true`;
- в `Очереди` видно, что уведомление реально готово к отправке.

Если в `Настройки` блок `Ручной запуск пилота` показывает `Готово к реальной отправке сейчас: 0`, кнопку `Запустить delivery tick` использовать рано.

### Этап 5. Выполнить контролируемую реальную отправку

Только когда ready count > 0:

1. В `Настройки` нажать `Запустить delivery tick`.
2. Подтвердить modal.
3. Сразу открыть:
   - `Очередь`
   - `События`
   - при необходимости `LOGS_CHAT_ID` / teacher log chat

Что считается успешным:

- notification instance переходит в `Отправлено`;
- появляется delivery attempt с `Telegram message_id`;
- pilot learner реально получает сообщение;
- если это confirmation message, callback кнопки отображаются корректно.

### Этап 6. Проверить callback flow

Если pilot notification содержит кнопки подтверждения:

1. Нажать `подтвердить` или `не смогу` на реальном сообщении.
2. Проверить:
   - в `Событиях` появился `response` или `teacher_alert`;
   - `lesson_participant_state` обновился;
   - для decline событие помечено как `requires_attention`.

## Что смотреть при проблемах

### Если очередь пустая

Проверить:

- есть ли active rules;
- есть ли подходящие upcoming lessons/packages;
- не выключены ли notifications у learner;
- не все ли rules остались в `draft`;
- не blocked ли событие quiet hours/prefs/category eligibility.

### Если planned queue есть, но real send не идёт

Проверить:

- ready count в `Настройки`;
- `delivery_enabled=true`;
- instance status = `scheduled`;
- `effective_scheduled_for <= now`;
- celery worker жив;
- ручной `delivery tick` реально был поставлен в очередь.

### Если сообщение ушло, но callback не обработался

Проверить:

- bot service после deploy обновился;
- handler `handlers/notifications.py` подключён;
- в `notification_delivery_attempts` есть `provider_message_id`;
- callback_data соответствует `notif_confirm_lesson_{instance_id}` / `notif_decline_lesson_{instance_id}`.

### Если появляются неожиданные дубли

Проверить:

- нет ли у ученика двух активных уроков в один слот;
- что пишет queue details drawer в warnings;
- нет ли двух разных `lesson_id` на одно и то же время;
- не был ли повторно запущен ручной `delivery tick` на те же due instances до смены статуса.

## Когда можно расширять rollout

Расширять pilot на следующих учеников можно только если первый pilot прошёл без критических проблем:

- новые сообщения реально доходят;
- callbacks работают;
- teacher понимает queue/activity;
- нет системных дублей;
- alerts читаемы;
- legacy suppression работает только для учеников в `new`.

## Когда можно включать global new

Global `Новая система` допустима только если:

1. Был минимум один успешный learner pilot.
2. Проверен реальный send и реальный callback.
3. Нет критических проблем в `Событиях`.
4. Teacher понимает, как пользоваться `Очередь`, `События` и `Ручной запуск пилота`.
5. Есть план отката.

## Откат

Если pilot пошёл плохо:

1. Для pilot learner переключить override обратно в `legacy` или `inherit`.
2. Общий режим не переводить в `new`.
3. Не запускать ручной `delivery tick` повторно, пока не понятна причина.
4. Разобрать:
   - `Очередь`
   - `События`
   - `notification_delivery_attempts`
   - teacher log chat

## Минимальный production checklist

Перед первым реальным pilot:

- [ ] deploy выполнен;
- [ ] миграция подтверждена;
- [ ] `Уведомления NEW` открываются;
- [ ] system templates и draft rules появились;
- [ ] общий режим не `new`;
- [ ] один pilot learner выбран;
- [ ] queue/explanation просмотрены;
- [ ] ready count > 0 перед ручным send;
- [ ] teacher понимает, как откатить pilot learner обратно.
