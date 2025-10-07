# 🚀 Quick Start Guide

## Локальная разработка

### 1. Backend (FastAPI) + Bot

```bash
# Установить зависимости
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Настроить .env
cp .env.example .env
nano .env  # Заполнить переменные

# Запустить Redis
docker compose -f docker-compose.local.yml up -d redis

# Запустить миграции
alembic upgrade head

# Запустить бота
python bot.py

# В другом терминале - запустить API
uvicorn api.main:app --reload --port 8001
```

### 2. Frontend (React)

```bash
cd mini-app

# Установить зависимости
npm install

# Запустить dev сервер
npm run dev
```

Откройте: http://localhost:5173

---

## Production деплой

### Быстрый старт на сервере:

```bash
# 1. Клонировать репозиторий
cd /srv
sudo mkdir -p applications-bot/current
sudo chown $USER:$USER applications-bot/current
cd applications-bot/current
git clone https://github.com/nemopss/ksu_applications_bot.git .

# 2. Настроить .env
cp .env.example .env
nano .env  # Заполнить продакшн значения

# 3. Создать директории
mkdir -p nginx certbot/www certbot/conf

# 4. Временный nginx для SSL
cat > nginx/nginx.conf << 'EOF'
server {
    listen 80;
    server_name api.xpyrkova23.ru app.xpyrkova23.ru;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 200 'OK';
    }
}
EOF

# 5. Запустить nginx
docker compose up -d nginx

# 6. Получить SSL сертификаты
nano scripts/init-ssl.sh  # Указать email
chmod +x scripts/init-ssl.sh
./scripts/init-ssl.sh

# 7. Восстановить правильный nginx конфиг из репо
# (файл nginx/nginx.conf уже правильный в репо)

# 8. Логин в GHCR
echo "YOUR_TOKEN" | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# 9. Запустить всё
docker compose pull
docker compose up -d

# 10. Проверить
docker compose ps
docker compose logs -f
```

### Автодеплой через GitHub

После push в `master` GitHub Actions автоматически:
1. Соберёт Docker образы
2. Запушит в GHCR
3. Задеплоит на сервер

**Требуемые GitHub Secrets:**
- `SERVER_HOST`
- `SERVER_USER`
- `SERVER_SSH_KEY`
- `GHCR_PAT`

---

## 🔗 Полезные ссылки

- 📚 **Полная инструкция:** [DEPLOYMENT.md](./DEPLOYMENT.md)
- 🌐 **Production URLs:**
  - API: https://api.xpyrkova23.ru
  - App: https://app.xpyrkova23.ru

---

## 📝 Основные команды

```bash
# Посмотреть логи
docker compose logs -f [service_name]

# Перезапустить сервис
docker compose restart [service_name]

# Обновить с GitHub
git pull && docker compose pull && docker compose up -d

# Сделать backup БД
cp database/bot.db database/bot.db.backup-$(date +%Y%m%d)
```

---

## 🛠 Структура проекта

```
.
├── api/                    # FastAPI backend
├── mini-app/              # React frontend
├── handlers/              # Telegram bot handlers
├── database/              # SQLite database
├── nginx/                 # Nginx config
├── scripts/               # Utility scripts
├── Dockerfile             # Bot image
├── Dockerfile.api         # API image
├── mini-app/Dockerfile    # App image
└── docker-compose.yml     # Production compose
```

---

Вопросы? Читайте [DEPLOYMENT.md](./DEPLOYMENT.md) для деталей! 🎉
