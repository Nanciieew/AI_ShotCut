#!/bin/bash
# Verify OmniShotCut inference environment inside Worker container.
# Run: docker compose up -d worker && docker exec movie-worker bash scripts/dev/verify_worker_inference.sh

echo "============================================"
echo "Worker Inference Environment Verification"
echo "============================================"

check() { echo -n "$1 ... "; eval "$2" >/dev/null 2>&1 && echo "✅ PASS" || echo "❌ FAILED"; }
not_run() { echo "🔸 $1: NOT RUN"; }

echo ""
echo "--- Core Imports ---"
check "import torch"          "python -c 'import torch; print(torch.__version__)'"
check "torch.cuda.is_available()" "python -c 'import torch; print(torch.cuda.is_available())'"
check "import torchvision"   "python -c 'import torchvision; print(torchvision.__version__)'"
check "import cv2"           "python -c 'import cv2; print(cv2.__version__)'"
check "import omnishotcut"   "python -c 'import omnishotcut; print(omnishotcut.__file__)'"

echo ""
echo "--- System Tools ---"
check "ffmpeg"      "ffmpeg -version"
check "ffprobe"     "ffprobe -version"

echo ""
echo "--- Volumes ---"
echo -n "MODEL_STORE_ROOT ... "; [ -d "$MODEL_STORE_ROOT" ] && echo "✅ $MODEL_STORE_ROOT exists" || echo "❌ missing"
[ -d "$MODEL_STORE_ROOT" ] && ls "$MODEL_STORE_ROOT/omnishotcut/1.0.0/" 2>/dev/null || true
echo -n "STORAGE_ROOT ... "; [ -d "$STORAGE_ROOT" ] && echo "✅ $STORAGE_ROOT exists" || echo "❌ missing"

echo ""
echo "--- Test Fixtures ---"
FIX_DIR="/app/tests/fixtures/videos/omnishotcut"
if [ -d "$FIX_DIR" ]; then
    echo "✅ $FIX_DIR"
    ls -lh "$FIX_DIR"/*.mp4 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
else
    echo "❌ $FIX_DIR missing"
fi

echo ""
echo "--- OmniShotCut Weight ---"
W="$MODEL_STORE_ROOT/omnishotcut/1.0.0/OmniShotCut_ckpt.pth"
if [ -f "$W" ]; then
    echo "✅ Weights: $(du -h "$W" | cut -f1)"
else
    echo "❌ Weights missing: $W"
fi

echo ""
echo "--- Raw Inference (smoke test) ---"
SMALLEST=$(ls -S "$FIX_DIR"/*.mp4 2>/dev/null | tail -1)
if [ -f "$SMALLEST" ]; then
    echo "Running on: $SMALLEST"
    python -c "
import time, os
os.environ['PATH'] = '/usr/bin:' + os.environ.get('PATH','')
import omnishotcut
w = os.path.join(os.environ['MODEL_STORE_ROOT'], 'omnishotcut/1.0.0/OmniShotCut_ckpt.pth')
model = omnishotcut.load(w)
t0 = time.monotonic()
ranges, confs = model.inference('$SMALLEST', mode='clean_shot')
rt = time.monotonic() - t0
print(f'Shots: {len(ranges)}  Runtime: {rt:.1f}s')
for r,c in zip(ranges[:3], confs[:3]):
    print(f'  [{r[0]:>5},{r[1]:>5}] intra_conf={c[\"intra_conf\"]:.3f}')
" 2>&1 && echo "✅ Raw inference OK" || echo "❌ Raw inference FAILED"
else
    not_run "Raw Inference" "No test fixtures found"
fi

echo ""
echo "============================================"
echo "Verification complete."
echo "============================================"
