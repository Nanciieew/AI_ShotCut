# OmniShotCut Benchmark Log

## Environment (2026-07-28)

| Item | Value |
|------|-------|
| Python | 3.14.4 |
| PyTorch | 2.13.0+cpu |
| CUDA | Not available |
| Device | CPU |
| FFmpeg | 7.1 (imageio-ffmpeg) |
| Commit | 23ad6fb41b296fb9258b0e7825125a914573b906 |
| Weights | OmniShotCut_ckpt.pth (156.5 MB, SHA256 verified) |
| Resolution | 128×96 (hardcoded in model) |

## Full Benchmark (2026-07-28, CPU, clean_shot + frame-diff MAD<5.0)

| Video | Raw | Filt | Expected | Status | Note |
|-------|-----|------|----------|--------|------|
| Hard_Cut_1.mp4 | 4 | 3 | 3 | ✅ | frame 661 FP filtered (MAD=2.6) |
| Multiple_Cuts_hard.mp4 | 13 | 13 | 13 | ✅ | All boundaries MAD > 21 |
| Multiple_Cuts_smooth.mp4 | 3 | 3 | 7 | ❌ | Dissolve blind (known limitation) |
| No_Cut_easy.mp4 | 1 | 1 | 1 | ✅ | — |
| No_Cut_hard.mp4 | 4 | 1 | 1 | ✅ | 3 FP filtered (MAD 0.8~1.6) |

### Frame-diff filter stats

| Video | Boundaries | MAD min | MAD max | MAD mean | FP flagged |
|-------|-----------|---------|---------|----------|------------|
| Hard_Cut_1 | 3 | 2.6 | 63.9 | 37.9 | 1 |
| Multiple_Cuts_hard | 12 | 21.6 | 68.0 | 47.8 | 0 |
| Multiple_Cuts_smooth | 2 | 15.1 | 21.4 | 18.3 | 0 |
| No_Cut_easy | 0 | — | — | — | 0 |
| No_Cut_hard | 3 | 0.8 | 1.6 | 1.2 | 3 |

**Threshold: MAD < 5.0 AND hist_corr > 0.95 → flag as FP.**
Real hard cuts have MAD > 15; false positives have MAD < 3.

## Known Limitations

### 1. Dissolve/Wipe Blindness (Multiple_Cuts_smooth)

- Model only detects 2/6 boundaries (3/7 shots)
- All 6 dissolve transitions classified as `intra=General` with conf > 0.99
- **Root cause**: 128×96 inference resolution cannot distinguish subtle cross-fades from normal scene content
- Both `clean_shot` and `default` modes return identical results (no labels other than General detected)
- **Mitigation**: Requires higher-resolution model or dedicated dissolve detector

### 2. High-Confidence False Positives (No_Cut_hard)

- Model detects 4 shots where 1 expected (3 false positives)
- All 4 detections have `intra_conf > 0.997`, `inter_conf > 0.999`
- **Root cause**: Motion/content changes at 128×96 appear as hard cuts to the model
- Confidence filtering CANNOT solve this — false positives have same confidence as true positives
- **Mitigation**: Requires scene-level context or secondary validation model

### 3. No Confidence Discrimination

- All detections (both correct and false) have conf > 0.99
- The model's `argmax` output with post-hoc softmax probability does not provide useful uncertainty estimates
- Confidence cannot be used as a filter criterion for this model

## Code Patches Applied

### engine.py
- `_run_on_numpy`: now returns `(ranges, intra_labels, inter_labels, confidences)` — 4-tuple
- Each confidence: `{"intra_conf": float, "inter_conf": float}` (softmax probability at argmax)
- `merge_predictions`: on duplicate frames, keeps higher-confidence boundary

### __init__.py
- `OmniShotCutModel.inference()`: 
  - `clean_shot` mode → returns `(ranges, confidences)`
  - `default` mode → returns `(ranges, intra_labels, inter_labels, confidences)`
