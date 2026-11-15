#!/usr/bin/env bash
set -e

echo "=== Asama.ai Container Initialization ==="

# Wait for PostgreSQL
echo "Waiting for PostgreSQL database to be ready..."
python -c "
import sys, time
from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
max_tries = 30
for i in range(max_tries):
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
            print('PostgreSQL is ready!')
            sys.exit(0)
    except Exception as e:
        print(f'Waiting for PostgreSQL ({i+1}/{max_tries})...')
        time.sleep(1)
print('ERROR: PostgreSQL connection timed out.')
sys.exit(1)
"

# Wait for Redis
echo "Waiting for Redis to be ready..."
python -c "
import sys, time
import redis
from app.config import settings

r = redis.from_url(settings.REDIS_URL)
max_tries = 30
for i in range(max_tries):
    try:
        if r.ping():
            print('Redis is ready!')
            sys.exit(0)
    except Exception as e:
        print(f'Waiting for Redis ({i+1}/{max_tries})...')
        time.sleep(1)
print('ERROR: Redis connection timed out.')
sys.exit(1)
"

# Run migrations if enabled
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "Running Alembic migrations..."
    alembic upgrade head
    echo "Migrations applied successfully."
fi

echo "Executing command: $@"
exec "$@"
