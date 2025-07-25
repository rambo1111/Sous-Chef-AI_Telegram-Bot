#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Start the bot in the background
echo "Starting Bot..."
python bot.py &

# Start the Gunicorn web server in the foreground
echo "Starting Gunicorn..."
gunicorn app:app