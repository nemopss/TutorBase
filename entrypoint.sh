#!/bin/sh

# Apply database migrations
echo "Applying database migrations..."
alembic upgrade head

# Start the bot
echo "Starting the bot..."
python bot.py
