# 🚀 Deployment Guide

Этот гайд объясняет как развернуть Web App на сервере с доменами **api.xpyrkova23.ru** и **app.xpyrkova23.ru**.

## 📋 Предварительные требования

1. **Сервер** с Docker и Docker Compose
2. **Домены** настроены и указывают на IP сервера:
   - `api.xpyrkova23.ru` → IP сервера
   - `app.xpyrkova23.ru` → IP сервера
3. **Доступ по SSH** к серверу
4. **GitHub Secrets** настроены:
   - `SERVER_HOST` - IP сервера
   - `SERVER_USER` - SSH пользователь
   - `SERVER_SSH_KEY` - SSH приватный ключ
   - `GHCR_PAT` - GitHub Personal Access Token с доступом к packages

## 🔧 Первоначальная настройка сервера

### 1. Подключитесь к серверу

```bash
ssh your-user@your-server-ip
```

### 2. Установите Docker и Docker Compose (если не установлены)

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### 3. Создайте директорию для приложения

```bash
sudo mkdir -p /srv/applications-bot/current
sudo chown $USER:$USER /srv/applications-bot/current
cd /srv/applications-bot/current
```

### 4. Клонируйте репозиторий

```bash
git clone https://github.com/nemopss/ksu_applications_bot.git .
```

### 5. Создайте `.env` файл

```bash
cp .env.example .env
nano .env
```

Заполните все необходимые переменные окружения:

```env
BOT_TOKEN=your-bot-token
DB_PATH=database/bot.db
ADMIN_CHAT_ID=your-admin-chat-id
LOGS_CHAT_ID=your-logs-chat-id
CANCELLATION_IMAGE_FILE_ID=your-file-id
ADMINS=[your-admin-ids]
REGULATIONS_URL=your-regulations-url
REDIS_URL=redis://redis:6379/0
JWT_SECRET=your-super-secret-jwt-key-change-this
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRES_SECONDS=900
JWT_REFRESH_EXPIRES_SECONDS=1209600
CORS_ORIGINS=["https://app.xpyrkova23.ru"]
MINI_APP_URL=https://app.xpyrkova23.ru
```

### 6. Создайте директории для nginx и certbot

```bash
mkdir -p nginx certbot/www certbot/conf
```

### 7. Временная nginx конфигурация (для получения SSL)

Создайте временный nginx конфиг без SSL:

```bash
cat > nginx/nginx.conf << 'EOF'
server {
    listen 80;
    server_name api.xpyrkova23.ru app.xpyrkova23.ru;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'OK';
        add_header Content-Type text/plain;
    }
}
EOF
```

### 8. Запустите nginx для получения сертификатов

```bash
docker compose up -d nginx
```

### 9. Получите SSL сертификаты

Отредактируйте email в скрипте:

```bash
nano scripts/init-ssl.sh
# Измените EMAIL="your-email@example.com" на ваш email
```

Запустите скрипт:

```bash
chmod +x scripts/init-ssl.sh
./scripts/init-ssl.sh
```

### 10. Замените nginx конфигурацию на продакшн

```bash
# Скопируйте из репозитория уже готовый nginx.conf
# Он уже создан и находится в nginx/nginx.conf
```

### 11. Логин в GitHub Container Registry

```bash
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

### 12. Запустите все сервисы

```bash
docker compose pull
docker compose up -d
```

### 13. Проверьте статус

```bash
docker compose ps
docker compose logs -f
```

## 🔄 Автоматический деплой через GitHub Actions

После первоначальной настройки, каждый push в `master` будет:

1. ✅ Собирать Docker образы для Bot, API и App
2. ✅ Пушить их в GitHub Container Registry
3. ✅ Деплоить на сервер через SSH
4. ✅ Обновлять и перезапускать контейнеры

## 🛠 Полезные команды

### Посмотреть логи

```bash
# Все сервисы
docker compose logs -f

# Конкретный сервис
docker compose logs -f api
docker compose logs -f app
docker compose logs -f nginx
docker compose logs -f applications_bot
```

### Перезапустить сервис

```bash
docker compose restart api
docker compose restart app
docker compose restart nginx
```

### Обновить с GitHub

```bash
cd /srv/applications-bot/current
git pull
docker compose pull
docker compose up -d
```

### Остановить все

```bash
docker compose down
```

### Посмотреть использование ресурсов

```bash
docker stats
```

## 🔒 Безопасность

### Firewall (UFW)

```bash
# Установка UFW
sudo apt install ufw

# Разрешить SSH
sudo ufw allow 22/tcp

# Разрешить HTTP и HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Включить firewall
sudo ufw enable

# Проверить статус
sudo ufw status
```

## 🌐 DNS настройки

Убедитесь что DNS записи настроены:

```
A    api.xpyrkova23.ru    →    YOUR_SERVER_IP
A    app.xpyrkova23.ru    →    YOUR_SERVER_IP
```

Проверить можно командой:

```bash
nslookup api.xpyrkova23.ru
nslookup app.xpyrkova23.ru
```

## 🎯 Тестирование

### Проверить API

```bash
curl https://api.xpyrkova23.ru/docs
```

### Проверить Web App

Откройте в браузере: https://app.xpyrkova23.ru

### Проверить SSL

```bash
curl -I https://api.xpyrkova23.ru
curl -I https://app.xpyrkova23.ru
```

## 🐛 Troubleshooting

### Проблемы с SSL

Если сертификаты не работают:

```bash
# Проверьте логи certbot
docker compose logs certbot

# Попробуйте получить сертификаты вручную
docker compose run --rm certbot certonly --webroot --webroot-path=/var/www/certbot -d api.xpyrkova23.ru

# Перезапустите nginx
docker compose restart nginx
```

### Проблемы с CORS

Убедитесь что в `.env` установлен правильный `CORS_ORIGINS`:

```env
CORS_ORIGINS=["https://app.xpyrkova23.ru"]
```

### База данных

База данных хранится в `./database/bot.db` и монтируется в контейнеры.

Сделать бэкап:

```bash
cp database/bot.db database/bot.db.backup-$(date +%Y%m%d-%H%M%S)
```

## 📊 Мониторинг

### Health checks

```bash
# API health
curl https://api.xpyrkova23.ru/docs

# App health
curl https://app.xpyrkova23.ru/health
```

### Logs rotation

Настройте logrotate для Docker:

```bash
sudo nano /etc/docker/daemon.json
```

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

```bash
sudo systemctl restart docker
```

## 🎉 Готово!

Ваше приложение теперь доступно по адресам:
- **API**: https://api.xpyrkova23.ru
- **Web App**: https://app.xpyrkova23.ru

При каждом push в master всё автоматически обновится! 🚀
