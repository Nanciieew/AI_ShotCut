"""Media processing schemas — structured probe results and normalization configs.

All time values in integer milliseconds. FPS stored as rational fraction.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FFprobeResult:
    """Structured video metadata from ffprobe.

    Corresponds to the format defined in:
      FFmpeg标准化_OmniShotCut_Docker_Celery单模型闭环.md §5
    """

    # Video stream
    video_codec: str = "unknown"
    pixel_format: str = "unknown"
    width: int = 0
    height: int = 0
    fps_num: int = 24000
    fps_den: int = 1001
    frame_rate_mode: str = "CFR"  # CFR or VFR

    # Audio stream
    audio_codec: Optional[str] = None
    audio_sample_rate: Optional[int] = None  # Hz

    # Container
    container_format: str = "unknown"
    duration_ms: int = 0
    frame_count: int = 0
    start_time_ms: int = 0

    # Flags
    has_video: bool = True
    has_audio: bool = False

    # Raw ffprobe JSON (for full preservation)
    raw_json: Optional[dict] = None

    @property
    def fps(self) -> float:
        """Floating-point FPS for convenience (not for storage)."""
        if self.fps_den == 0:
            return 0.0
        return self.fps_num / self.fps_den

    @property
    def duration_one_frame_ms(self) -> int:
        """Duration of a single frame in milliseconds (floor)."""
        if self.fps_num == 0:
            return 0
        return (self.fps_den * 1000) // self.fps_num

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict (excludes raw_json)."""
        return {
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "pixel_format": self.pixel_format,
            "width": self.width,
            "height": self.height,
            "fps_num": self.fps_num,
            "fps_den": self.fps_den,
            "frame_rate_mode": self.frame_rate_mode,
            "duration_ms": self.duration_ms,
            "frame_count": self.frame_count,
            "start_time_ms": self.start_time_ms,
            "has_video": self.has_video,
            "has_audio": self.has_audio,
            "audio_sample_rate": self.audio_sample_rate,
            "container_format": self.container_format,
        }


@dataclass
class NormalizationConfig:
    """Standardized output specification for video normalization.

    Per: FFmpeg标准化_OmniShotCut_Docker_Celery单模型闭环.md §6

    FPS handling:
        - Prefer original video's reasonable fixed FPS
        - Convert VFR → CFR if needed
        - Do NOT unconditionally force all videos to a fixed FPS
    """

    # Output container
    container: str = "mp4"

    # Video encoding
    video_codec: str = "libx264"
    pixel_format: str = "yuv420p"
    frame_rate_mode: str = "cfr"  # ffmpeg -vsync value

    # Audio encoding
    audio_codec: str = "aac"
    audio_sample_rate: int = 48000  # Hz

    # Rendering
    faststart: bool = True
    normalize_timestamps: bool = True  # avoid_negative_ts make_zero

    # Validation
    max_duration_delta_ms: int = 100  # allowed drift after normalization

    @property
    def movflags(self) -> str:
        flags = []
        if self.faststart:
            flags.append("+faststart")
        return " ".join(flags) if flags else ""


@dataclass
class NormalizationResult:
    """Result of a video normalization run."""

    # Input
    input_path: str
    input_sha256: str

    # Output
    output_path: str
    output_sha256: str
    output_size_bytes: int

    # Probes (required fields first, then defaults)
    probe_before: FFprobeResult
    probe_after: FFprobeResult

    # Optional paths / metadata
    probe_before_path: str = ""
    probe_after_path: str = ""
    duration_delta_ms: int = 0
    validation_passed: bool = False
    validation_errors: list[str] = field(default_factory=list)
    ffmpeg_version: str = ""
    ffmpeg_command: list[str] = field(default_factory=list)
    runtime_ms: int = 0
    manifest_path: str = ""
