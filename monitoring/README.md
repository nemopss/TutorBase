# 📊 Monitoring Setup - Prometheus + Grafana

## 🚀 Quick Start

### 1. Запуск мониторинга

```bash
# Убедитесь, что в .env задан GRAFANA_PASSWORD

# Запустить только monitoring-профиль
docker compose --profile monitoring up -d prometheus grafana

# Проверить статус
docker compose ps prometheus grafana
```

### 2. Доступ к интерфейсам

- **Grafana**: `http://localhost:3001` на самом сервере
  - Username: `admin`
  - Password: значение `GRAFANA_PASSWORD` из `.env`

- **Prometheus**: `http://localhost:9090` на самом сервере

- **API Metrics**: `http://api:8001/metrics` внутри Docker-сети или `https://api.your-domain.example/metrics` снаружи

### 3. Первый вход в Grafana

1. Откройте `http://localhost:3001` на сервере или используйте SSH-туннель:
   ```bash
   ssh -L 3001:127.0.0.1:3001 -L 9090:127.0.0.1:9090 user@your-server
   ```
2. Войдите с учетными данными (`admin` / значение `GRAFANA_PASSWORD`)
3. Дашборд "TutorBase Operations Monitoring" будет доступен автоматически

## 📈 Доступные метрики

### Автоматические метрики (FastAPI)
- `http_requests_total` - Общее количество HTTP запросов
- `http_request_duration_seconds` - Длительность запросов
- `http_requests_in_progress` - Запросы в процессе обработки
- `process_*`, `python_*` - Runtime-метрики процесса API

### Что считать "мусорным" трафиком
- Для Prometheus безопасно считать мусор через `handler="none"` и 4xx/5xx-статусы.
- Не добавляйте raw path как label в метрики для произвольных URL: это создаёт взрыв cardinality и со временем убивает Prometheus.
- Если нужен точный список сканерских или мусорных URL, это уже задача access logs, а не Prometheus labels.

### Бизнес-метрики
- `packages_created_total` - Созданные пакеты уроков
- `active_packages` - Активные пакеты (gauge)
- `scheduled_lessons` - Запланированные уроки (gauge)
- `total_learners` - Всего учеников (gauge)

### Фоновые задачи и нотификации
- `celery_task_started_total` - Старты Celery-задач по `task_name`
- `celery_task_succeeded_total` - Успешные завершения Celery-задач
- `celery_task_failed_total` - Падения Celery-задач
- `celery_task_retried_total` - Ретраи Celery-задач
- `celery_task_duration_seconds` - Длительность Celery-задач
- `notification_jobs_claimed_total` - Захваченные notification jobs
- `notification_jobs_processed_total` - Обработанные notification jobs по результату
- `notification_deliveries_claimed_total` - Захваченные к доставке уведомления
- `notification_deliveries_processed_total` - Доставки уведомлений по результату

### Финансы и производительность
- `payments_recorded_total` - Количество зафиксированных платежей
- `payments_recorded_amount_total` - Сумма зафиксированных платежей
- `payments_voided_total` - Количество аннулированных платежей
- `payments_voided_amount_total` - Сумма аннулированных платежей
- `db_query_duration_seconds` - Время выполнения DB запросов
- `reminder_processing_duration_seconds` - Время обработки напоминаний

## 🔧 Использование custom метрик в коде

```python
from api.prometheus_metrics import (
    packages_created_total,
    celery_task_started_total,
    active_packages_gauge,
    db_query_duration
)

# Пример: increment counter
packages_created_total.inc()

# Пример: increment labeled counter
celery_task_started_total.labels(task_name="utils.tasks.metrics.sync_package_metrics").inc()

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

# Top endpoint'ы по нагрузке
topk(10, sum by (method, handler) (rate(http_requests_total{handler!~"/metrics|/health"}[5m])))

# Самые медленные endpoint'ы по p95
topk(10, histogram_quantile(0.95, sum by (le, method, handler) (rate(http_request_duration_seconds_bucket{handler!~"/metrics|/health"}[5m]))))

# Самые медленные endpoint'ы по среднему времени
topk(10, (sum by (method, handler) (rate(http_request_duration_seconds_sum{handler!~"/metrics|/health"}[5m]))) / clamp_min(sum by (method, handler) (rate(http_request_duration_seconds_count{handler!~"/metrics|/health"}[5m])), 0.001))

# Сколько было unmatched/junk запросов за час
sum(increase(http_requests_total{handler="none"}[1h]))

# Разбивка junk-запросов по статусам
sum by (status) (increase(http_requests_total{handler="none"}[1h]))

# Активные пакеты за последний день
active_packages

# Ошибки фоновых задач за 15 минут
sum by (task_name) (increase(celery_task_failed_total[15m]))

# Доставленные уведомления за 1 час
sum by (result) (increase(notification_deliveries_processed_total[1h]))

# Сумма зафиксированных платежей за 24 часа
sum by (currency) (increase(payments_recorded_amount_total[24h]))
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

- **Prometheus**: хранит данные 14 дней с ограничением размера TSDB до 2 GB
- **Grafana**: дашборды и настройки сохраняются в volume `grafana_data`

### Backup

```bash
# Backup Grafana
docker compose exec grafana grafana-cli admin export > grafana-backup.json

# Backup Prometheus (volume)
docker run --rm -v tutorbase_prometheus_data:/data -v $(pwd):/backup alpine tar czf /backup/prometheus-backup.tar.gz /data
```

## 🐛 Troubleshooting

### Prometheus не видит метрики API

1. Проверьте что API доступен: `curl http://localhost:8001/metrics`
2. Проверьте targets в Prometheus: http://localhost:9090/targets
3. Убедитесь что контейнеры в одной сети: `docker network inspect app-network`

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
