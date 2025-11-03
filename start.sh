#!/bin/bash
# Ultra-simplified start script

export PORT=${PORT:-8080}

echo "Starting PROMOTORE on port $PORT"

exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 0
