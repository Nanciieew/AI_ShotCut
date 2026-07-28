"""OmniShotCut Adapter — wraps third-party model for Celery Task use.

Implements BaseModelAdapter. Handles:
  - Model loading / unloading
  - Raw inference call
  - Frame → ms conversion
  - Output validation
  - Error mapping to standard error codes

Status: SPIKE — core logic in place, full integration pending.
"""

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


class OmniShotCutAdapter(BaseModelAdapter):
    """Adapter for OmniShotCut shot boundary detection.

    Wraps the third-party omnishotcut package and enforces the
    project's unified input/output contract.
    """

    name = "omnishotcut"
    version = "0.1.0"

    def __init__(self) -> None:
        self._model: Any = None
        self._loaded = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load OmniShotCut model weights.

        Uses: model_store/omnishotcut/1.0.0/OmniShotCut_ckpt.pth
        """
        if self._loaded:
            return

        try:
            import omnishotcut  # noqa: F401
        except ImportError:
            raise OmniShotCutImportError()

        import os

        weight_path = os.path.join(
            os.getenv("MODEL_STORE_ROOT", "./model_store"),
            "omnishotcut/1.0.0/OmniShotCut_ckpt.pth",
        )

        if not os.path.exists(weight_path):
            # Try downloading from HuggingFace Hub
            from huggingface_hub import hf_hub_download

            os.makedirs(os.path.dirname(weight_path), exist_ok=True)
            hf_hub_download(
                repo_id=HF_REPO,
                filename=HF_FILENAME,
                local_dir=os.path.dirname(weight_path),
            )

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
        """Run OmniShotCut inference.

        Input (per IO_Rule §4.1):
            schema_version, task_id, video_id,
            model: {name, version},
            input: {video_uri},
            parameters: {mode: "clean_shot"}

        Returns unified success/failure output.
        """
        if not self._loaded:
            self.load()

        schema_version = model_input.get("schema_version", "1.0")
        task_id = model_input["task_id"]
        video_id = model_input["video_id"]
        video_uri = model_input["input"]["video_uri"]
        mode = model_input.get("parameters", {}).get("mode", "clean_shot")

        try:
            # --- Raw inference ---
            import time
            import os
            from pathlib import Path

            # Convert storage:// URI to local path
            video_path = self._resolve_uri(video_uri)

            if not os.path.exists(video_path):
                return self._error(
                    task_id, video_id, schema_version,
                    "VIDEO_DECODE_FAILED",
                    f"Video not found: {video_path}",
                    retryable=False,
                )

            # Get FPS via ffprobe
            fps_num, fps_den = self._get_fps(video_path)

            t0 = time.monotonic()
            raw_ranges = self._model.inference(str(video_path), mode=mode)
            runtime_ms = int((time.monotonic() - t0) * 1000)

            # --- Convert frames → ms ---
            converter = ShotConverter(fps_num=fps_num, fps_den=fps_den)
            converted = converter.convert(raw_ranges, video_id=video_id)

            # Build output
            shots_list = [{
                "shot_id": s.shot_id,
                "video_id": video_id,
                "index": s.index,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "start_frame": s.start_frame,
                "end_frame_exclusive": s.end_frame_exclusive,
                "boundary_type": s.boundary_type,
                "confidence": s.confidence,
            } for s in converted]

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

            return self._success(
                task_id, video_id, schema_version,
                artifact_key="shots",
                artifact_uri="",  # filled by Celery Task after save
                metrics={
                    "shot_count": len(shots_list),
                    "runtime_ms": runtime_ms,
                },
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
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_uri(uri: str) -> str:
        """Convert storage:// URI to local absolute path."""
        prefix = "storage://"
        if uri.startswith(prefix):
            import os

            root = os.getenv("STORAGE_ROOT", "./data")
            return os.path.join(root, uri[len(prefix):])
        return uri

    @staticmethod
    def _get_fps(video_path: str) -> tuple[int, int]:
        """Extract FPS as num/den from video via ffprobe."""
        import subprocess
        import json

        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=r_frame_rate",
                    "-of", "json",
                    video_path,
                ],
                capture_output=True, text=True, timeout=15,
            )
            info = json.loads(result.stdout)
            fps_str = info["streams"][0]["r_frame_rate"]
            num, den = fps_str.split("/")
            return int(num), int(den)
        except Exception:
            return 24000, 1001  # default NTSC film

    @staticmethod
    def _success(
        task_id: str, video_id: str, schema_version: str,
        artifact_key: str, artifact_uri: str, metrics: dict,
    ) -> dict:
        return {
            "schema_version": schema_version,
            "task_id": task_id,
            "video_id": video_id,
            "status": "SUCCEEDED",
            "model": {"name": "omnishotcut", "version": "0.1.0"},
            "artifacts": {artifact_key: artifact_uri},
            "metrics": metrics,
            "error": None,
        }

    @staticmethod
    def _error(
        task_id: str, video_id: str, schema_version: str,
        code: str, message: str, retryable: bool,
    ) -> dict:
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
