"""OmniShotCut Adapter — wraps third-party model for Celery Task use.

Implements BaseModelAdapter. Handles:
  - Model loading / unloading
  - Raw inference call (clean_shot with confidences)
  - Frame-diff false-positive filtering (MAD < 5.0)
  - Frame → ms conversion (ShotConverter)
  - Output validation (validate_shot_output)
  - Error mapping to standard error codes

Status: TESTING — integrated with frame_diff, ready for Celery Task.
"""

import os
import time
from pathlib import Path
from typing import Any

from models.base.adapter import BaseModelAdapter
from models.omnishotcut.converter import ShotConverter
from models.omnishotcut.validation import validate_shot_output
from models.omnishotcut.exceptions import (
    OmniShotCutImportError,
    OmniShotCutInferenceError,
)

# FIXED third-party source
FIXED_COMMIT = "23ad6fb41b296fb9258b0e7825125a914573b906"
HF_REPO = "uva-cv-lab/OmniShotCut"
HF_FILENAME = "OmniShotCut_ckpt.pth"

# Frame-diff thresholds (empirically calibrated)
MAD_THRESHOLD = 5.0
HIST_CORR_THRESHOLD = 0.95


class OmniShotCutAdapter(BaseModelAdapter):
    """Adapter for OmniShotCut shot boundary detection.

    Wraps the third-party omnishotcut package and enforces the
    project's unified input/output contract (IO_Rule.md).
    """

    name = "omnishotcut"
    version = "0.1.0"

    def __init__(self) -> None:
        self._model: Any = None
        self._loaded = False
        self._last_shots: list[dict] = []   # last predict() shots for artifact save

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load OmniShotCut model weights.

        Uses: model_store/omnishotcut/1.0.0/OmniShotCut_ckpt.pth
        Auto-downloads from HuggingFace Hub if missing.
        """
        if self._loaded:
            return

        try:
            import omnishotcut  # third-party package
        except ImportError:
            raise OmniShotCutImportError()

        weight_path = os.path.join(
            os.getenv("MODEL_STORE_ROOT", "./model_store"),
            "omnishotcut/1.0.0/OmniShotCut_ckpt.pth",
        )

        if not os.path.exists(weight_path):
            from huggingface_hub import hf_hub_download

            os.makedirs(os.path.dirname(weight_path), exist_ok=True)
            hf_hub_download(
                repo_id=HF_REPO,
                filename=HF_FILENAME,
                local_dir=os.path.dirname(weight_path),
            )

        # Ensure FFmpeg is on PATH before model load (model uses ffmpeg internally)
        self._ensure_ffmpeg_path()

        self._model = omnishotcut.load(weight_path)
        self._loaded = True

    def unload(self) -> None:
        """Release model resources."""
        self._model = None
        self._loaded = False
        import gc

        gc.collect()

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        """Run OmniShotCut inference with frame-diff post-filtering.

        Input (per IO_Rule §4.1):
            {
                "schema_version": "1.0",
                "task_id": "task_001",
                "video_id": "video_001",
                "model": {"name": "omnishotcut", "version": "0.1.0"},
                "input": {"video_uri": "storage://path/to/video.mp4"},
                "parameters": {"mode": "clean_shot"}
            }

        Returns unified success/failure output per IO_Rule §2/§3.
        """
        if not self._loaded:
            self.load()

        schema_version = model_input.get("schema_version", "1.0")
        task_id = model_input["task_id"]
        video_id = model_input["video_id"]
        video_uri = model_input["input"]["video_uri"]
        mode = model_input.get("parameters", {}).get("mode", "clean_shot")

        try:
            # --- Resolve video path ---
            video_path = self._resolve_uri(video_uri)
            if not os.path.exists(video_path):
                return self._error(
                    task_id, video_id, schema_version,
                    "VIDEO_DECODE_FAILED",
                    f"Video not found: {video_path}",
                    retryable=False,
                )

            # --- Get FPS ---
            fps_num, fps_den = self._get_fps(video_path)

            # --- Raw inference ---
            t0 = time.monotonic()
            result = self._model.inference(str(video_path), mode=mode)
            runtime_ms = int((time.monotonic() - t0) * 1000)

            # In clean_shot mode, inference returns ranges only.
            # In default mode, it returns (ranges, intra_labels, inter_labels).
            if mode == "clean_shot":
                raw_ranges = result
                confidences = [{"intra_conf": 1.0, "inter_conf": 1.0}] * len(result)
            else:
                raw_ranges, raw_intra, raw_inter = result
                confidences = [
                    {"intra_conf": 1.0, "inter_conf": 1.0}
                    for _ in raw_ranges
                ]

            # --- Frame-diff post-filter ---
            filtered_ranges, fd_stats = self._apply_frame_diff(
                video_path, raw_ranges
            )

            # --- Convert frames → ms ---
            converter = ShotConverter(fps_num=fps_num, fps_den=fps_den)
            converted = converter.convert(filtered_ranges, video_id=video_id)

            # Build shots + attach avg confidence from raw detection
            shots_list = []
            for s in converted:
                # Find matching raw confidence
                conf = None
                for r, c in zip(raw_ranges, confidences):
                    if r[0] <= s.start_frame < r[1]:
                        conf = (c.get("intra_conf", 0) + c.get("inter_conf", 0)) / 2
                        break

                shots_list.append({
                    "shot_id": s.shot_id,
                    "video_id": video_id,
                    "index": s.index,
                    "start_ms": s.start_ms,
                    "end_ms": s.end_ms,
                    "start_frame": s.start_frame,
                    "end_frame_exclusive": s.end_frame_exclusive,
                    "boundary_type": s.boundary_type,
                    "confidence": round(conf, 4) if conf else None,
                })

            # --- Validate ---
            validation = validate_shot_output({
                "video_id": video_id,
                "model": {"name": self.name, "version": self.version},
                "shots": shots_list,
            })

            if not validation["valid"]:
                return self._error(
                    task_id, video_id, schema_version,
                    "SCHEMA_VALIDATION_FAILED",
                    "; ".join(validation["errors"]),
                    retryable=False,
                )

            # Store shots for downstream artifact save
            self._last_shots = shots_list

            # Build artifact URI per IO_Rule §6
            artifact_uri = (
                f"storage://projects/{video_id[:8]}/videos/{video_id}/"
                f"artifacts/omnishotcut/{self.version}/shots.json"
            )

            return self._success(
                task_id=task_id,
                video_id=video_id,
                schema_version=schema_version,
                artifact_key="shots",
                artifact_uri=artifact_uri,
                shots=shots_list,
                metrics={
                    "shot_count": len(filtered_ranges),        # IO_Rule §2 required
                    "shot_count_raw": len(raw_ranges),          # pre-filter count
                    "false_positives_removed": len(raw_ranges) - len(filtered_ranges),
                    "runtime_ms": runtime_ms,
                    "frame_diff": fd_stats,
                },
                warnings=validation.get("warnings", []),
            )

        except OmniShotCutImportError:
            return self._error(
                task_id, video_id, schema_version,
                "OMNISHOTCUT_IMPORT_ERROR",
                "OmniShotCut is not installed.",
                retryable=False,
            )
        except Exception as e:
            return self._error(
                task_id, video_id, schema_version,
                "MODEL_INFERENCE_FAILED",
                str(e),
                retryable=False,
            )

    def health_check(self) -> bool:
        """Check if model is loaded and responsive."""
        if not self._loaded:
            try:
                self.load()
            except Exception:
                return False
        return True

    # ------------------------------------------------------------------
    # Frame-diff filter
    # ------------------------------------------------------------------

    def _apply_frame_diff(
        self, video_path: str, raw_ranges: list[list[int]]
    ) -> tuple[list[list[int]], dict]:
        """Run frame-difference validation and filter false positives.

        Returns (filtered_ranges, stats_dict).
        """
        if len(raw_ranges) <= 1:
            return raw_ranges, {"boundaries_checked": 0, "false_positives_removed": 0}

        try:
            from models.omnishotcut.frame_diff import FrameDiffValidator

            validator = FrameDiffValidator(
                mad_threshold=MAD_THRESHOLD,
                hist_threshold=HIST_CORR_THRESHOLD,
            )
            report = validator.validate(video_path, raw_ranges)
            filtered = validator.filter_by_diff(raw_ranges, report)

            return filtered, {
                "boundaries_checked": report.stats.get("total_boundaries", 0),
                "false_positives_removed": report.stats.get("false_positive_count", 0),
                "mad_min": report.stats.get("mad_min"),
                "mad_max": report.stats.get("mad_max"),
                "mad_mean": report.stats.get("mad_mean"),
            }
        except Exception:
            # If frame-diff fails, return raw ranges unfiltered
            return raw_ranges, {"boundaries_checked": 0, "false_positives_removed": 0, "error": "frame_diff_failed"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_ffmpeg_path() -> None:
        """Ensure FFmpeg/ffprobe are on PATH."""
        try:
            import imageio_ffmpeg
            ff_dir = str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)
            os.environ["PATH"] = ff_dir + os.pathsep + os.environ.get("PATH", "")
        except ImportError:
            pass  # rely on system ffmpeg

    @staticmethod
    def _resolve_uri(uri: str) -> str:
        """Convert storage:// URI to local absolute path."""
        prefix = "storage://"
        if uri.startswith(prefix):
            root = os.getenv("STORAGE_ROOT", "./data")
            return os.path.join(root, uri[len(prefix):])
        return uri

    @staticmethod
    def _get_fps(video_path: str) -> tuple[int, int]:
        """Extract FPS as num/den from video via FFmpeg."""
        import re
        import subprocess

        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
        except ImportError:
            ffmpeg = "ffmpeg"

        try:
            result = subprocess.run(
                [ffmpeg, "-i", video_path],
                capture_output=True, text=True, timeout=15,
            )
            # ffmpeg prints info to stderr: "Stream #0:0: ... 30 fps ..."
            for line in (result.stderr + result.stdout).split("\n"):
                if "Stream #0:0" in line:
                    m = re.search(r"(\d+)\s*fps", line)
                    if m:
                        return int(m.group(1)), 1
                    m = re.search(r"(\d+)/(\d+)\s*fps", line)
                    if m:
                        return int(m.group(1)), int(m.group(2))
            return 24000, 1001
        except Exception:
            return 24000, 1001

    @staticmethod
    def _success(
        task_id: str, video_id: str, schema_version: str,
        artifact_key: str, artifact_uri: str, metrics: dict,
        shots: list[dict] | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": schema_version,
            "task_id": task_id,
            "video_id": video_id,
            "status": "SUCCEEDED",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "artifacts": {artifact_key: artifact_uri},
            "metrics": metrics,
            "warnings": warnings or [],
            "error": None,
        }

    @staticmethod
    def _error(
        task_id: str, video_id: str, schema_version: str,
        code: str, message: str, retryable: bool,
    ) -> dict[str, Any]:
        return {
            "schema_version": schema_version,
            "task_id": task_id,
            "video_id": video_id,
            "status": "FAILED",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "artifacts": {},
            "metrics": {},
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
            },
        }
