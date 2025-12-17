FROM python:3.11-slim AS base

# Устанавливаем общие зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем общие файлы
COPY requirements-app.txt .
COPY requirements-web.txt .

# Устанавливаем все зависимости
RUN pip install --no-cache-dir \
    -r requirements-app.txt \
    -r requirements-web.txt

# Копируем исходные коды
COPY fast_api_app_server.py .
COPY fast_api_web_server.py .
COPY wait-for-db.sh .
COPY wait-for-backend.sh .
RUN chmod +x wait-for-db.sh wait-for-backend.sh

# Создаем точки входа
RUN echo '#!/bin/bash\n\
if [ "$SERVICE_TYPE" = "backend" ]; then\n\
    exec /app/wait-for-db.sh db 5432 postgres ${DB_PASSWORD} postgres\n\
elif [ "$SERVICE_TYPE" = "frontend" ]; then\n\
    exec /app/wait-for-backend.sh backend 5001 5000\n\
else\n\
    echo "Please set SERVICE_TYPE to backend or frontend"\n\
    exit 1\n\
fi' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]