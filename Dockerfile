# Stage 1: Build the React frontend
FROM node:20-slim AS build-frontend
WORKDIR /web
COPY web/package*.json ./
RUN npm install
COPY web/ ./
RUN npm run build

# Stage 2: Final runtime image (rootless)
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    nginx \
    gettext-base \
    git \
    build-essential \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash appuser

# App directories
WORKDIR /app
RUN mkdir -p \
      /app/input \
      /app/output \
      /app/transcripts \
      /app/config \
      /var/cache/nginx \
      /var/log/nginx \
      /run/nginx

# Assign ownership
RUN chown -R appuser:appuser \
      /app \
      /var/cache/nginx \
      /var/log/nginx \
      /run/nginx

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install vosk (then clean build deps)
RUN git clone https://github.com/alphacep/vosk-api.git /tmp/vosk-api && \
    cd /tmp/vosk-api/python && \
    python setup.py install && \
    rm -rf /tmp/vosk-api && \
    apt-get purge -y git build-essential python3-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Copy backend code
COPY --chown=appuser:appuser *.py ./

# Copy frontend build
COPY --from=build-frontend /web/dist /usr/share/nginx/html

# Nginx config template (Debian-native)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Startup script
RUN printf '%s\n' \
'#!/bin/bash' \
'set -e' \
'' \
'# Render nginx config' \
'envsubst "$PORT" < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf' \
'' \
'# Start FastAPI (localhost only)' \
'python -m uvicorn api:app --host 127.0.0.1 --port 8000 >> /app/config/api.log 2>&1 &' \
'' \
'# Start nginx (non-root)' \
'nginx -g "daemon off;"' \
> /app/start.sh \
&& chmod +x /app/start.sh \
&& chown appuser:appuser /app/start.sh

# Nginx must not try to switch users
RUN sed -i '/^user\s\+/d' /etc/nginx/nginx.conf

# Switch to non-root user
USER appuser

# Non-privileged port
ENV PORT=8080
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT}/ || exit 1

CMD ["/app/start.sh"]
