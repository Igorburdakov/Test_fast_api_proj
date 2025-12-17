#!/bin/bash
# wait-for-backend.sh - ожидание готовности backend

set -e

host="$1"
port="$2"
frontend_port="$3"
shift 3

echo "Waiting for backend at $host:$port..."

until curl -f http://$host:$port/health 2>/dev/null; do
  echo "Backend is unavailable - sleeping"
  sleep 5
done

echo "Backend is up - starting Flask application"

exec python fast_api_web_server.py
