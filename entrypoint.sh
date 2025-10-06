#!/bin/sh
set -e

# Apply database migrations
echo "Applying database migrations..."
alembic upgrade head

# Default command runs the bot
if [ $# -eq 0 ]; then
  set -- python bot.py
fi

echo "Starting command: $@"
exec "$@"
