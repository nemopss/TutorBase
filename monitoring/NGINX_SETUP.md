# 🌐 Nginx Setup для доступа к мониторингу

## ✅ Готово!

Конфигурация Nginx обновлена для доступа к мониторингу через ваш домен.

## 📍 Доступ к дашбордам:

После деплоя будут доступны:

- **Grafana**: https://api.xpyrkova23.ru/grafana/
- **Prometheus**: https://api.xpyrkova23.ru/prometheus/
- **API Metrics**: https://api.xpyrkova23.ru/metrics
- **Health Check**: https://api.xpyrkova23.ru/health

## 🚀 Деплой на сервер:

```bash
# 1. Закоммитьте изменения
git add nginx/nginx.conf docker-compose.yml
git commit -m "Add Nginx proxy for Grafana and Prometheus"
git push origin main

# 2. На сервере
ssh your-server
cd /path/to/applications_bot

# 3. Обновите код
git pull origin main

# 4. Перезапустите Nginx и Grafana
docker compose up -d nginx grafana

# 5. Проверьте
docker compose ps
docker compose logs nginx grafana
```

## 🔒 Защита Prometheus паролем (рекомендуется)

Prometheus лучше закрыть паролем, чтобы не было публичного доступа.

### 1. Создайте htpasswd файл:

```bash
# На сервере или локально
# Установите apache2-utils если нет
# Ubuntu/Debian:
sudo apt-get install apache2-utils

# macOS (уже установлено)
# Windows: используйте онлайн генератор htpasswd

# Создайте пользователя
htpasswd -c .htpasswd monitoring
# Введите пароль дважды

# Скопируйте файл на сервер в директорию nginx
# Например: /path/to/applications_bot/nginx/.htpasswd
```

### 2. Раскомментируйте в nginx.conf:

В `nginx/nginx.conf` в location `/prometheus/`:

```nginx
location /prometheus/ {
    # Раскомментируйте эти строки:
    auth_basic "Restricted Access";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    # ... остальное
}
```

### 3. Обновите docker-compose.yml:

Добавьте volume для htpasswd:

```yaml
nginx:
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    - ./nginx/.htpasswd:/etc/nginx/.htpasswd:ro  # добавьте эту строку
    - ./certbot/www:/var/www/certbot:ro
    - ./certbot/conf:/etc/letsencrypt:ro
```

### 4. Перезапустите:

```bash
docker compose restart nginx
```

Теперь Prometheus будет запрашивать логин/пароль!

## 🔐 Альтернатива: IP whitelist

Если хотите открыть доступ только с определенных IP:

```nginx
location /prometheus/ {
    # Разрешить только с этих IP
    allow 192.168.1.0/24;  # ваша локальная сеть
    allow 1.2.3.4;         # ваш IP
    deny all;
    
    proxy_pass http://prometheus:9090/;
    # ...
}
```

## ✅ Проверка после деплоя:

```bash
# Проверьте что Nginx видит Grafana и Prometheus
docker compose exec nginx nginx -t

# Проверьте доступность
curl -I https://api.xpyrkova23.ru/grafana/
curl -I https://api.xpyrkova23.ru/prometheus/

# Откройте в браузере
open https://api.xpyrkova23.ru/grafana/
```

## 🎯 Grafana первый вход:

1. Откройте: https://api.xpyrkova23.ru/grafana/
2. Логин: `admin`
3. Пароль: (из вашего .env, переменная GRAFANA_PASSWORD)
4. Смените пароль при первом входе (опционально)
5. Дашборд "KSU Bot API Monitoring" уже настроен!

## 🐛 Troubleshooting

### Ошибка 502 Bad Gateway:

```bash
# Проверьте что Grafana запущена
docker compose ps grafana

# Проверьте логи
docker compose logs grafana

# Перезапустите
docker compose restart grafana nginx
```

### Ошибка "Origin not allowed":

Обновите конфигурацию Grafana в `docker-compose.yml`:

```yaml
environment:
  - GF_SERVER_ROOT_URL=https://api.xpyrkova23.ru/grafana
```

### Prometheus не открывается:

```bash
# Проверьте запущен ли
docker compose ps prometheus

# Проверьте доступ изнутри nginx
docker compose exec nginx curl http://prometheus:9090/
```

## 📱 Мобильный доступ

Grafana отлично работает на мобильных! Просто откройте:
- https://api.xpyrkova23.ru/grafana/

Можно добавить в закладки на домашний экран для быстрого доступа.

## 🔄 Обновление конфигурации

При любых изменениях в nginx.conf:

```bash
# На сервере
cd /path/to/applications_bot
git pull
docker compose exec nginx nginx -t  # тест конфигурации
docker compose restart nginx        # перезапуск
```

---

🎉 **Готово! Теперь у вас есть красивые дашборды по адресу:**

**https://api.xpyrkova23.ru/grafana/**
