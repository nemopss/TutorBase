# KSU Applications Bot

Telegram бот, FastAPI API и React mini-app для управления записями и уроками KSU.

## 🧱 Состав проекта

- **`bot.py`** — Telegram-бот (Aiogram) с Redis FSM.
- **`api/`** — REST API на FastAPI, JWT аутентификация, SQLite (по умолчанию) или внешняя БД.
- **`mini-app/`** — React/Vite мини-приложение для Telegram WebApp.
- **`nginx/`** — реверс-прокси и TLS-конфигурация.
- **`docker-compose.yml`** — продакшн-стек.

## ⚙️ Подготовка окружения

1. Скопируйте пример конфигурации:
   ```bash
   cp .env.example .env
   ```
2. Заполните ключевые переменные:
   - `BOT_TOKEN` — токен Telegram-бота.
   - `ADMINS` — JSON-массив ID админов (`[123,456]`), именно эти пользователи получат роль `admin`.
   - `LOGS_CHAT_ID`, `ADMIN_CHAT_ID` — каналы/чаты для уведомлений.
   - `REDIS_URL` — адрес Redis (`redis://redis:6379/0` в docker, `redis://localhost:6379/0` локально).
   - `JWT_SECRET`, `JWT_ACCESS_EXPIRES_SECONDS`, `JWT_REFRESH_EXPIRES_SECONDS`.
   - `MINI_APP_URL`, `CORS_ORIGINS` — адрес фронта.

## 🧪 Локальная разработка

### Python-окружение
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Запуск компонентов
- Бот: `python bot.py`
- API локально c uvicorn:
  ```bash
  uvicorn api.main:app --reload --port 8001
  ```
- Mini-app:
  ```bash
  cd mini-app
  npm install
  npm run dev
  ```
  Используйте туннель (ngrok/localhost.run), чтобы Telegram WebApp видел локальный фронт.

### Docker-комплект для разработки
```bash
docker compose -f docker-compose.local.yml up --build
```

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
cd /srv/applications-bot/current
git pull
docker compose pull
docker compose up -d --remove-orphans
```

## 🔐 Практики безопасности

- Держите `.env` вне репозитория, файлы базы (`database/`) — с правами только для нужных сервисов.
- Закройте наружу все контейнеры, кроме nginx (используйте firewall / security groups).
- Рассмотрите fail2ban для фильтрации бот-сканеров и rate-limit в nginx.
- Регулярно пересобирайте образы, обновляйте зависимости (`pip`, `npm`, `apk`), новыми тегами.

## 📁 Полезные каталоги

- `alembic/` — миграции БД.
- `handlers/`, `services/`, `filters/` — логика бота.
- `mini-app/src/pages/Admin.tsx` — админ-панель.
- `monitoring/` — Prometheus/Grafana шаблоны.
- `docs/` — архитектурные заметки и планы.

## 📄 License

MIT
