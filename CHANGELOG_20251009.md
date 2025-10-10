# Changelog - 2025-10-09

## Исправления и улучшения

### 1. Исправлена проблема с кнопкой "Открыть на весь экран" на iPad

**Проблема:** Кнопка разворачивания не отображалась в Telegram Web App на iPad.

**Решение:**
- **App.tsx**: Убрана проверка `isExpanded` перед вызовом `tg.expand()`, добавлены вызовы `enableClosingConfirmation()` и установка цветов
- **index.html**: Добавлены мета-теги для iOS/iPad (`apple-mobile-web-app-capable`, `viewport-fit=cover`)
- **index.css**: Добавлены CSS фиксы для viewport (`position: fixed`, `100dvh`, `overscroll-behavior: none`)
- **useTelegram.ts**: Добавлен обработчик `viewportChanged` и повторная попытка разворачивания через 100мс

### 2. Исправлена проблема с volumes в docker-compose.yml

**Проблема:** Prometheus и Grafana создавались при автодеплое несмотря на то, что были закомментированы.

**Решение:**
- Закомментирован раздел `volumes` в docker-compose.yml, который ссылался на `prometheus_data` и `grafana_data`

### 3. Добавлена возможность создания ученика напрямую из chat_id

**Новый функционал:**

#### Backend:
- **models.py**: Добавлено поле `notifications_enabled` в модель `Learner`
- **Migration**: Создана миграция `20251009_add_learner_notifications_enabled.py`
- **crud.py**: 
  - Добавлена функция `create_learner_from_chat_id()` для создания ученика из chat_id
  - Обновлена функция `update_learner()` для поддержки `notifications_enabled`
- **schemas/learners.py**: Добавлены новые схемы:
  - `CreateLearnerFromChatIdRequest`
  - `UpdateLearnerNotificationsRequest`
  - Расширена `LearnerResponse` (добавлены `notifications_enabled`, `chat_id`)
- **routes/learners.py**: Добавлены новые endpoints:
  - `POST /learners` - создание ученика из chat_id
  - `PATCH /learners/{learner_id}/notifications` - управление уведомлениями
  - Обновлен `GET /learners` для возврата новых полей

#### Frontend:
- **LearnerForm.tsx**: Новый компонент-форма для добавления учеников и управления уведомлениями
- **Learners.tsx**: Новая страница для управления учениками с возможностью:
  - Просмотр всех учеников
  - Добавление нового ученика через chat_id
  - Включение/отключение уведомлений для каждого ученика
- **App.tsx**: Добавлен роут `/learners`
- **AppLayout.tsx**: Добавлен пункт меню "Learners" с иконкой TeamOutlined

### 4. Добавлена возможность отключить все уведомления ученику

**Функционал:**
- При отключении уведомлений для ученика (`notifications_enabled = False`), все напоминания будут пропускаться
- **reminders.py**: Добавлена проверка флага `notifications_enabled` перед отправкой уведомлений
- Пропущенные напоминания помечаются статусом 'skipped' с комментарием

## API Endpoints

### Новые endpoints:

```
POST /api/learners
Body: {
  "chat_id": 123456789,
  "display_name": "Имя ученика",
  "notes": "Опциональные заметки"
}

PATCH /api/learners/{learner_id}/notifications
Body: {
  "notifications_enabled": true/false
}

GET /api/learners
Response: {
  "items": [{
    "id": 1,
    "display_name": "Имя ученика",
    "notifications_enabled": true,
    "chat_id": 123456789
  }]
}
```

## Инструкции по деплою

1. Закоммитить и запушить изменения
2. GitHub Actions автоматически соберет и задеплоит новые образы
3. На сервере выполнить миграцию базы данных:
   ```bash
   cd /srv/applications-bot/current
   docker compose exec applications_bot alembic upgrade head
   ```
4. Перезапустить контейнеры (если нужно):
   ```bash
   docker compose restart
   ```

## Примечания

- Поле `notifications_enabled` по умолчанию установлено в `True` для всех существующих и новых учеников
- При создании ученика из chat_id автоматически создается `BotUser`, если его еще нет
- Если `BotUser` уже существует, но без связанного `Learner`, будет создан только `Learner`
