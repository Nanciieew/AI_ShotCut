"""Unit tests for core/media/keyframes.py — target math + extraction."""

import io
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent))

from core.media.keyframes import (
    select_frame,
    frame_to_timestamp_ms,
    compute_keyframe_targets,
    extract_keyframes,
    KeyframeTarget,
    ExtractionResult,
    POSITIONS,
)

# ---------------------------------------------------------------------------
# Target frame math (integer arithmetic, no round(), no floats)
# ---------------------------------------------------------------------------

class TestSelectFrame:
    """Integer target frame selection."""

    def test_normal_shot_24000_1001(self):
        """Shot [0, 103) at ~23.976fps."""
        assert select_frame(0, 103, 1, 4) == 26   # 25%
        assert select_frame(0, 103, 1, 2) == 51   # 50%
        assert select_frame(0, 103, 3, 4) == 77   # 75%

    def test_single_frame_shot(self):
        """1-frame shot: all positions → same frame."""
        for num, den in POSITIONS:
            assert select_frame(10, 11, num, den) == 10

    def test_two_frame_shot(self):
        """2-frame shot: 2 unique, 25%/50% diverge."""
        assert select_frame(10, 12, 1, 4) == 10
        assert select_frame(10, 12, 1, 2) == 11
        assert select_frame(10, 12, 3, 4) == 11

    def test_three_frame_shot(self):
        """3-frame shot: frames [10,11,12], max_offset=2.
        25% offset=1→frame 11, 50% offset=1→frame 11, 75% offset=2→frame 12."""
        assert select_frame(10, 13, 1, 4) == 11
        assert select_frame(10, 13, 1, 2) == 11
        assert select_frame(10, 13, 3, 4) == 12

    def test_very_long_shot(self):
        """Long shot: positions spread across full range."""
        f25 = select_frame(0, 10001, 1, 4)
        f50 = select_frame(0, 10001, 1, 2)
        f75 = select_frame(0, 10001, 3, 4)
        assert f25 < f50 < f75
        assert f25 >= 0 and f75 <= 10000

    def test_invalid_span_raises(self):
        """Zero or negative span raises ValueError."""
        with pytest.raises(ValueError):
            select_frame(5, 5, 1, 4)
        with pytest.raises(ValueError):
            select_frame(5, 3, 1, 4)


class TestFrameToTimestampMs:
    """Integer timestamp conversion."""

    def test_known_frames_24000_1001(self):
        assert frame_to_timestamp_ms(26, 24000, 1001) == 1084
        assert frame_to_timestamp_ms(51, 24000, 1001) == 2127
        assert frame_to_timestamp_ms(77, 24000, 1001) == 3212

    def test_frame_zero(self):
        assert frame_to_timestamp_ms(0, 24000, 1001) == 0
        assert frame_to_timestamp_ms(0, 30000, 1001) == 0

    def test_30fps(self):
        """Integer FPS: 30fps → each frame = 1000/30 = 33.333...ms."""
        assert frame_to_timestamp_ms(1, 30, 1) == 33
        assert frame_to_timestamp_ms(30, 30, 1) == 1000


# ---------------------------------------------------------------------------
# compute_keyframe_targets
# ---------------------------------------------------------------------------

class TestComputeKeyframeTargets:
    """Full target computation from shot list."""

    def test_single_shot_three_targets(self):
        shots = [
            {"shot_id": "shot_000001", "index": 0,
             "start_frame": 0, "end_frame_exclusive": 103,
             "start_ms": 0, "end_ms": 4280},
        ]
        targets = compute_keyframe_targets(shots, 24000, 1001)
        assert len(targets) == 3
        assert [t.frame_number for t in targets] == [26, 51, 77]

    def test_targets_sorted_by_frame_number(self):
        shots = [
            {"shot_id": "shot_000002", "index": 1,
             "start_frame": 100, "end_frame_exclusive": 200,
             "start_ms": 4170, "end_ms": 8345},
            {"shot_id": "shot_000001", "index": 0,
             "start_frame": 0, "end_frame_exclusive": 100,
             "start_ms": 0, "end_ms": 4170},
        ]
        targets = compute_keyframe_targets(shots, 24000, 1001)
        frames = [t.frame_number for t in targets]
        assert frames == sorted(frames), f"Not sorted: {frames}"

    def test_global_dedup_overlapping_shots(self):
        """Two shots that share a frame boundary should dedup."""
        shots = [
            {"shot_id": "shot_01", "index": 0,
             "start_frame": 0, "end_frame_exclusive": 10},
            {"shot_id": "shot_02", "index": 1,
             "start_frame": 10, "end_frame_exclusive": 20},
        ]
        targets = compute_keyframe_targets(shots, 24000, 1001)
        frames = [t.frame_number for t in targets]
        assert len(frames) == len(set(frames)), f"Duplicate frames: {frames}"

    def test_filenames_are_deterministic(self):
        shots = [
            {"shot_id": "shot_000001", "index": 0,
             "start_frame": 0, "end_frame_exclusive": 100},
        ]
        targets = compute_keyframe_targets(shots, 24000, 1001)
        expected = [
            "shot_000001_001_004.jpg",
            "shot_000001_001_002.jpg",
            "shot_000001_003_004.jpg",
        ]
        assert [t.filename for t in targets] == expected

    def test_missing_frame_fields_raises(self):
        shots = [{"shot_id": "bad_shot", "index": 0}]
        with pytest.raises(ValueError, match="missing frame fields"):
            compute_keyframe_targets(shots, 24000, 1001)


# ---------------------------------------------------------------------------
# extract_keyframes (requires PyAV)
# ---------------------------------------------------------------------------

class TestExtractKeyframes:
    """Single-pass PyAV extraction tests."""

    @pytest.fixture
    def synthetic_video_path(self):
        """Create a small 30-frame CFR H.264 test video via PyAV."""
        import av

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.close()

        container = av.open(tmp.name, "w")
        stream = container.add_stream("libx264", rate=30)
        stream.width = 64
        stream.height = 48
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "30", "preset": "ultrafast"}

        for i in range(30):
            frame = av.VideoFrame(64, 48, "yuv420p")
            # Vary the luma so each frame has a unique SHA-256
            for plane in range(3):
                p = frame.planes[plane]
                buf = bytes([(i * 8 + plane * 3) % 256] * p.buffer_size)
                p.update(buf)
            for packet in stream.encode(frame):
                container.mux(packet)

        for packet in stream.encode():
            container.mux(packet)
        container.close()

        yield tmp.name
        os.unlink(tmp.name)

    def test_extract_known_frames(self, synthetic_video_path):
        """Extract frames 0, 15, 29 and verify they exist."""
        targets = [
            KeyframeTarget(
                frame_number=0, timestamp_ms=0,
                shot_id="test", position_num=1, position_den=4,
                filename="frame_000.jpg",
            ),
            KeyframeTarget(
                frame_number=15, timestamp_ms=500,
                shot_id="test", position_num=1, position_den=2,
                filename="frame_015.jpg",
            ),
            KeyframeTarget(
                frame_number=29, timestamp_ms=966,
                shot_id="test", position_num=3, position_den=4,
                filename="frame_029.jpg",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_keyframes(
                video_path=synthetic_video_path,
                targets=targets,
                output_dir=Path(tmpdir),
                image_format="jpeg",
                quality=85,
                max_long_side=672,
            )

            assert len(result.saved) == 3
            assert len(result.not_found) == 0
            assert all(t.saved for t in targets)
            assert all(os.path.exists(Path(tmpdir) / t.filename) for t in targets)

            # Verify SHA-256 is non-empty
            for t in targets:
                assert len(t.sha256) == 64
                assert t.size_bytes > 0

            # Verify images are valid JPEGs
            for t in targets:
                path = Path(tmpdir) / t.filename
                data = path.read_bytes()
                assert data[:3] == b"\xff\xd8\xff", f"Not a JPEG: {t.filename}"

            # Verify no .tmp residue
            tmp_files = list(Path(tmpdir).glob("*.tmp"))
            assert len(tmp_files) == 0, f"Temporary files left: {tmp_files}"

    def test_resize_respects_max_long_side(self, synthetic_video_path):
        """Output images should not exceed max_long_side."""
        from PIL import Image

        targets = [
            KeyframeTarget(
                frame_number=5, timestamp_ms=166,
                shot_id="test", position_num=1, position_den=2,
                filename="frame_005.jpg",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            extract_keyframes(
                video_path=synthetic_video_path,
                targets=targets,
                output_dir=Path(tmpdir),
                image_format="jpeg",
                quality=85,
                max_long_side=32,  # smaller than 64x48
            )

            img = Image.open(Path(tmpdir) / "frame_005.jpg")
            try:
                assert max(img.size) == 32
                # Aspect ratio: 64:48 = 4:3
                assert img.size in ((32, 24), (24, 32))
            finally:
                img.close()

    def test_empty_targets(self, synthetic_video_path):
        """Empty target list returns immediately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_keyframes(
                video_path=synthetic_video_path,
                targets=[],
                output_dir=Path(tmpdir),
            )
            assert len(result.saved) == 0
            assert len(result.not_found) == 0

    def test_sha256_is_deterministic(self, synthetic_video_path):
        """Same frame encoded twice → same SHA-256."""
        targets_a = [
            KeyframeTarget(frame_number=10, timestamp_ms=333,
                           shot_id="a", position_num=1, position_den=2,
                           filename="a.jpg"),
        ]
        targets_b = [
            KeyframeTarget(frame_number=10, timestamp_ms=333,
                           shot_id="b", position_num=1, position_den=2,
                           filename="b.jpg"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            extract_keyframes(synthetic_video_path, targets_a, Path(tmpdir),
                              image_format="jpeg", quality=100)
            extract_keyframes(synthetic_video_path, targets_b, Path(tmpdir),
                              image_format="jpeg", quality=100)

            assert targets_a[0].sha256 == targets_b[0].sha256
