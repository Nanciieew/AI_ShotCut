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

# Global pip settings to reduce disk usage
ENV PIP_NO_CACHE_DIR=1

# ------------------------------------------------------------------
# Layer 1: System dependencies
# ------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-extra \
    # OpenCV runtime (headless: no GUI)
    # libgl1-mesa-glx removed in Debian Trixie → replaced by libgl1 + libglx0
    libgl1 \
    libglx0 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    # Git (needed for pip install from git)
    git \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# Layer 2: PyTorch CPU (split into sub-layers to avoid OOM/daemon crash)
# ------------------------------------------------------------------
# Pre-fix: upgrade typing_extensions for torch compatibility
RUN pip install --no-cache-dir "typing_extensions>=4.12"

# Step 2a: PyTorch core (no deps — avoids combined memory pressure)
RUN pip install --no-deps --no-cache-dir \
    torch \
    --index-url https://download.pytorch.org/whl/cpu

# Step 2b: PyTorch dependencies + torchvision (smaller install)
RUN pip install --no-cache-dir \
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

# --- OmniShotCut model deps (pre-install to avoid conflicts) ---
RUN pip install --no-cache-dir \
    ffmpeg-python \
    opencv-python-headless \
    huggingface_hub \
    packaging

# --- OmniShotCut package (fixed commit) ---
# pyproject.toml deps installed automatically by pip
RUN pip install --no-cache-dir \
    git+https://github.com/UVA-Computer-Vision-Lab/OmniShotCut.git@23ad6fb41b296fb9258b0e7825125a914573b906

# --- Patch OmniShotCut CUDA hardcodes (CPU-only worker) ---
RUN python -c "\
import omnishotcut, os; \
p = os.path.join(os.path.dirname(omnishotcut.__file__), 'engine.py'); \
c = open(p).read(); \
c = c.replace('model.to(\"cuda\")', 'model.to(\"cpu\")'); \
c = c.replace('.to(\"cuda\")', '.to(\"cpu\")'); \
open(p, 'w').write(c); \
print('Patched engine.py for CPU')"

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
