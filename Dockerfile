# Stage 1: Build the React frontend
FROM node:20-slim AS build-frontend
WORKDIR /web
COPY web/package*.json ./
RUN npm install
COPY web/ ./
RUN npm run build

# Stage 2: FastAPI runtime
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
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m appuser
WORKDIR /app
RUN mkdir -p \
      /app/input \
      /app/output \
      /app/transcripts \
      /app/config
RUN chown -R appuser:appuser /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install vosk from repository (pip version has syntax error)
RUN git clone https://github.com/alphacep/vosk-api.git /tmp/vosk-api && \
    cd /tmp/vosk-api/python && \
    python setup.py install && \
    rm -rf /tmp/vosk-api

# Clean up build dependencies
RUN apt-get purge -y git build-essential python3-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Set model path to persistent config directory
ENV VOSK_MODEL_PATH=/app/config/model

# Copy backend code
COPY --chown=appuser:appuser *.py ./
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copy frontend build to Nginx public folder
COPY --from=build-frontend /web/dist /usr/share/nginx/html

# Environment variable for the frontend port (default 80)
ENV PORT=80

# Wrapper script to start both services
RUN echo '#!/bin/bash\n\
# Substitute PORT env into nginx config\n\
envsubst "\$PORT" < /etc/nginx/templates/default.conf.template > /etc/nginx/sites-available/default\n\
ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default\n\
\n\
# Download default Vosk model if not exists\n\
if [ ! -d "/app/config/model" ]; then\n\
    echo "Downloading Vosk model..."\n\
    curl -L https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip -o /tmp/model.zip\n\
    unzip /tmp/model.zip -d /app/config\n\
    mv /app/config/vosk-model-small-en-us-0.15 /app/config/model\n\
    rm /tmp/model.zip\n\
fi\n\
\n\
# Start FastAPI (Localhost only for isolation)\n\
python -m uvicorn api:app --host 127.0.0.1 --port 8000 >> /app/config/api.log 2>&1 &\n\
\n\
# Start Nginx\n\
nginx -g "daemon off;"\n\
' > /app/start.sh && chmod +x /app/start.sh && chown appuser:appuser /app/start.sh

# Adjust Nginx permissions to run as non-root
RUN touch /var/run/nginx.pid && \
    mkdir -p /var/cache/nginx /var/log/nginx /var/lib/nginx && \
    chown -R appuser:appuser /var/run/nginx.pid /var/cache/nginx /var/log/nginx /etc/nginx/sites-available /etc/nginx/sites-enabled /var/lib/nginx

USER appuser

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

CMD ["/app/start.sh"]
