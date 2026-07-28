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

## Full Benchmark

Run: `python scripts/experiments/omnishotcut/run_benchmark.py`

Outputs saved to: `tests/fixtures/raw_outputs/omnishotcut/`

## Template

```text
| video_name.mp4 | fps | frames | dur (s) | runtime (s) | shots | mode |
```
