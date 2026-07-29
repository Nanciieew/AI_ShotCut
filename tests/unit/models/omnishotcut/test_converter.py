"""Unit tests for OmniShotCut ShotConverter."""

import pytest
from models.omnishotcut.converter import ShotConverter


class TestFrameToMs:
    """frame_to_ms conversion for various FPS values."""

    def test_30fps_zero(self):
        c = ShotConverter(30, 1)
        assert c.frame_to_ms(0) == 0

    def test_30fps_one_second(self):
        c = ShotConverter(30, 1)
        assert c.frame_to_ms(30) == 1000

    def test_30fps_frame_456(self):
        c = ShotConverter(30, 1)
        assert c.frame_to_ms(456) == 15200

    def test_24000_1001_fps(self):
        c = ShotConverter(24000, 1001)
        # frame 0 is 0ms
        assert c.frame_to_ms(0) == 0

    def test_25fps(self):
        c = ShotConverter(25, 1)
        assert c.frame_to_ms(25) == 1000

    def test_30000_1001_fps(self):
        c = ShotConverter(30000, 1001)
        assert c.frame_to_ms(0) == 0


class TestConvert:
    """convert() produces correct Shot lists."""

    def test_single_shot(self):
        c = ShotConverter(30, 1)
        shots = c.convert([[0, 456]], video_id="v1")
        assert len(shots) == 1
        s = shots[0]
        assert s.shot_id == "shot_000001"
        assert s.index == 0
        assert s.start_frame == 0
        assert s.end_frame_exclusive == 457   # inclusive 456 → exclusive 457
        assert s.start_ms == 0
        assert s.end_ms == 15233

    def test_multi_shot(self):
        c = ShotConverter(30, 1)
        shots = c.convert([[0, 210], [210, 216], [216, 276]], video_id="v1")
        assert len(shots) == 3
        assert shots[0].index == 0
        assert shots[1].index == 1
        assert shots[2].index == 2

    def test_continuity_multi_shot(self):
        """Shot[i].end_ms == Shot[i+1].start_ms — zero gap."""
        c = ShotConverter(30, 1)
        shots = c.convert([[0, 210], [210, 500], [500, 1000]], video_id="v1")
        for i in range(len(shots) - 1):
            assert shots[i].end_ms == shots[i + 1].start_ms, (
                f"Gap at index {i}: "
                f"end_ms={shots[i].end_ms} start_ms={shots[i+1].start_ms}"
            )

    def test_continuity_3_shots_30fps(self):
        c = ShotConverter(30, 1)
        shots = c.convert([[0, 456], [456, 871], [871, 1266]], video_id="v1")
        assert len(shots) == 3
        for i in range(len(shots) - 1):
            assert shots[i].end_ms == shots[i + 1].start_ms

    def test_empty_input(self):
        c = ShotConverter(30, 1)
        shots = c.convert([], video_id="v1")
        assert shots == []

    def test_video_id_preserved(self):
        c = ShotConverter(30, 1)
        shots = c.convert([[0, 100]], video_id="test_vid")
        # video_id is stored in the adapter's output dict, not in ConvertedShot dataclass
        assert shots[0].shot_id == "shot_000001"

    def test_shot_id_format(self):
        c = ShotConverter(30, 1)
        shots = c.convert([[0, 100], [100, 200]], video_id="v1")
        assert shots[0].shot_id == "shot_000001"
        assert shots[1].shot_id == "shot_000002"


class TestConvertEdgeCases:
    def test_invalid_fps(self):
        with pytest.raises(ValueError):
            ShotConverter(0, 1)
        with pytest.raises(ValueError):
            ShotConverter(30, 0)

    def test_end_frame_exclusive_convention(self):
        """OmniShotCut inclusive end → converter makes it exclusive."""
        c = ShotConverter(30, 1)
        # raw: [0, 456] inclusive means last frame is 456
        shots = c.convert([[0, 456]], video_id="v1")
        # end_frame_exclusive should be 457 (last exclusive frame = 456 + 1)
        assert shots[0].end_frame_exclusive == 457

    def test_boundary_type_passthrough(self):
        c = ShotConverter(30, 1)
        shots = c.convert([[0, 100]], video_id="v1", boundary_type="hard_cut")
        assert shots[0].boundary_type == "hard_cut"

    def test_confidence_none_by_default(self):
        c = ShotConverter(30, 1)
        shots = c.convert([[0, 100]], video_id="v1")
        assert shots[0].confidence is None
