#!/bin/bash
# wait-for-db.sh - ожидание готовности PostgreSQL

set -e

host="$1"
port="$2"
user="$3"
password="$4"
database="$5"
shift 5

echo "Waiting for PostgreSQL at $host:$port..."

until PGPASSWORD=$password psql -h "$host" -p "$port" -U "$user" -d "$database" -c '\q' 2>/dev/null; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 5
done

echo "PostgreSQL is up - starting application"

exec python -m uvicorn fast_api_app_server:app --host 0.0.0.0 --port 5001