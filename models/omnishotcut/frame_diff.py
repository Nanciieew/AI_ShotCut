"""Frame-difference validator for shot boundary verification.

Computes pixel-level difference metrics between adjacent frames
at each detected shot boundary. Used to distinguish real hard cuts
(large inter-frame difference) from false positives (small difference).

Metrics:
  - mad: Mean Absolute pixel Difference [0, 255]
  - hist_corr: Histogram correlation [0, 1] — 1 = identical
  - ssd: Sum of Squared Differences (normalized)
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class FrameDiffResult:
    """Pixel-difference metrics for a single boundary."""

    frame_idx: int
    mad: float  # Mean absolute difference [0, 255]
    hist_corr: float  # Histogram correlation [0, 1], higher = more similar
    ssd_norm: float  # Normalized SSD [0, 1]
    is_likely_false: bool = False  # Heuristic flag
    note: str = ""


@dataclass
class FrameDiffReport:
    """Full differential analysis for a video's detected boundaries."""

    video: str
    boundaries: list[FrameDiffResult] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


class FrameDiffValidator:
    """Validates shot boundaries by comparing adjacent frame pixels.

    Usage:
        v = FrameDiffValidator()
        report = v.validate("video.mp4", [(0, 456), (456, 661)], fps=30)
        for b in report.boundaries:
            print(f"frame {b.frame_idx}: MAD={b.mad:.1f} hist_corr={b.hist_corr:.3f}")
    """

    # Heuristic thresholds (calibrated from literature + empirical)
    MAD_HARD_CUT_MIN = 8.0  # Below this, unlikely to be a real hard cut
    HIST_CORR_HARD_CUT_MAX = 0.85  # Above this, frames are too similar

    def __init__(self, mad_threshold: float = 8.0, hist_threshold: float = 0.85) -> None:
        self.mad_threshold = mad_threshold
        self.hist_threshold = hist_threshold

    def validate(
        self,
        video_path: str,
        raw_ranges: list[list[int]],
        fps: float | None = None,
    ) -> FrameDiffReport:
        """Compute frame-difference at each shot boundary.

        A boundary occurs at frame N, where shot[N-1] ends and shot[N] begins.
        We compare frame N-1 (last of prev shot) with frame N (first of next shot).

        Args:
            video_path: Path to video file.
            raw_ranges: OmniShotCut raw output [[start, end], ...].
            fps: Optional FPS for logging.

        Returns:
            FrameDiffReport with per-boundary metrics.
        """
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return FrameDiffReport(video=video_path)

        boundaries: list[FrameDiffResult] = []

        # Extract boundary frame indices (end of each shot → next shot start)
        for i in range(len(raw_ranges) - 1):
            boundary_frame = raw_ranges[i][1]  # frame where shot i ends

            # Read frame at boundary-1 and boundary
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, boundary_frame - 1))
            ret1, f0 = cap.read()
            ret2, f1 = cap.read()

            if not ret1 or not ret2:
                boundaries.append(
                    FrameDiffResult(
                        frame_idx=boundary_frame,
                        mad=-1,
                        hist_corr=0,
                        ssd_norm=0,
                        is_likely_false=False,
                        note="frame read failed",
                    )
                )
                continue

            mad, hist_corr, ssd_norm = self._compute_diff(f0, f1)
            likely_false = (mad < self.mad_threshold) and (hist_corr > self.hist_threshold)

            boundaries.append(
                FrameDiffResult(
                    frame_idx=boundary_frame,
                    mad=round(mad, 2),
                    hist_corr=round(hist_corr, 4),
                    ssd_norm=round(ssd_norm, 6),
                    is_likely_false=likely_false,
                    note=(
                        f"MAD({mad:.1f}) < {self.mad_threshold} "
                        f"AND hist_corr({hist_corr:.3f}) > {self.hist_threshold}"
                        if likely_false
                        else ""
                    ),
                )
            )

        cap.release()

        # Stats
        mads = [b.mad for b in boundaries if b.mad >= 0]
        stats = {}
        if mads:
            stats = {
                "mad_min": round(min(mads), 1),
                "mad_max": round(max(mads), 1),
                "mad_mean": round(np.mean(mads), 1),
                "mad_std": round(np.std(mads), 1),
                "false_positive_count": sum(1 for b in boundaries if b.is_likely_false),
                "total_boundaries": len(boundaries),
            }

        return FrameDiffReport(
            video=video_path,
            boundaries=boundaries,
            stats=stats,
        )

    def filter_by_diff(
        self,
        raw_ranges: list[list[int]],
        report: FrameDiffReport,
    ) -> list[list[int]]:
        """Remove shots separated by boundaries that fail frame-diff check.

        Merges neighboring shots when the boundary between them is flagged
        as a likely false positive (too little pixel change).

        Args:
            raw_ranges: Original shot ranges.
            report: FrameDiffReport from validate().

        Returns:
            Filtered shot ranges with likely-FP boundaries merged.
        """
        if not report.boundaries:
            return raw_ranges

        # Build false-positive boundary set
        fp_frames = {b.frame_idx for b in report.boundaries if b.is_likely_false}

        merged: list[list[int]] = []
        current_start = raw_ranges[0][0]
        current_end = raw_ranges[0][1]

        for i in range(1, len(raw_ranges)):
            boundary = raw_ranges[i - 1][1]
            if boundary in fp_frames:
                # Merge: extend current shot
                current_end = raw_ranges[i][1]
            else:
                merged.append([current_start, current_end])
                current_start = raw_ranges[i][0]
                current_end = raw_ranges[i][1]

        merged.append([current_start, current_end])
        return merged

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_diff(self, frame_a: np.ndarray, frame_b: np.ndarray) -> tuple[float, float, float]:
        """Compute MAD, histogram correlation, and normalized SSD."""
        # Ensure same size
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))

        # Convert to grayscale
        if frame_a.ndim == 3:
            ga = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
            gb = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
        else:
            ga, gb = frame_a, frame_b

        # MAD
        mad = float(np.mean(np.abs(ga.astype(np.float64) - gb.astype(np.float64))))

        # Histogram correlation
        hist_a = cv2.calcHist([ga], [0], None, [256], [0, 256])
        hist_b = cv2.calcHist([gb], [0], None, [256], [0, 256])
        hist_corr = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))

        # Normalized SSD
        diff = ga.astype(np.float64) - gb.astype(np.float64)
        ssd = float(np.sum(diff**2))
        ssd_norm = ssd / (ga.shape[0] * ga.shape[1] * 255.0**2)

        return mad, hist_corr, ssd_norm


# Backward-compatible import
import cv2
