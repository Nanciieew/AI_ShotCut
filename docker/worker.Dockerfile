# ============================================================
# Celery Worker Dockerfile — OmniShotCut inference ready
# ============================================================
# Layers ordered by change frequency to maximise Docker cache:
#   1. System packages (FFmpeg, OpenCV runtime libs)
#   2. PyTorch CPU (large download, rarely changes)
#   3. Python dependencies (base + worker + model deps)
#   4. Application source (changes most often)
# ============================================================

FROM python:3.11-slim

WORKDIR /app

# ------------------------------------------------------------------
# Layer 1: System dependencies
# ------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-extra \
    # OpenCV runtime (headless: no GUI)
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Git (needed for pip install from git)
    git \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# Layer 2: PyTorch CPU (large, cached separately)
# ------------------------------------------------------------------
RUN pip install --no-cache-dir \
    torch \
    torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# ------------------------------------------------------------------
# Layer 3: Python dependencies
# ------------------------------------------------------------------
# Copy only requirements for cache
COPY requirements/base.txt      requirements/base.txt
COPY requirements/worker.txt    requirements/worker.txt
COPY requirements/models/       requirements/models/

RUN pip install --no-cache-dir -r requirements/worker.txt

# --- OmniShotCut model deps (without the package itself) ---
RUN pip install --no-cache-dir \
    numpy \
    ffmpeg-python \
    opencv-python-headless \
    huggingface_hub \
    Pillow \
    packaging

# --- OmniShotCut package (fixed commit) ---
# pyproject.toml deps installed automatically by pip
RUN pip install --no-cache-dir \
    git+https://github.com/UVA-Computer-Vision-Lab/OmniShotCut.git@23ad6fb41b296fb9258b0e7825125a914573b906

# ------------------------------------------------------------------
# Layer 4: Application source
# ------------------------------------------------------------------
COPY . .

# ------------------------------------------------------------------
# Runtime
# ------------------------------------------------------------------
ENV STORAGE_ROOT=/data
ENV MODEL_STORE_ROOT=/models

CMD ["celery", "-A", "workers.celery_app", "worker", \
     "--loglevel=info", "--concurrency=1", \
     "-Q", "video,shot,subtitle,feature,scene,final,maintenance"]
