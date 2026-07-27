# ============================================================
# Celery Worker Dockerfile
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# System dependencies for FFmpeg and audio/video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-extra \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
