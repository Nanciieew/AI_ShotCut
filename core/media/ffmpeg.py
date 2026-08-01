"""FFmpeg wrapper — command building and safe execution.

All FFmpeg invocations go through this module.
No task should shell out to ffmpeg directly.
"""

import subprocess

from core.media.exceptions import FFmpegError
from core.media.schemas import FFprobeResult, NormalizationConfig


def build_normalize_command(
    input_path: str,
    output_path: str,
    probe: FFprobeResult,
    config: NormalizationConfig | None = None,
) -> list[str]:
    """Build an FFmpeg normalization command as a parameter list.

    Per spec: FFmpeg标准化_OmniShotCut_Docker_Celery单模型闭环.md §6-7

    - H.264 video, yuv420p, CFR
    - AAC audio, 48000 Hz
    - Faststart enabled
    - Timestamps normalized to zero
    - Preserves original FPS (does NOT force a fixed FPS)
    - Handles missing audio gracefully (-map 0:a:0?)

    Args:
        input_path: Path to input video.
        output_path: Path for normalized output.
        probe: FFprobeResult of the input video.
        config: Optional normalization configuration.

    Returns:
        List of command arguments (safe for subprocess, no shell=True).
    """
    cfg = config or NormalizationConfig()

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        # Video stream
        "-map",
        "0:v:0",
        # Audio stream (optional — `?` means skip if missing)
        "-map",
        "0:a:0?",
        # Video encoding
        "-c:v",
        cfg.video_codec,
        "-pix_fmt",
        cfg.pixel_format,
        "-vsync",
        cfg.frame_rate_mode,
        # Scale to even dimensions (codec requirement)
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        # Preset for speed/quality balance
        "-preset",
        "fast",
        "-crf",
        "23",
    ]

    # Audio encoding (only if audio stream exists)
    if probe.has_audio:
        cmd += [
            "-c:a",
            cfg.audio_codec,
            "-ar",
            str(cfg.audio_sample_rate),
        ]

    # Faststart for web playback
    if cfg.faststart:
        cmd += ["-movflags", "+faststart"]

    # Normalize timestamps
    if cfg.normalize_timestamps:
        cmd += ["-avoid_negative_ts", "make_zero"]

    cmd.append(str(output_path))
    return cmd


def run_ffmpeg(
    cmd: list[str],
    timeout: int = 600,
    description: str = "ffmpeg",
) -> subprocess.CompletedProcess:
    """Execute an FFmpeg command safely.

    - Uses parameter list (NO shell=True)
    - Captures stdout/stderr
    - Enforces timeout
    - Checks return code
    - Reports stderr tail on failure

    Args:
        cmd: FFmpeg command as list of arguments.
        timeout: Maximum execution time in seconds.
        description: Human-readable label for error messages.

    Returns:
        CompletedProcess instance (already check_returncode'd).

    Raises:
        FFmpegError: If command fails or times out.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise FFmpegError(f"{description} timed out after {timeout}s")
    except FileNotFoundError:
        raise FFmpegError("ffmpeg not found. Is FFmpeg installed?")

    if result.returncode != 0:
        stderr_tail = result.stderr[-500:] if result.stderr else "(no stderr)"
        raise FFmpegError(f"{description} failed (exit {result.returncode}): {stderr_tail}")

    return result


def get_ffmpeg_version(ffmpeg_bin: str = "ffmpeg") -> str:
    """Get the FFmpeg version string.

    Returns empty string if ffmpeg is not available.
    """
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # First line is e.g. "ffmpeg version 7.1.5-0+deb13u1 ..."
        return result.stdout.split("\n")[0].strip()
    except Exception:
        return ""
