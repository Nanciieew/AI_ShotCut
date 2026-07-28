"""Frame → millisecond converter for OmniShotCut raw output.

OmniShotCut outputs shot ranges as [start_frame, end_frame] where
end_frame is INCLUSIVE. The project schema requires [start_ms, end_ms)
in integer milliseconds with end_frame_exclusive.

This module converts:
  [start_frame, end_frame_inclusive] + fps → [start_ms, end_ms) + frames
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConvertedShot:
    """A single shot after frame-to-ms conversion."""

    shot_id: str
    index: int
    start_ms: int
    end_ms: int
    start_frame: int
    end_frame_exclusive: int
    boundary_type: Optional[str] = None
    confidence: Optional[float] = None


class ShotConverter:
    """Converts OmniShotCut raw frame ranges to project Shot Schema.

    Usage:
        converter = ShotConverter(fps_num=24000, fps_den=1001)
        shots = converter.convert(raw_ranges, video_id="video_001")
    """

    def __init__(self, fps_num: int, fps_den: int) -> None:
        """Initialize with FPS as a rational fraction.

        Args:
            fps_num: FPS numerator.
            fps_den: FPS denominator.
        """
        if fps_num <= 0 or fps_den <= 0:
            raise ValueError(
                f"Invalid FPS: {fps_num}/{fps_den}. Both must be positive."
            )
        self.fps_num = fps_num
        self.fps_den = fps_den

    @property
    def fps(self) -> float:
        """Floating-point FPS for convenience (not for storage)."""
        return self.fps_num / self.fps_den

    def frame_to_ms(self, frame: int) -> int:
        """Convert a frame index to milliseconds (integer, rounded)."""
        return round(frame * self.fps_den * 1000 / self.fps_num)

    def convert(
        self,
        raw_ranges: list[list[int]],
        video_id: str,
        boundary_type: Optional[str] = None,
    ) -> list[ConvertedShot]:
        """Convert OmniShotCut raw frame ranges to project Shots.

        Args:
            raw_ranges: [[start_frame, end_frame_inclusive], ...]
            video_id: Associated video identifier.
            boundary_type: Optional transition type label.

        Returns:
            List of ConvertedShot with ms timestamps and exclusive end frames.
        """
        shots: list[ConvertedShot] = []

        for idx, (start_frame, end_frame_inclusive) in enumerate(raw_ranges):
            # OmniShotCut raw: [start, end] inclusive
            # Project schema:   [start_ms, end_ms) exclusive
            # end_frame_exclusive = end_frame_inclusive + 1
            end_frame_exclusive = end_frame_inclusive + 1

            start_ms = self.frame_to_ms(start_frame)
            end_ms = self.frame_to_ms(end_frame_exclusive)

            shot = ConvertedShot(
                shot_id=f"shot_{idx + 1:06d}",
                index=idx,
                start_ms=start_ms,
                end_ms=end_ms,
                start_frame=start_frame,
                end_frame_exclusive=end_frame_exclusive,
                boundary_type=boundary_type,
                confidence=None,  # clean_shot mode has no confidence
            )
            shots.append(shot)

        return shots
