"""FFprobe wrapper — structured metadata extraction.

All video metadata extraction goes through this module.
No task should shell out to ffprobe directly.
"""

import json
import os
import subprocess

from core.media.exceptions import FFprobeError
from core.media.schemas import FFprobeResult


def run_ffprobe(
    video_path: str,
    ffprobe_bin: str = "ffprobe",
    timeout: int = 30,
) -> FFprobeResult:
    """Extract structured video metadata via ffprobe.

    Args:
        video_path: Absolute or relative path to the video file.
        ffprobe_bin: Path or command name for ffprobe.
        timeout: Maximum seconds to wait for ffprobe.

    Returns:
        FFprobeResult with structured fields.

    Raises:
        FFprobeError: If ffprobe fails, returns non-zero, or output
            cannot be parsed.
    """
    if not os.path.exists(video_path):
        raise FFprobeError(f"Video file not found: {video_path}")

    cmd = [
        ffprobe_bin,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise FFprobeError(f"ffprobe timed out after {timeout}s: {video_path}")
    except FileNotFoundError:
        raise FFprobeError(f"ffprobe not found: {ffprobe_bin}. Is FFmpeg installed?")

    if result.returncode != 0:
        stderr_tail = result.stderr[-500:] if result.stderr else "(no stderr)"
        raise FFprobeError(f"ffprobe exited with code {result.returncode}: {stderr_tail}")

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise FFprobeError(f"Failed to parse ffprobe JSON output: {e}")

    return _parse_ffprobe_output(info)


def probe_video(
    video_path: str,
    output_dir: str | None = None,
    label: str = "probe",
    ffprobe_bin: str = "ffprobe",
    timeout: int = 30,
) -> FFprobeResult:
    """Run ffprobe and optionally save raw JSON to disk.

    Args:
        video_path: Path to video file.
        output_dir: If provided, saves raw ffprobe JSON as
            ``{label}.json`` in this directory.
        label: Filename prefix for saved probe (e.g. "probe_before").
        ffprobe_bin: Path to ffprobe.
        timeout: Timeout in seconds.

    Returns:
        FFprobeResult with structured metadata.
    """
    probe = run_ffprobe(video_path, ffprobe_bin=ffprobe_bin, timeout=timeout)

    if output_dir is not None and probe.raw_json is not None:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{label}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(probe.raw_json, f, indent=2, ensure_ascii=False)

    return probe


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _parse_ffprobe_output(info: dict) -> FFprobeResult:
    """Parse raw ffprobe JSON into a structured FFprobeResult."""
    fmt = info.get("format", {})
    streams = info.get("streams", [])

    result = FFprobeResult(raw_json=info)

    # Container
    result.container_format = fmt.get("format_name", "unknown")
    if "duration" in fmt and fmt["duration"]:
        try:
            result.duration_ms = int(float(fmt["duration"]) * 1000)
        except (ValueError, TypeError):
            result.duration_ms = 0

    # Start time
    if "start_time" in fmt and fmt["start_time"]:
        try:
            result.start_time_ms = int(float(fmt["start_time"]) * 1000)
        except (ValueError, TypeError):
            result.start_time_ms = 0

    for stream in streams:
        codec_type = stream.get("codec_type", "")

        if codec_type == "video":
            _parse_video_stream(result, stream)
        elif codec_type == "audio":
            _parse_audio_stream(result, stream)

    return result


def _parse_video_stream(result: FFprobeResult, stream: dict) -> None:
    """Parse a video stream entry from ffprobe."""
    result.has_video = True
    result.video_codec = stream.get("codec_name", "unknown")
    result.pixel_format = stream.get("pix_fmt", "unknown")
    result.width = stream.get("width", 0) or 0
    result.height = stream.get("height", 0) or 0

    # Frame count
    nb_frames = stream.get("nb_frames")
    if nb_frames is not None:
        try:
            result.frame_count = int(nb_frames)
        except (ValueError, TypeError):
            pass
    # Fallback: also check nb_read_frames
    if result.frame_count == 0:
        nb_read = stream.get("nb_read_frames")
        if nb_read is not None:
            try:
                result.frame_count = int(nb_read)
            except (ValueError, TypeError):
                pass
    # If still unknown, estimate from duration × fps
    if result.frame_count == 0 and result.duration_ms > 0:
        fps = result.fps_num / max(result.fps_den, 1)
        result.frame_count = int(fps * result.duration_ms / 1000)

    # FPS
    r_frame_rate = stream.get("r_frame_rate", "")
    if r_frame_rate and "/" in r_frame_rate:
        try:
            num_str, den_str = r_frame_rate.split("/")
            result.fps_num = int(num_str)
            result.fps_den = int(den_str)
        except (ValueError, ZeroDivisionError):
            pass
    elif r_frame_rate:
        try:
            fps_val = float(r_frame_rate)
            if fps_val > 0:
                result.fps_num = int(fps_val * 1001)
                result.fps_den = 1001
        except ValueError:
            pass

    # Avg frame rate (used if r_frame_rate is absent or invalid)
    avg_frame_rate = stream.get("avg_frame_rate", "")
    if (result.fps_num == 0 or result.fps_den == 0) and avg_frame_rate:
        try:
            num_str, den_str = avg_frame_rate.split("/")
            result.fps_num = int(num_str)
            result.fps_den = int(den_str)
        except (ValueError, ZeroDivisionError):
            pass

    # Frame rate mode detection (heuristic)
    # If r_frame_rate differs significantly from avg_frame_rate, it's VFR
    if r_frame_rate and avg_frame_rate and r_frame_rate != avg_frame_rate:
        result.frame_rate_mode = "VFR"


def _parse_audio_stream(result: FFprobeResult, stream: dict) -> None:
    """Parse an audio stream entry from ffprobe."""
    result.has_audio = True
    result.audio_codec = stream.get("codec_name")
    sample_rate = stream.get("sample_rate")
    if sample_rate:
        try:
            result.audio_sample_rate = int(sample_rate)
        except (ValueError, TypeError):
            pass
