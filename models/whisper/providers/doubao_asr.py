"""Doubao (豆包) ASR provider — ByteDance OpenSpeech native API.

Endpoint: openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash
Auth: X-Api-Key header with speech API key.

Files > 15min are auto-chunked and transcribed in parallel.
"""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

MAX_CHUNK_SECONDS = 900  # 15 minutes per chunk


class DoubaoASRProvider:
    """Doubao speech recognition via ByteDance OpenSpeech.

    Uses the native bigmodel ASR API. Large audio is auto-chunked.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "bigmodel",
        base_url: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash",
        resource_id: str = "volc.bigasr.auc_turbo",
        timeout: int = 300,
        max_workers: int = 8,
    ) -> None:
        self.api_key = api_key.split(":")[-1] if ":" in api_key else api_key
        self.model = model
        self.base_url = base_url
        self.resource_id = resource_id
        self.timeout = timeout
        self.max_workers = max_workers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(self, audio_path: str, language: str | None = None) -> dict:
        """Transcribe audio. Auto-chunks files > 15 minutes."""
        duration = _audio_duration_seconds(audio_path)
        if duration and duration > MAX_CHUNK_SECONDS:
            return self._transcribe_chunked(audio_path, duration)
        return self._transcribe_single(audio_path, language)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _transcribe_single(self, audio_path: str, language: str | None = None) -> dict:
        """Send a single audio file to the ASR API."""
        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        headers = {
            "X-Api-Key": self.api_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
            "X-Api-Sequence": "-1",
            "Content-Type": "application/json",
        }
        payload = {
            "user": {"uid": "ai-shotcut"},
            "audio": {"data": audio_b64},
            "request": {"model_name": self.model},
        }

        t0 = time.monotonic()
        resp = requests.post(self.base_url, headers=headers, json=payload, timeout=self.timeout)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code != 200:
            raise RuntimeError(f"Doubao ASR {resp.status_code}: {resp.text[:500]}")

        result = resp.json()
        result["_elapsed_ms"] = elapsed_ms
        return result

    def _transcribe_chunked(self, audio_path: str, total_seconds: float) -> dict:
        """Split audio into 15min chunks, transcribe in parallel, merge results."""
        chunk_dir = Path(tempfile.mkdtemp(prefix="doubao_chunks_"))
        try:
            n_chunks = max(1, int(total_seconds / MAX_CHUNK_SECONDS) + 1)
            print(f"Chunking {total_seconds:.0f}s audio → {n_chunks} × {MAX_CHUNK_SECONDS}s chunks")

            # Split with ffmpeg
            cmd = [
                "ffmpeg", "-y", "-i", audio_path,
                "-f", "segment", "-segment_time", str(MAX_CHUNK_SECONDS),
                "-c", "copy", str(chunk_dir / "chunk_%03d.wav"),
            ]
            subprocess.run(cmd, capture_output=True, check=True, timeout=120)
            chunks = sorted(chunk_dir.glob("chunk_*.wav"))
            print(f"Split into {len(chunks)} chunks")

            # Parallel transcription
            results = {}
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {
                    pool.submit(self._transcribe_single, str(c)): i
                    for i, c in enumerate(chunks)
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        results[idx] = future.result()
                        print(f"  Chunk {idx + 1}/{len(chunks)} done")
                    except Exception as e:
                        print(f"  Chunk {idx + 1}/{len(chunks)} FAILED: {e}")
                        results[idx] = {"_error": str(e)}

            # Merge results with timestamp offsets
            merged = self._merge_results(results, n_chunks)
            return merged

        finally:
            # Cleanup temp chunks
            for f in chunk_dir.glob("*.wav"):
                try: f.unlink()
                except OSError: pass
            try: chunk_dir.rmdir()
            except OSError: pass

    def _merge_results(self, results: dict, n_chunks: int) -> dict:
        """Merge chunked ASR results with adjusted timestamps."""
        all_utterances = []
        all_texts = []
        total_elapsed = 0
        language = "unknown"

        for i in range(n_chunks):
            r = results.get(i, {})
            if "_error" in r:
                continue
            total_elapsed += r.get("_elapsed_ms", 0)
            offset_ms = i * MAX_CHUNK_SECONDS * 1000

            result_val = r.get("result", {})
            # Handle both legacy list format and current dict format
            if isinstance(result_val, list) and result_val:
                r0 = result_val[0]
            elif isinstance(result_val, dict):
                r0 = result_val
            else:
                continue

            language = r0.get("language", language)
            utterances = r0.get("utterances", [])
            text = r0.get("text", "")
            if text:
                all_texts.append(text)

            if utterances:
                for u in utterances:
                    u = dict(u)
                    u["start_time"] = u.get("start_time", 0) + offset_ms
                    u["end_time"] = u.get("end_time", 0) + offset_ms
                    all_utterances.append(u)
            elif text:
                # No utterances — create a segment from flat text
                all_utterances.append({
                    "text": text,
                    "start_time": offset_ms,
                    "end_time": offset_ms + MAX_CHUNK_SECONDS * 1000,
                    "confidence": 0.0,
                })

        return {
            "result": [{
                "text": " ".join(all_texts),
                "utterances": all_utterances,
                "language": language,
            }],
            "_elapsed_ms": total_elapsed,
            "_chunked": True,
            "_n_chunks": n_chunks,
        }

    def health_check(self) -> bool:
        try:
            resp = requests.get("https://openspeech.bytedance.com", timeout=10)
            return resp.status_code < 500
        except Exception:
            return False


def _audio_duration_seconds(path: str) -> float | None:
    """Get audio duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip()) if result.stdout.strip() else None
    except Exception:
        return None
