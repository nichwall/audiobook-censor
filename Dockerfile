# Stage 1: Build the React frontend
FROM node:20-slim AS build-frontend
WORKDIR /web
COPY web/package*.json ./
RUN npm install
COPY web/ ./
RUN npm run build

# Stage 2: Final image with Python, Nginx, and FFmpeg
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

WORKDIR /app

# Create a non-root user
RUN useradd -m -s /bin/bash appuser && \
    mkdir -p /app/input /app/output /app/transcripts /app/config && \
    chown -R appuser:appuser /app

# Install Python dependencies (except vosk)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install vosk from repository and then clean up build deps
RUN git clone https://github.com/alphacep/vosk-api.git /tmp/vosk-api && \
    cd /tmp/vosk-api/python && \
    python setup.py install && \
    rm -rf /tmp/vosk-api && \
    apt-get purge -y git build-essential python3-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Copy backend code
COPY --chown=appuser:appuser *.py ./
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copy built frontend from Stage 1
COPY --from=build-frontend /web/dist /usr/share/nginx/html

# Environment variable for the frontend port (default 80)
ENV PORT=80

# Wrapper script to start both services
RUN echo '#!/bin/bash\n\
# Substitute PORT env into nginx config\n\
envsubst "\$PORT" < /etc/nginx/templates/default.conf.template > /etc/nginx/sites-available/default\n\
ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default\n\
\n\
# Start FastAPI (Localhost only for isolation)\n\
python -m uvicorn api:app --host 127.0.0.1 --port 8000 >> /app/config/api.log 2>&1 &\n\
\n\
# Start Nginx\n\
nginx -g "daemon off;"\n\
' > /app/start.sh && chmod +x /app/start.sh && chown appuser:appuser /app/start.sh

# Adjust Nginx permissions to run as non-root
RUN touch /var/run/nginx.pid && \
    chown -R appuser:appuser /var/run/nginx.pid /var/cache/nginx /var/log/nginx /etc/nginx/sites-available /etc/nginx/sites-enabled /var/lib/nginx

USER appuser

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

CMD ["/app/start.sh"]
