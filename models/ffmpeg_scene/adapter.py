"""FFmpeg Scene Detection Adapter — calls FFmpeg scene filter to detect shots.

Replaces OmniShotCut when GPU/PyTorch is unavailable.
Pure FFmpeg: ~5s vs OmniShotCut ~35min on same video.
"""

import json
import os
import re
import subprocess
import time
from typing import Any

from models.base.adapter import BaseModelAdapter


class FFmpegSceneAdapter(BaseModelAdapter):
    """Shot boundary detection via FFmpeg scene filter.

    Input (IO_Rule):
      input.video_uri — storage:// URI to normalized.mp4

    Output:
      shots.json — same format as OmniShotCut: [{shot_id, index, start_ms, end_ms, ...}]
    """

    name = "ffmpeg_scene"
    version = "0.1.0"

    def __init__(self):
        self._loaded = True  # FFmpeg is always available
        self._last_result: dict = {}

    def load(self) -> None:
        """FFmpeg needs no weights — always ready."""
        self._loaded = True

    def unload(self) -> None:
        pass

    def health_check(self) -> bool:
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        """Run FFmpeg scene detection on the video.

        Parameters (optional, in model_input["parameters"]):
          threshold: float = 0.1 — scene change threshold (0.1-0.5)
          fps: int — override FPS (auto-detected if unset)
        """
        sv = model_input.get("schema_version", "1.0")
        tid = model_input["task_id"]
        vid = model_input["video_id"]
        video_uri = model_input["input"]["video_uri"]
        threshold = model_input.get("parameters", {}).get("threshold", 0.1)

        try:
            video_path = self._resolve(video_uri)
            if not os.path.exists(video_path):
                return self._err(
                    tid, vid, sv, "VIDEO_NOT_FOUND", f"File not found: {video_path}", False
                )

            t0 = time.monotonic()

            # Get FPS
            fps = self._get_fps(video_path)

            # Run FFmpeg scene detection
            shots = self._detect_scenes(video_path, fps, threshold)

            runtime_ms = int((time.monotonic() - t0) * 1000)
            self._last_result = {"video_id": vid, "shots": shots}

            art = (
                f"projects/{vid[:8]}/videos/{vid}/artifacts/ffmpeg_scene/{self.version}/shots.json"
            )

            return {
                "schema_version": sv,
                "task_id": tid,
                "video_id": vid,
                "status": "SUCCEEDED",
                "model": {"name": self.name, "version": self.version},
                "artifacts": {"shots": f"storage://{art}"},
                "metrics": {
                    "shot_count": len(shots),
                    "runtime_ms": runtime_ms,
                    "threshold": threshold,
                },
                "error": None,
            }

        except Exception as e:
            return self._err(tid, vid, sv, "FFMPEG_SCENE_FAILED", str(e), False)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _get_fps(video_path: str) -> float:
        """Get FPS from ffprobe."""
        try:
            r = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    video_path,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            info = json.loads(r.stdout)
            for s in info.get("streams", []):
                if s.get("codec_type") == "video":
                    fps_str = s.get("r_frame_rate", "30/1")
                    num, den = fps_str.split("/")
                    return int(num) / int(den)
        except Exception:
            pass
        return 30.0

    @staticmethod
    def _detect_scenes(video_path: str, fps: float, threshold: float = 0.1) -> list[dict]:
        """Run FFmpeg scene filter and return shots list."""
        r = subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-vf",
                f"select='gt(scene,{threshold})',showinfo",
                "-vsync",
                "vfr",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Parse timestamps from FFmpeg stderr
        times = sorted(set(float(t) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)))

        # Get total duration
        dur_r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        info = json.loads(dur_r.stdout)
        total_dur_s = float(info["format"]["duration"])

        # Build shots list — include time 0 as first shot start
        if times and times[0] > 0.1:
            times.insert(0, 0.0)
        if not times or times[0] != 0.0:
            times.insert(0, 0.0)

        # Deduplicate: merge adjacent detections within 200ms (same cut)
        merged = [times[0]]
        for t in times[1:]:
            if t - merged[-1] > 0.2:
                merged.append(t)
        times = merged

        # Build shots, filtering out too-short ones (noise)
        min_dur_ms = 500  # minimum shot duration
        shots = []
        idx = 0
        for i in range(len(times)):
            start_s = times[i]
            end_s = times[i + 1] if i + 1 < len(times) else total_dur_s
            start_ms = int(start_s * 1000)
            end_ms = int(end_s * 1000)
            if end_ms - start_ms < min_dur_ms:
                continue  # skip noise
            start_frame = int(start_s * fps)
            end_frame = int(end_s * fps)
            shots.append(
                {
                    "shot_id": f"shot_{idx + 1:06d}",
                    "video_id": "",
                    "index": idx,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "start_frame": start_frame,
                    "end_frame_exclusive": end_frame,
                    "boundary_type": "hard_cut" if i > 0 else None,
                    "confidence": 0.8,
                }
            )
            idx += 1

        return shots

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve(uri: str) -> str:
        p = "storage://"
        return (
            os.path.join(os.getenv("STORAGE_ROOT", "./data"), uri[len(p) :])
            if uri.startswith(p)
            else uri
        )

    @staticmethod
    def _err(t, v, s, c, m, r) -> dict:
        return {
            "schema_version": s,
            "task_id": t,
            "video_id": v,
            "status": "FAILED",
            "model": {"name": "ffmpeg_scene", "version": "0.1.0"},
            "artifacts": {},
            "metrics": {},
            "error": {"code": c, "message": m, "retryable": r},
        }
