# KSU Applications Bot

## Quick Start

### Requirements
- Python 3.11+
- Poetry or pip
- Docker / Docker Compose (optional)

### Configuration
1. Copy `.env.example` to `.env` and fill in the values:
   ```bash
   cp .env.example .env
   ```
Required keys:
- `BOT_TOKEN` — Telegram bot token
- `ADMINS` — JSON list of admin chat IDs
- `JWT_SECRET` — secret for API tokens
- `REDIS_URL` — e.g. `redis://localhost:6379/0` for bare-metal run; docker-compose overrides to `redis://redis:6379/0`

### Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

For API + bot via Docker:
```bash
docker compose -f docker-compose.local.yml up --build
```

### Tests
```bash
pytest
```

## API
FastAPI app available at `/api/v1`. Key endpoints:
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/packages`, `POST /api/v1/packages/create`
- `GET /api/v1/lessons`, `GET /api/v1/lessons/packages/{package_id}`, `POST /api/v1/lessons/packages/{package_id}`
- `GET /api/v1/templates`, `POST /api/v1/templates/create`
- `GET /api/v1/reminders`, `GET /api/v1/reminders/packages/{package_id}`
- `GET /api/v1/metrics/summary`

## License
MIT
