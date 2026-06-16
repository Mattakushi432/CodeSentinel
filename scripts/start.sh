#!/bin/sh
set -e

# Auto-generate SECRET_KEY if not provided — sessions reset on restart without a persistent key.
if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "change-me-in-production" ]; then
    SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    export SECRET_KEY
    echo "WARNING: SECRET_KEY not set. Generated a temporary key."
    echo "Add to your .env to persist sessions:  SECRET_KEY=$SECRET_KEY"
fi

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
