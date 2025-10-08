# 📊 Monitoring Setup - Summary of Changes

## 📦 Files Created

### Configuration Files:
- `monitoring/prometheus.yml` - Prometheus configuration
- `monitoring/grafana/provisioning/datasources/prometheus.yml` - Grafana datasource
- `monitoring/grafana/provisioning/dashboards/dashboard.yml` - Dashboard provider
- `monitoring/grafana/provisioning/dashboards/json/ksu-api-dashboard.json` - Pre-built dashboard

### API Files:
- `api/prometheus_metrics.py` - Custom business metrics definitions
- `api/routes/health.py` - Health check endpoints
- `api/metrics_updater.py` - Background task for gauge updates

### Documentation:
- `monitoring/README.md` - Detailed monitoring documentation
- `MONITORING_SETUP.md` - Quick start guide

## 🔧 Files Modified

### `docker-compose.yml`
- Added `prometheus` service on port 9090
- Added `grafana` service on port 3001
- Added volumes: `prometheus_data`, `grafana_data`

### `requirements.txt`
- Added `prometheus-fastapi-instrumentator==7.0.0`
- Added `prometheus-client==0.20.0`

### `api/app.py`
- Added Prometheus instrumentation
- Added health router
- Added lifespan manager for metrics updater

### `services/package_service.py`
- Added metrics tracking for package creation
- Imports custom metrics with fallback

## 🎯 Features Added

### 1. Automatic HTTP Metrics
- Request count per endpoint
- Response time (histogram)
- Requests in progress
- Status codes distribution

### 2. Business Metrics
- `packages_created_total` - Packages created counter
- `active_packages` - Current active packages (gauge)
- `scheduled_lessons` - Current scheduled lessons (gauge)
- `total_learners` - Total learners count (gauge)

### 3. Health Checks
- `/health` - Full system health check
- `/ready` - Readiness probe
- `/live` - Liveness probe
- `/metrics` - Prometheus metrics endpoint

### 4. Auto-updating Gauges
Background task updates gauge metrics every 30 seconds:
- Counts from database
- No manual intervention needed

### 5. Pre-configured Dashboard
Grafana dashboard includes:
- HTTP request rate graph
- Request duration (p95) graph
- Active packages stat
- Scheduled lessons stat
- Total learners stat
- Packages created (24h) stat
- Lessons created by status graph
- Reminders sent graph
- HTTP error rate graph with alert

## 🚀 Deployment Steps

### 1. Update `.env` file:
```bash
echo "GRAFANA_PASSWORD=your_secure_password" >> .env
```

### 2. Rebuild and push API image:
```bash
cd /Users/nemopss/dev/ksu/applications_bot

# Build new API image
docker build -t ghcr.io/nemopss/ksu-applications-bot-api:latest -f Dockerfile.api .

# Push to registry
docker push ghcr.io/nemopss/ksu-applications-bot-api:latest
```

### 3. Deploy on server:
```bash
# SSH to server
ssh your-server

# Pull latest changes
cd /path/to/applications_bot
git pull origin main

# Pull new images
docker compose pull

# Start new services
docker compose up -d prometheus grafana

# Restart API with new code
docker compose up -d --force-recreate api

# Check everything is running
docker compose ps
```

### 4. Verify:
```bash
# Check health
curl http://localhost:8000/health

# Check metrics endpoint
curl http://localhost:8000/metrics | head -20

# Check Prometheus
curl http://localhost:9090/-/healthy

# Open Grafana
# http://your-server:3001
# Login: admin / your_secure_password
```

## 📊 Accessing Dashboards

### Local Development:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001
- API Metrics: http://localhost:8000/metrics

### Production (за Nginx):
Добавьте в `nginx/nginx.conf`:

```nginx
# Grafana
location /grafana/ {
    proxy_pass http://grafana:3000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

# Prometheus (опционально, лучше закрыть)
location /prometheus/ {
    proxy_pass http://prometheus:9090/;
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
```

## 🔒 Security Considerations

1. **Change default Grafana password** - используйте сильный пароль
2. **Close external ports** - оставьте только через Nginx
3. **Setup authentication** - Nginx basic auth для Prometheus
4. **Use HTTPS** - для production обязательно
5. **Backup dashboards** - регулярно экспортируйте настройки

## 📈 Next Steps

### Recommended additions:

1. **Add more business metrics:**
   - Lessons completion rate
   - Reminder response rate
   - Average lessons per package
   - Teacher workload

2. **Setup alerts:**
   - High error rate (>5%)
   - Slow response time (>2s)
   - Low database connection pool
   - Service down

3. **Add PostgreSQL exporter (optional):**
```yaml
postgres-exporter:
  image: prometheuscommunity/postgres-exporter
  environment:
    DATA_SOURCE_NAME: "postgresql://user:pass@db:5432/dbname"
```

4. **Add Node Exporter for system metrics:**
```yaml
node-exporter:
  image: prom/node-exporter
  volumes:
    - /proc:/host/proc:ro
    - /sys:/host/sys:ro
```

## 🐛 Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| Prometheus не запускается | Проверьте `monitoring/prometheus.yml` синтаксис |
| Grafana не подключается к Prometheus | URL должен быть `http://prometheus:9090` |
| Метрики не обновляются | Перезапустите API: `docker compose restart api` |
| Dashboard пустой | Подождите 30 сек для сбора данных |
| No data in Grafana | Проверьте Prometheus targets: http://localhost:9090/targets |

## 📝 Git Commit

```bash
git add .
git commit -m "Add Prometheus + Grafana monitoring

Features:
- Automatic HTTP metrics via prometheus-fastapi-instrumentator
- Custom business metrics (packages, lessons, learners)
- Health check endpoints (/health, /ready, /live)
- Pre-configured Grafana dashboard
- Background task for gauge updates
- Docker compose setup for Prometheus + Grafana

Changes:
- Added monitoring/ directory with configs
- Updated docker-compose.yml with prometheus & grafana
- Added prometheus_metrics.py with business metrics
- Added health.py router for health checks
- Added metrics_updater.py for background updates
- Updated requirements.txt with prometheus libs
- Instrumented package_service.py with metrics

Access:
- Grafana: http://localhost:3001 (admin/password)
- Prometheus: http://localhost:9090
- Metrics: http://localhost:8000/metrics"

git push origin main
```

## ✅ Checklist

After deployment, verify:

- [ ] Prometheus running: `docker compose ps prometheus`
- [ ] Grafana running: `docker compose ps grafana`
- [ ] API healthy: `curl http://localhost:8000/health`
- [ ] Metrics endpoint: `curl http://localhost:8000/metrics`
- [ ] Prometheus targets UP: http://localhost:9090/targets
- [ ] Grafana login works: http://localhost:3001
- [ ] Dashboard shows data: "KSU Bot API Monitoring"
- [ ] Gauges updating: watch `active_packages` metric

---

🎉 **Monitoring is ready!**

For detailed usage, see: `MONITORING_SETUP.md` and `monitoring/README.md`
