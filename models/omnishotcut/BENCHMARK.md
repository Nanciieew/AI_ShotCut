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

## SPIKE Verification (demo_video1.mp4)

| Metric | Value |
|--------|-------|
| Shots detected | 26 |
| Runtime | 21.7s |
| Mode | clean_shot |

## Full Benchmark (2026-07-28, CPU, clean_shot)

| Video | FPS | Frames | Duration | Runtime | Shots | Notes |
|-------|-----|--------|----------|---------|-------|-------|
| Hard_Cut_1.mp4 | 30 | 1266 | 42.2s | 17.9s | 4 | ✅ |
| Multiple_Cuts_hard.mp4 | 30 | 1688 | 56.3s | 23.3s | 13 | ✅ Shortest shot: 6f |
| Multiple_Cuts_smooth.mp4 | 30 | 1382 | 46.1s | 19.8s | 3 | ⚠️ Dissolves filtered, only 3 hard cuts |
| No_Cut_easy.mp4 | 30 | 2729 | 91.0s | 37.2s | 1 | ✅ Correct |
| No_Cut_hard.mp4 | 30 | 2718 | 90.6s | 39.0s | 4 | ❌ FP — should be 1 |

**Key findings**:
- `clean_shot` mode filters dissolve/wipe transitions → `Multiple_Cuts_smooth` only found 3/expected
- Motion/changes in `No_Cut_hard` caused 4 false positives
- CPU inference ~0.4s/frame on 30fps video (~42% real-time)
