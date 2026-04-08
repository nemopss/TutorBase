# TutorBase

Telegram бот, FastAPI API и React mini-app для управления записями и уроками TutorBase.

## 🧱 Состав проекта

- **`bot.py`** — Telegram-бот (Aiogram) с Redis FSM.
- **`api/`** — REST API на FastAPI, JWT аутентификация и PostgreSQL в качестве основной БД.
- **`mini-app/`** — React/Vite мини-приложение для Telegram WebApp.
- **`nginx/`** — реверс-прокси и TLS-конфигурация.
- **`docker-compose.yml`** — продакшн-стек.

## ⚙️ Подготовка окружения

1. Создайте `.env` на базе примера:
   ```bash
   cp .env.example .env
   ```
2. Заполните обязательные поля:
   - `BOT_TOKEN`, `ADMINS`, `LOGS_CHAT_ID`, `ADMIN_CHAT_ID`;
   - `REDIS_URL`, `JWT_SECRET`, `JWT_*_EXPIRES_SECONDS`;
   - `MINI_APP_URL`, `CORS_ORIGINS`.
3. Пропишите `POSTGRESQL_HOST/PORT/USER/PASSWORD/DBNAME` — прод и dev уже работают на PostgreSQL; SQLite оставлен только для оффлайн-режима (`DB_PATH`).
4. Примените миграции:
   ```bash
   alembic upgrade head
   ```

## 🧪 Локальная разработка

### Вариант 1. Docker Compose

В репозитории есть dev-стек (`docker-compose.dev.yml`), который поднимает Postgres, Redis, API (с авто-релоадом) и Vite Dev Server.

```bash
cp .env.dev.example .env.dev

docker compose -f docker-compose.dev.yml up -d postgres redis

docker compose -f docker-compose.dev.yml up -d --build api mini-app

docker compose -f docker-compose.dev.yml exec api alembic upgrade head
```

Особенности dev-режима:
- `DEV_MODE=true` включает мок авторизацию. Мини-приложение отправляет `init_data="dev"`, а API создаёт фиктивного пользователя (`DEV_TELEGRAM_ID`, `DEV_USERNAME`, `DEV_DISPLAY_NAME`).
- Фронт доступен на `http://localhost:5173`, API — на `http://localhost:8001/api/v1`.
- Бот можно включить по требованию: `docker compose -f docker-compose.dev.yml --profile bot up -d bot`.

### Вариант 2. Ручной запуск (venv + npm)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

alembic upgrade head

uvicorn api.app:create_app --factory --reload --port 8001

cd mini-app
npm install
npm run dev
```

> Для работы мини-приложения без Telegram включите dev-режим: `VITE_DEV_MODE=true`, `VITE_DEV_INIT_DATA=dev` (значения совпадают с `.env.dev.example`).

### Тесты

- Backend: `pytest`
- Mini-app: `cd mini-app && npm test`

## 👩‍🏫 Роли и доступ

- При первом логине все пользователи получают роль `viewer`. Только ID из `ADMINS` приходят как `admin`.
- К странице `/admin` допускаются только пользователи с ролью `admin`; там можно менять роли (`viewer` ↔ `teacher` ↔ `admin`).
- Любые роли ниже `teacher` не видят основное приложение — отображается страница «Доступ ограничен».

## 🚀 Автодеплой

Релизы отслеживает GitHub Actions (`.github/workflows/deploy.yml`):

1. Job `changes` анализирует, какие части репозитория изменились.
2. Build job собирает и пушит образы **только** для изменённых сервисов.
3. Deploy job по SSH:
   - `git pull`
   - точечно обновляет контейнеры (бот, API, фронт);
   - перезапускает nginx при изменениях API/фронта/конфига;
   - при изменении `docker-compose.yml` пересоздаёт весь стек.

> Понадобятся секреты: `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`, `GHCR_PAT`.

### Ручное обновление
```bash
ssh user@server
cd /srv/tutorbase/current
git pull
docker compose pull
docker compose up -d --remove-orphans
```

## 🔐 Практики безопасности

- Храните `.env` вне репозитория, `database/` — с правами только для нужных сервисов.
- Открывайте наружу только nginx (firewall / security groups).
- Рассмотрите fail2ban + rate-limit в nginx.
- Регулярно пересобирайте образы, обновляйте зависимости (`pip`, `npm`, `apk`).
- Настройте бэкапы PostgreSQL (`pg_dump`, snapshot). Скрипт переноса данных из SQLite в PostgreSQL лежит в `OLD_DB/data_migrate.load` (pgloader).

## 📁 Полезные каталоги

- `alembic/` — миграции БД.
- `handlers/`, `services/`, `filters/` — логика бота.
- `mini-app/src/pages/Admin.tsx` — админ-панель.
- `monitoring/` — Prometheus/Grafana шаблоны.
- `docs/` — архитектурные заметки и планы.
  - Для первого production pilot новой notification-системы используйте [docs/notifications_prod_pilot_runbook.md](docs/notifications_prod_pilot_runbook.md).

## 📄 License

MIT
