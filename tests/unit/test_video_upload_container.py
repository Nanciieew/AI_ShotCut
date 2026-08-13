from apps.api.routes.videos import _container_extension


def test_ffprobe_container_formats_map_to_real_extensions() -> None:
    assert _container_extension("mov,mp4,m4a,3gp,3g2,mj2") == "mp4"
    assert _container_extension("matroska,webm") == "mkv"
    assert _container_extension("avi") == "avi"
    assert _container_extension("mpegts") is None
