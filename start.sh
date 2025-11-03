#!/bin/bash
# Start script for Google Cloud Run - SIMPLIFIED

# Usar a porta fornecida pelo Cloud Run
export PORT=${PORT:-8080}

echo "🚀 Starting PROMOTORE on port $PORT"

# Iniciar gunicorn diretamente (banco será criado no primeiro acesso)
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info

