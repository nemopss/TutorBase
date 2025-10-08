# 🚀 Quick Start: Prometheus + Grafana Monitoring

## ✅ Что уже готово:

1. **FastAPI instrumentation** - автоматический сбор метрик HTTP
2. **Custom business metrics** - пакеты, уроки, напоминания
3. **Prometheus** - хранение метрик
4. **Grafana** - визуализация
5. **Health endpoints** - `/health`, `/ready`, `/live`
6. **Auto-updating gauges** - фоновая задача обновляет метрики каждые 30 секунд

## 📦 Установка

### 1. Добавьте в `.env`:

```bash
# Monitoring
GRAFANA_PASSWORD=your_secure_password_here
```

### 2. Пересоберите Docker образы:

```bash
cd /Users/nemopss/dev/ksu/applications_bot

# Пересобрать API с новыми зависимостями
docker compose build api

# Или rebuild локально и push
docker build -t ghcr.io/nemopss/ksu-applications-bot-api:latest -f Dockerfile.api .
docker push ghcr.io/nemopss/ksu-applications-bot-api:latest
```

### 3. Запустите мониторинг:

```bash
# Запустить все сервисы
docker compose up -d

# Проверить логи
docker compose logs -f prometheus grafana api
```

### 4. Проверьте доступность:

```bash
# Health check
curl http://localhost:8000/health

# Prometheus metrics
curl http://localhost:8000/metrics

# Prometheus UI
open http://localhost:9090

# Grafana
open http://localhost:3001
```

## 🎨 Grafana Setup

1. **Откройте**: http://localhost:3001
2. **Войдите**: 
   - Username: `admin`
   - Password: `your_secure_password_here` (из .env)
3. **Дашборд**: "KSU Bot API Monitoring" уже настроен автоматически

## 📊 Доступные метрики

### HTTP метрики (автоматические):
- `http_requests_total` - всего запросов
- `http_request_duration_seconds` - время ответа
- `http_requests_in_progress` - активные запросы

### Business метрики (ваши):
- `packages_created_total{learner_id}` - созданные пакеты
- `active_packages` - активные пакеты (gauge)
- `scheduled_lessons` - запланированные уроки (gauge)
- `total_learners` - всего учеников (gauge)

### Будущие (добавьте по мере надобности):
- `lessons_created_total{status}` 
- `lessons_updated_total{old_status,new_status}`
- `reminders_sent_total{status}`
- `db_query_duration_seconds{operation}`

## 🔍 Примеры PromQL запросов

```promql
# Request rate по эндпоинтам
rate(http_requests_total[5m])

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate (5xx)
rate(http_requests_total{status=~"5.."}[5m])

# Созданные пакеты за 24 часа
increase(packages_created_total[24h])

# Текущие активные пакеты
active_packages

# Рост количества учеников
rate(total_learners[1h])
```

## 🔔 Настройка алертов (опционально)

### В Grafana:

1. Откройте панель на дашборде
2. Перейдите в "Alert" → "Create alert rule"
3. Пример условия: `rate(http_requests_total{status=~"5.."}[5m]) > 0.05`
4. Добавьте notification channel

### Telegram алерты:

1. В Grafana: Configuration → Notification channels
2. Type: Telegram
3. BOT API Token: ваш бот токен
4. Chat ID: ваш chat ID
5. Test для проверки

## 🐛 Troubleshooting

### Проблема: Prometheus не видит API

```bash
# Проверьте что API отвечает
curl http://api:8000/metrics

# Проверьте targets в Prometheus
open http://localhost:9090/targets

# Проверьте сеть
docker network inspect applications_bot_app-network
```

### Проблема: Grafana не показывает данные

```bash
# Проверьте datasource
# Grafana → Configuration → Data Sources → Prometheus
# URL должен быть: http://prometheus:9090

# Проверьте что Prometheus собирает данные
# Prometheus → Graph → введите метрику: http_requests_total
```

### Проблема: Нет custom метрик

```bash
# Проверьте логи API
docker compose logs api | grep -i metric

# Проверьте что код импортирует метрики
# В services/package_service.py должен быть:
# from api.prometheus_metrics import packages_created_total

# Перезапустите API
docker compose restart api
```

## 📈 Добавление новых метрик

### 1. Определите метрику в `api/prometheus_metrics.py`:

```python
from prometheus_client import Counter

my_new_metric = Counter(
    'my_metric_total',
    'Description of my metric',
    ['label1', 'label2']
)
```

### 2. Используйте в коде:

```python
from api.prometheus_metrics import my_new_metric

# В вашей функции
my_new_metric.labels(label1='value1', label2='value2').inc()
```

### 3. Проверьте в Prometheus:

```bash
# Подождите 10-15 секунд
# Откройте http://localhost:9090
# Введите: my_metric_total
```

### 4. Добавьте на дашборд в Grafana

## 🎯 Best Practices

1. **Counter** для событий (созданные, отправленные, ошибки)
2. **Gauge** для текущего состояния (активные, запланированные)
3. **Histogram** для измерения времени (latency, duration)
4. **Labels** с осторожностью - не создавайте слишком много комбинаций

## 🔒 Production рекомендации

1. **Закройте порты**:
```yaml
# docker-compose.yml
prometheus:
  ports:
    - "127.0.0.1:9090:9090"  # только localhost

grafana:
  ports:
    - "127.0.0.1:3001:3000"  # только localhost
```

2. **Добавьте Nginx proxy** с аутентификацией
3. **Настройте backup** для Grafana dashboards
4. **Включите HTTPS** для Grafana
5. **Настройте retention** в Prometheus (по умолчанию 30 дней)

## 📚 Полная документация

См. `monitoring/README.md` для подробностей по:
- Созданию дашбордов
- Настройке алертов
- Интеграции с другими системами
- Troubleshooting

## ✅ Checklist после установки

- [ ] API отвечает на `/health`
- [ ] Prometheus собирает метрики (проверить /targets)
- [ ] Grafana показывает данные
- [ ] Дашборд "KSU Bot API Monitoring" работает
- [ ] Gauge метрики обновляются (active_packages, etc.)
- [ ] Настроен пароль для Grafana
- [ ] (Опционально) Настроены алерты

---

🎉 **Готово! Ваш мониторинг работает!**

Prometheus UI: http://localhost:9090
Grafana: http://localhost:3001 (admin / ваш пароль)
