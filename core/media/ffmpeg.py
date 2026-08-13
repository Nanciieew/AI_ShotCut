"""FFmpeg wrapper — command building and safe execution.

All FFmpeg invocations go through this module.
No task should shell out to ffmpeg directly.
"""

import os
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


def build_shot_proxy_command(
    input_path: str,
    output_path: str,
    probe: FFprobeResult,
    width: int = 320,
    height: int = 180,
) -> list[str]:
    """Build FFmpeg command for 320×180 proxy video (no audio).

    Per spec: OmniShotCut_320x180_Proxy视频方案.md §3-4

    - Scale with aspect ratio preserved, pad to 320×180
    - H.264, yuv420p, veryfast preset, CRF 18
    - No audio (-an)
    - Same FPS as source (-fps_mode passthrough)
    - No -r override, no fps filter
    """
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1"
        ),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-fps_mode",
        "passthrough",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def validate_proxy_output(
    proxy_path: str,
    probe_normalized: FFprobeResult,
    width: int = 320,
    height: int = 180,
) -> list[str]:
    """Validate proxy video against spec requirements.

    Returns list of error strings (empty = valid).
    """
    from core.media.ffprobe import run_ffprobe

    errors: list[str] = []

    if not os.path.exists(proxy_path):
        errors.append("Proxy file missing")
        return errors

    try:
        probe = run_ffprobe(proxy_path)
    except Exception as e:
        errors.append(f"Proxy ffprobe failed: {e}")
        return errors

    if probe.width != width:
        errors.append(f"Width {probe.width} != {width}")
    if probe.height != height:
        errors.append(f"Height {probe.height} != {height}")
    if "h264" not in probe.video_codec.lower():
        errors.append(f"Codec {probe.video_codec} is not H.264")
    if probe.pixel_format != "yuv420p":
        errors.append(f"Pixel format {probe.pixel_format} != yuv420p")
    if probe.has_audio:
        errors.append("Proxy must not have audio")
    if probe.fps_num != probe_normalized.fps_num or probe.fps_den != probe_normalized.fps_den:
        errors.append(
            f"FPS mismatch: {probe.fps_num}/{probe.fps_den} "
            f"!= {probe_normalized.fps_num}/{probe_normalized.fps_den}"
        )
    if probe.frame_count != probe_normalized.frame_count:
        errors.append(
            f"Frame count mismatch: {probe.frame_count} != {probe_normalized.frame_count}"
        )
    if abs(probe.start_time_ms) > 100:
        errors.append(f"Start time {probe.start_time_ms}ms not near zero")
    duration_delta = abs(probe.duration_ms - probe_normalized.duration_ms)
    max_delta = max(probe_normalized.duration_one_frame_ms * 2, 100)
    if duration_delta > max_delta:
        errors.append(f"Duration delta {duration_delta}ms > {max_delta}ms (2 frames)")

    return errors


# ---------------------------------------------------------------------------
# ASR audio extraction (§4.1)
# ---------------------------------------------------------------------------


def build_asr_audio_command(input_path: str, output_path: str) -> list[str]:
    """Build FFmpeg command for 16 kHz mono WAV extraction.

    Produces: PCM S16LE, 16000 Hz, 1 channel — per Doubao SeedASR requirements.
    """
    return [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        input_path,
        "-vn",
        "-map",
        "0:a:0",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        output_path,
    ]


def build_keyframe_extract_command(
    video_path: str,
    output_dir: str,
    shots: list[dict],
    positions: list | None = None,
) -> tuple[list[str], list]:
    """Build FFmpeg command to extract keyframes for all shots in ONE pass.

    Uses select filter with frame index matching. Extracts start + mid + end
    per shot (same strategy as SceneSeg keyf_img_saver).

    Output: shot_{index:06d}_img_{n}.jpg

    Args:
        video_path: Path to source video (normalized.mp4).
        output_dir: Directory for output JPEGs.
        shots: List of shot dicts with start_frame/end_frame_exclusive/index.
        positions: Frame positions per shot. Default: ["start","mid","end"].

    Returns:
        FFmpeg command list (safe for subprocess, no shell=True).
    """
    import os as _os

    _os.makedirs(output_dir, exist_ok=True)

    if positions is None:
        positions = ["start", "mid", "end"]

    frames_to_extract = []
    for shot in shots:
        sf = shot.get("start_frame", 0)
        ef = shot.get("end_frame_exclusive", sf + 1)
        idx = shot.get("index", 0)
        nf = ef - sf

        for i, pos in enumerate(positions):
            if pos == "start":
                frame = sf
            elif pos == "end":
                frame = ef - 1 if ef > sf else sf
            else:
                frame = sf + nf // 2
            frame = max(sf, min(ef - 1, frame))
            frames_to_extract.append((frame, idx, i + 1))

    # Build select expression: eq(n,FRAME)+eq(n,FRAME2)+...
    select_expr = "+".join(f"eq(n\\,{f})" for f, _, _ in frames_to_extract)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"select={select_expr}",
        "-vsync",
        "0",
        "-frame_pts",
        "1",
        f"{output_dir}/frame_%06d.jpg",
    ]
    return cmd, frames_to_extract


def build_keyframe_extract_per_shot_commands(
    video_path: str,
    output_dir: str,
    shots: list[dict],
    positions: list | None = None,
) -> list[tuple[str, list[str]]]:
    """Build one FFmpeg command per shot (simpler, isolated failures).

    Returns list of (shot_id, command_list) tuples.
    """
    import os as _os

    _os.makedirs(output_dir, exist_ok=True)

    if positions is None:
        positions = ["start", "mid", "end"]

    commands = []
    for shot in shots:
        sf = shot.get("start_frame", 0)
        ef = shot.get("end_frame_exclusive", sf + 1)
        sh_idx = shot.get("index", 0)
        shot_id = shot.get("shot_id", f"shot_{sh_idx:06d}")
        nf = ef - sf

        select_parts = []
        filenames = []
        for i, pos in enumerate(positions):
            if pos == "start":
                frame = sf
            elif pos == "end":
                frame = ef - 1 if ef > sf else sf
            else:
                frame = sf + nf // 2
            frame = max(sf, min(ef - 1, frame))
            select_parts.append(f"eq(n\\,{frame})")
            filenames.append(f"shot_{sh_idx:06d}_img_{i + 1}.jpg")

        select_expr = "+".join(select_parts)
        # Use per-shot prefix: all frames from one shot in same dir
        # Since we extract exactly 3 frames per shot, we use numbered output
        out_pattern = f"{output_dir}/shot_{sh_idx:06d}_img_%d.jpg"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"select={select_expr}",
            "-vsync",
            "0",
            "-vframes",
            str(len(positions)),
            out_pattern,
        ]
        commands.append((shot_id, cmd))

    return commands


def validate_keyframe_output(
    output_dir: str,
    shots: list[dict],
    positions: list | None = None,
) -> list[str]:
    """Validate that all expected keyframes were extracted.

    Returns list of error strings (empty = all present).
    """
    import os as _os

    errors = []
    if positions is None:
        positions = ["start", "mid", "end"]

    for shot in shots:
        sh_idx = shot.get("index", 0)
        for i in range(len(positions)):
            expected = _os.path.join(output_dir, f"shot_{sh_idx:06d}_img_{i + 1}.jpg")
            if not _os.path.exists(expected):
                errors.append(f"Missing: {expected}")
            elif _os.path.getsize(expected) == 0:
                errors.append(f"Empty: {expected}")
    return errors


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
