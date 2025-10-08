# 📊 Monitoring Setup - Prometheus + Grafana

## 🚀 Quick Start

### 1. Запуск мониторинга

```bash
# Запустить все сервисы включая мониторинг
docker compose up -d

# Проверить статус
docker compose ps
```

### 2. Доступ к интерфейсам

- **Grafana**: http://localhost:3001
  - Username: `admin`
  - Password: `admin123` (или из `GRAFANA_PASSWORD` в .env)

- **Prometheus**: http://localhost:9090

- **API Metrics**: http://localhost:8000/metrics (или ваш API URL)

### 3. Первый вход в Grafana

1. Откройте http://localhost:3001
2. Войдите с учетными данными (admin/admin123)
3. Дашборд "KSU Bot API Monitoring" будет доступен автоматически

## 📈 Доступные метрики

### Автоматические метрики (FastAPI)
- `http_requests_total` - Общее количество HTTP запросов
- `http_request_duration_seconds` - Длительность запросов
- `http_requests_in_progress` - Запросы в процессе обработки

### Бизнес-метрики
- `packages_created_total` - Созданные пакеты уроков
- `lessons_created_total` - Созданные уроки
- `lessons_updated_total` - Обновленные уроки
- `reminders_sent_total` - Отправленные напоминания
- `active_packages` - Активные пакеты (gauge)
- `scheduled_lessons` - Запланированные уроки (gauge)
- `total_learners` - Всего учеников (gauge)

### Производительность
- `db_query_duration_seconds` - Время выполнения DB запросов
- `reminder_processing_duration_seconds` - Время обработки напоминаний

## 🔧 Использование custom метрик в коде

```python
from api.prometheus_metrics import (
    packages_created_total,
    lessons_created_total,
    active_packages_gauge,
    db_query_duration
)

# Пример: increment counter
packages_created_total.labels(learner_id=123).inc()

# Пример: set gauge
active_packages_gauge.set(42)

# Пример: measure duration
with db_query_duration.labels(operation="list_packages").time():
    # ваш код
    packages = await get_packages()
```

## 📊 Создание своих дашбордов

1. В Grafana перейдите в "Dashboards" → "New Dashboard"
2. Добавьте панель
3. Выберите Prometheus как источник данных
4. Используйте PromQL для запросов:

```promql
# Примеры запросов:

# Request rate по endpoints
rate(http_requests_total[5m])

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Активные пакеты за последний день
active_packages

# Созданные уроки за 24 часа
increase(lessons_created_total[24h])
```

## 🔔 Настройка алертов (опционально)

### В Grafana:

1. Откройте панель на дашборде
2. Нажмите "Alert" → "Create alert rule"
3. Настройте условия (например: error rate > 1%)
4. Добавьте notification channel (email, Telegram, webhook)

### Пример alert rule:

```yaml
# В prometheus.yml можно добавить:
rule_files:
  - 'alerts.yml'

# Создайте alerts.yml:
groups:
  - name: api_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate"
          description: "Error rate is {{ $value }} req/s"
```

## 🗄️ Хранение данных

- **Prometheus**: хранит данные 30 дней (настраивается в docker-compose.yml)
- **Grafana**: дашборды и настройки сохраняются в volume `grafana_data`

### Backup

```bash
# Backup Grafana
docker compose exec grafana grafana-cli admin export > grafana-backup.json

# Backup Prometheus (volume)
docker run --rm -v applications_bot_prometheus_data:/data -v $(pwd):/backup alpine tar czf /backup/prometheus-backup.tar.gz /data
```

## 🐛 Troubleshooting

### Prometheus не видит метрики API

1. Проверьте что API доступен: `curl http://localhost:8000/metrics`
2. Проверьте targets в Prometheus: http://localhost:9090/targets
3. Убедитесь что контейнеры в одной сети: `docker network inspect applications_bot_app-network`

### Grafana не показывает данные

1. Проверьте datasource: Configuration → Data Sources → Prometheus
2. Проверьте что URL: `http://prometheus:9090`
3. Нажмите "Test" для проверки подключения

### Нет custom метрик

Убедитесь что вы:
1. Импортировали метрики: `from api.prometheus_metrics import ...`
2. Используете их в коде (inc, set, time, etc.)
3. Перезапустили API: `docker compose restart api`

## 📚 Полезные ссылки

- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Tutorials](https://grafana.com/tutorials/)
- [FastAPI Instrumentator Docs](https://github.com/trallnag/prometheus-fastapi-instrumentator)

## 🎨 Готовые дашборды Grafana

Можно импортировать готовые дашборды из Grafana.com:

1. FastAPI: https://grafana.com/grafana/dashboards/16110
2. Prometheus Stats: https://grafana.com/grafana/dashboards/3662
3. Node Exporter (если добавите): https://grafana.com/grafana/dashboards/1860

Import: Dashboards → Import → введите ID
