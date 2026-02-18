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

# Download the Vosk small US English model into the image so we can use it at runtime.
ARG VOSK_MODEL_URL=https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
RUN curl -L "${VOSK_MODEL_URL}" -o /tmp/model.zip && \
    unzip /tmp/model.zip -d /tmp && \
    mv /tmp/vosk-model-small-en-us-0.15 /app/model && \
    rm -rf /tmp/model.zip

RUN chown -R appuser:appuser /app

# Install Python dependencies (including vosk via pip)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Patch the installed vosk transcriber so overlapping sentence accumulation works correctly.
RUN python - <<'PY'
from pathlib import Path

path = Path('/usr/local/lib/python3.11/site-packages/vosk/transcriber/transcriber.py')
text = path.read_text()
needle = 'monologue["text"] += part["text"]'
replace = 'monologues["text"] += part["text"]'

if needle not in text:
    raise SystemExit('expected pattern not found')

path.write_text(text.replace(needle, replace, 1))
PY

# Clean up build dependencies
RUN apt-get purge -y git build-essential python3-dev && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Set model path to the baked-in model
ENV VOSK_MODEL_PATH=/app/model

# Copy backend code
COPY --chown=appuser:appuser *.py ./

# Copy frontend build into the app directory
COPY --from=build-frontend /web/dist /app/frontend

# Environment variable for the frontend port (default 8000)
ENV PORT=8000

# Wrapper script to start the API server
RUN echo '#!/bin/bash\n\
set -euo pipefail\n\
\n\
# Ensure API log exists so we can tail it later\n\
mkdir -p /app/config\n\
touch /app/config/api.log\n\
\n\
# Run uvicorn and log output\n\
python -m uvicorn api:app --host 0.0.0.0 --port $PORT 2>&1 | tee /app/config/api.log\n\
' > /app/start.sh && chmod +x /app/start.sh && chown appuser:appuser /app/start.sh

USER appuser

EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

CMD ["/app/start.sh"]
