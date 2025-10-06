#!/bin/sh
set -e

# Apply database migrations
echo "Applying database migrations..."
alembic upgrade head

# Start the API server in the background
echo "Starting API server..."
uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8001 &

# Default command runs the bot
if [ $# -eq 0 ]; then
  set -- python bot.py
fi

echo "Starting command: $@"
exec "$@"
