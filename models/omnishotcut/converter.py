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
        """Convert a frame index to milliseconds (floor division, exact)."""
        return (frame * self.fps_den * 1000) // self.fps_num

    def convert(
        self,
        raw_ranges: list[list[int]],
        video_id: str,
        boundary_type: Optional[str] = None,
    ) -> list[ConvertedShot]:
        """Convert OmniShotCut raw frame ranges to project Shots.

        Shot[i].end_ms == Shot[i+1].start_ms — guaranteed zero gap by
        using the next shot's start frame to compute the current end_ms.

        Args:
            raw_ranges: [[start_frame, end_frame_inclusive], ...]
            video_id: Associated video identifier.
            boundary_type: Optional transition type label.

        Returns:
            List of ConvertedShot with continuous ms timestamps.
        """
        n = len(raw_ranges)
        if n == 0:
            return []
        if n == 1:
            start_frame, end_incl = raw_ranges[0]
            end_frame_exclusive = end_incl + 1
            return [ConvertedShot(
                shot_id=self._shot_id(0), index=0,
                start_ms=self.frame_to_ms(start_frame),
                end_ms=self.frame_to_ms(end_frame_exclusive),
                start_frame=start_frame,
                end_frame_exclusive=end_frame_exclusive,
                boundary_type=boundary_type,
            )]

        shots: list[ConvertedShot] = []
        for idx in range(n):
            start_frame = raw_ranges[idx][0]
            end_frame_exclusive = raw_ranges[idx][1] + 1  # inclusive→exclusive

            start_ms = self.frame_to_ms(start_frame)
            if idx < n - 1:
                # End = next shot's start → guaranteed zero gap
                next_start = raw_ranges[idx + 1][0]
                end_ms = self.frame_to_ms(next_start)
                end_frame_exclusive = next_start
            else:
                # Last shot: use its own end_frame_exclusive
                end_ms = self.frame_to_ms(end_frame_exclusive)

            shots.append(ConvertedShot(
                shot_id=self._shot_id(idx),
                index=idx,
                start_ms=start_ms,
                end_ms=end_ms,
                start_frame=start_frame,
                end_frame_exclusive=end_frame_exclusive,
                boundary_type=boundary_type,
            ))
        return shots

    @staticmethod
    def _shot_id(index: int) -> str:
        return f"shot_{index + 1:06d}"
