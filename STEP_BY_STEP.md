# 🚀 Пошаговая инструкция деплоя

## 📋 ЧТО У ВАС ЕСТЬ СЕЙЧАС:
- ✅ Домены: `api.xpyrkova23.ru` и `app.xpyrkova23.ru`
- ✅ Сервер с IP адресом
- ✅ Бот уже работает на сервере через Docker

---

## ЭТАП 1: ЛОКАЛЬНО (на вашем компьютере)

### Шаг 1.1: Закоммитить новые файлы

```bash
cd /Users/nemopss/dev/ksu/applications_bot

# Проверить что изменилось
git status

# Добавить все новые файлы
git add .

# Закоммитить
git commit -m "Add production deployment configuration for API and Web App

- Add Dockerfile.api for FastAPI backend
- Add mini-app/Dockerfile for React frontend
- Add nginx configuration with SSL support
- Update docker-compose.yml with api, app, nginx, certbot
- Update GitHub Actions to build 3 Docker images
- Add deployment documentation"

# Пока НЕ пушить в master! Сначала настроим сервер
```

---

## ЭТАП 2: НАСТРОЙКА DNS (если ещё не сделано)

### Шаг 2.1: Проверить DNS записи

Убедитесь что в вашем DNS провайдере (например, reg.ru, timeweb и т.д.) настроены A-записи:

```
Тип    Имя                      Значение
A      api.xpyrkova23.ru       ВАШ_IP_СЕРВЕРА
A      app.xpyrkova23.ru       ВАШ_IP_СЕРВЕРА
```

### Шаг 2.2: Проверить что DNS работает

```bash
# На вашем компьютере
nslookup api.xpyrkova23.ru
nslookup app.xpyrkova23.ru

# Должны показывать IP вашего сервера
```

**⚠️ ВАЖНО:** DNS может занять до 24 часов, но обычно обновляется за 5-15 минут.

---

## ЭТАП 3: НА СЕРВЕРЕ - Первоначальная настройка

### Шаг 3.1: Подключиться к серверу

```bash
ssh ваш_пользователь@IP_СЕРВЕРА
```

### Шаг 3.2: Перейти в директорию с ботом

```bash
cd /srv/applications-bot/current
```

### Шаг 3.3: Сделать backup текущей конфигурации

```bash
# Создать папку для бэкапа
mkdir -p ~/backup-$(date +%Y%m%d)

# Скопировать важные файлы
cp .env ~/backup-$(date +%Y%m%d)/
cp docker-compose.yml ~/backup-$(date +%Y%m%d)/
cp -r database ~/backup-$(date +%Y%m%d)/

echo "Backup создан в ~/backup-$(date +%Y%m%d)/"
```

### Шаг 3.4: Остановить текущий бот (временно)

```bash
docker compose down
```

### Шаг 3.5: Обновить код из GitHub

```bash
# Сначала нужно запушить изменения с вашего компьютера
# Пока пропустите этот шаг, вернёмся к нему позже
```

---

## ЭТАП 4: НА СЕРВЕРЕ - Настройка .env файла

### Шаг 4.1: Открыть .env файл

```bash
nano .env
```

### Шаг 4.2: Обновить переменные для продакшена

**ВАЖНО:** Измените следующие строки в вашем .env:

```env
# ===== ОСТАВЬТЕ КАК ЕСТЬ (текущие настройки бота) =====
BOT_TOKEN=ваш_текущий_токен
ADMIN_CHAT_ID=ваш_текущий_id
LOGS_CHAT_ID=ваш_текущий_id
CANCELLATION_IMAGE_FILE_ID=ваш_текущий_file_id
ADMINS=[ваши_текущие_admins]
REGULATIONS_URL=ваш_текущий_url
REMINDER_NOTIFY_USERNAME=nemopss
DB_PATH=database/bot.db
REDIS_URL=redis://redis:6379/0

# ===== ДОБАВЬТЕ ИЛИ ИЗМЕНИТЕ ЭТИ СТРОКИ =====

# JWT Secret - ОБЯЗАТЕЛЬНО ИЗМЕНИТЕ на случайную строку!
JWT_SECRET=СГЕНЕРИРУЙТЕ_СЛУЧАЙНУЮ_СТРОКУ_МИНИМУМ_32_СИМВОЛА
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRES_SECONDS=900
JWT_REFRESH_EXPIRES_SECONDS=1209600

# CORS - укажите домен вашего приложения
CORS_ORIGINS=["https://app.xpyrkova23.ru"]

# Mini App URL - укажите домен вашего приложения
MINI_APP_URL=https://app.xpyrkova23.ru
```

### Шаг 4.3: Сгенерировать JWT_SECRET

**На сервере выполните:**

```bash
# Сгенерировать случайный секретный ключ
openssl rand -hex 32

# Скопируйте вывод и вставьте в .env как JWT_SECRET
```

### Шаг 4.4: Итоговый .env должен выглядеть так:

```env
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ADMIN_CHAT_ID=352019235
LOGS_CHAT_ID=352019235
CANCELLATION_IMAGE_FILE_ID=AgACAgIAAxkBAAIC...
ADMINS=[352019235]
REGULATIONS_URL=https://your-regulations-url.com
REMINDER_NOTIFY_USERNAME=nemopss
DB_PATH=database/bot.db
REDIS_URL=redis://redis:6379/0
JWT_SECRET=a1b2c3d4e5f6789012345678901234567890abcdef1234567890
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRES_SECONDS=900
JWT_REFRESH_EXPIRES_SECONDS=1209600
CORS_ORIGINS=["https://app.xpyrkova23.ru"]
MINI_APP_URL=https://app.xpyrkova23.ru
```

**Сохраните файл:** `Ctrl+X` → `Y` → `Enter`

---

## ЭТАП 5: НА СЕРВЕРЕ - Создать необходимые директории

### Шаг 5.1: Создать директории для nginx и certbot

```bash
mkdir -p nginx
mkdir -p certbot/www
mkdir -p certbot/conf
```

---

## ЭТАП 6: НА СЕРВЕРЕ - Временная конфигурация nginx для получения SSL

### Шаг 6.1: Создать временный nginx.conf

```bash
cat > nginx/nginx.conf << 'EOF'
# Временная конфигурация для получения SSL сертификатов
server {
    listen 80;
    server_name api.xpyrkova23.ru app.xpyrkova23.ru;

    # Для certbot challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Временный ответ
    location / {
        return 200 'Server is being configured. Please wait...\n';
        add_header Content-Type text/plain;
    }
}
EOF
```

### Шаг 6.2: Проверить что файл создан

```bash
cat nginx/nginx.conf
```

---

## ЭТАП 7: ЛОКАЛЬНО - Запушить изменения в GitHub

### Шаг 7.1: На вашем компьютере

```bash
cd /Users/nemopss/dev/ksu/applications_bot

# Если ещё не закоммитили - сделайте это сейчас
git add .
git commit -m "Add production deployment configuration"

# Запушить в репозиторий (НЕ в master, а в отдельную ветку)
git checkout -b deploy-web-app
git push origin deploy-web-app
```

**⚠️ ВАЖНО:** Сначала пушим в отдельную ветку, чтобы случайно не запустить автодеплой!

---

## ЭТАП 8: НА СЕРВЕРЕ - Получить обновленный код

### Шаг 8.1: Обновить репозиторий

```bash
# Вернуться в директорию проекта
cd /srv/applications-bot/current

# Получить ветку с изменениями
git fetch origin
git checkout deploy-web-app

# Или если хотите сразу в master:
# git pull origin master
```

---

## ЭТАП 9: НА СЕРВЕРЕ - Запустить nginx для получения SSL

### Шаг 9.1: Запустить только nginx

```bash
docker compose up -d nginx
```

### Шаг 9.2: Проверить что nginx работает

```bash
docker compose ps
docker compose logs nginx

# Проверить через браузер
curl http://api.xpyrkova23.ru
curl http://app.xpyrkova23.ru
```

Должны увидеть: `Server is being configured. Please wait...`

---

## ЭТАП 10: НА СЕРВЕРЕ - Получить SSL сертификаты

### Шаг 10.1: Отредактировать скрипт получения SSL

```bash
nano scripts/init-ssl.sh
```

**Измените строку с EMAIL:**

```bash
EMAIL="ваш_реальный_email@example.com"  # ← ИЗМЕНИТЕ ЭТО!
```

**Сохраните:** `Ctrl+X` → `Y` → `Enter`

### Шаг 10.2: Сделать скрипт исполняемым

```bash
chmod +x scripts/init-ssl.sh
```

### Шаг 10.3: Запустить получение сертификатов

```bash
./scripts/init-ssl.sh
```

**Что будет происходить:**
- Скрипт запросит сертификаты для `api.xpyrkova23.ru`
- Затем для `app.xpyrkova23.ru`
- Let's Encrypt проверит что вы владелец доменов
- Сертификаты будут сохранены в `certbot/conf/`

**Если возникнет ошибка:**
- Проверьте что DNS работает: `nslookup api.xpyrkova23.ru`
- Проверьте что порт 80 открыт: `curl http://api.xpyrkova23.ru`

---

## ЭТАП 11: НА СЕРВЕРЕ - Заменить nginx конфигурацию на продакшн

### Шаг 11.1: Скопировать продакшн конфиг

```bash
# Продакшн конфиг уже есть в репозитории в папке nginx/
# Но его создал скрипт выше, поэтому нужно его заменить

# Удалить временный конфиг
rm nginx/nginx.conf

# Скопировать правильный из репозитория (он был в коммите)
git checkout nginx/nginx.conf
```

Если файл не появился в git, создайте его вручную:

```bash
nano nginx/nginx.conf
```

И вставьте содержимое из файла который я создал (см. в VSCode открытый файл `nginx/nginx.conf`).

---

## ЭТАП 12: НА СЕРВЕРЕ - Залогиниться в GitHub Container Registry

### Шаг 12.1: Создать Personal Access Token в GitHub

1. Откройте GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Нажмите "Generate new token (classic)"
3. Название: `GHCR Access for Server`
4. Отметьте: `write:packages`, `read:packages`, `delete:packages`
5. Generate token
6. **СКОПИРУЙТЕ токен** (он больше не покажется!)

### Шаг 12.2: Залогиниться на сервере

```bash
# На сервере выполните:
echo "ВАШ_ТОКЕН" | docker login ghcr.io -u nemopss --password-stdin
```

**Должны увидеть:** `Login Succeeded`

---

## ЭТАП 13: ЛОКАЛЬНО - Запустить GitHub Actions для сборки образов

### Шаг 13.1: Добавить GitHub Secrets (если ещё не добавлены)

В GitHub репозитории:
1. Settings → Secrets and variables → Actions
2. Добавьте секреты:
   - `SERVER_HOST` = IP вашего сервера
   - `SERVER_USER` = пользователь SSH (обычно `root` или ваше имя)
   - `SERVER_SSH_KEY` = приватный SSH ключ для подключения к серверу
   - `GHCR_PAT` = Personal Access Token который создали выше

### Шаг 13.2: Замержить ветку в master

```bash
# На вашем компьютере
cd /Users/nemopss/dev/ksu/applications_bot

git checkout master
git merge deploy-web-app
git push origin master
```

**Что произойдёт:**
- GitHub Actions автоматически запустится
- Соберёт 3 Docker образа (bot, api, app)
- Запушит их в GitHub Container Registry
- Задеплоит на сервер через SSH

### Шаг 13.3: Следить за процессом

Откройте в браузере:
```
https://github.com/nemopss/ksu_applications_bot/actions
```

Следите за прогрессом сборки и деплоя.

---

## ЭТАП 14: НА СЕРВЕРЕ - Запустить все сервисы

### Шаг 14.1: Остановить nginx (если работает)

```bash
docker compose down nginx
```

### Шаг 14.2: Запустить все сервисы

```bash
docker compose pull
docker compose up -d
```

### Шаг 14.3: Проверить статус

```bash
docker compose ps
```

**Должны увидеть:**
```
NAME                            STATUS
applications_bot                Up
api                            Up
app                            Up
nginx                          Up
redis                          Up
certbot                        Up
```

### Шаг 14.4: Посмотреть логи

```bash
# Все логи
docker compose logs -f

# Или отдельные сервисы
docker compose logs -f api
docker compose logs -f app
docker compose logs -f nginx
```

---

## ЭТАП 15: ПРОВЕРКА - Убедиться что всё работает

### Шаг 15.1: Проверить API

Откройте в браузере:
```
https://api.xpyrkova23.ru/docs
```

Должна открыться документация FastAPI (Swagger UI).

### Шаг 15.2: Проверить Web App

Откройте в браузере:
```
https://app.xpyrkova23.ru
```

Должно открыться React приложение.

### Шаг 15.3: Проверить SSL

```bash
# На вашем компьютере или сервере
curl -I https://api.xpyrkova23.ru
curl -I https://app.xpyrkova23.ru
```

Должны увидеть заголовки с `HTTP/2 200` и сертификаты от Let's Encrypt.

---

## ЭТАП 16: ОБНОВЛЕНИЕ MINI_APP_URL В БОТЕ

### Шаг 16.1: Обновить кнопку в боте

В файле `keyboards/common.py` кнопка уже использует `config.MINI_APP_URL`, так что:

1. Убедитесь что в `.env` на сервере установлен `MINI_APP_URL=https://app.xpyrkova23.ru`
2. Перезапустите бота: `docker compose restart applications_bot`
3. Проверьте в Telegram что кнопка "🌐 Open Web App" открывает правильный URL

---

## 🎉 ГОТОВО!

Теперь у вас работает:
- **Telegram Bot** - получает команды, отправляет уведомления
- **FastAPI Backend** - `https://api.xpyrkova23.ru` - обрабатывает запросы
- **React Web App** - `https://app.xpyrkova23.ru` - красивый интерфейс
- **Nginx** - раздаёт приложения через HTTPS с SSL
- **Auto-deploy** - при каждом push в master всё автоматически обновляется

---

## 📝 Полезные команды после деплоя

```bash
# Посмотреть логи
docker compose logs -f [service]

# Перезапустить сервис
docker compose restart [service]

# Обновить с GitHub (вручную)
cd /srv/applications-bot/current
git pull
docker compose pull
docker compose up -d

# Backup базы данных
cp database/bot.db database/bot.db.backup-$(date +%Y%m%d-%H%M)

# Мониторинг ресурсов
docker stats

# Очистить старые образы
docker system prune -a
```

---

## 🆘 Если что-то пошло не так

### SSL не работает

```bash
# Проверить логи certbot
docker compose logs certbot

# Попробовать получить сертификаты вручную
docker compose run --rm certbot certonly --webroot --webroot-path=/var/www/certbot -d api.xpyrkova23.ru

# Перезапустить nginx
docker compose restart nginx
```

### API не отвечает

```bash
# Проверить логи API
docker compose logs api

# Проверить переменные окружения
docker compose exec api env | grep -E "JWT|CORS|MINI_APP"

# Перезапустить API
docker compose restart api
```

### Web App показывает ошибку

```bash
# Проверить логи app
docker compose logs app

# Проверить nginx
docker compose logs nginx

# Открыть браузер DevTools (F12) и посмотреть Console
```

### Вернуться к старой конфигурации

```bash
# Восстановить из бэкапа
cd /srv/applications-bot/current
docker compose down
cp ~/backup-ДАТА/.env .env
cp ~/backup-ДАТА/docker-compose.yml docker-compose.yml
docker compose up -d
```

---

## 📞 Контакты для помощи

Если возникли проблемы - я помогу! Просто опишите:
1. На каком этапе застряли
2. Какую ошибку видите
3. Что показывают логи

Удачи! 🚀
