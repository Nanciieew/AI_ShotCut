"""Unit tests for executable_info — FFmpeg, FFprobe, Docker, nvidia-smi."""

from core.environment.executable_info import collect_executable_info


def test_collect_executable_info_returns_list():
    results = collect_executable_info()
    assert isinstance(results, list)
    assert len(results) >= 4


def test_ffmpeg_check_exists():
    results = collect_executable_info()
    ffmpeg = next(c for c in results if c["check"] == "ffmpeg")
    assert ffmpeg["status"] in ("PASS", "WARNING", "NOT_INSTALLED")


def test_ffprobe_check_exists():
    results = collect_executable_info()
    ffprobe = next(c for c in results if c["check"] == "ffprobe")
    assert ffprobe["status"] in ("PASS", "WARNING", "NOT_INSTALLED")


def test_docker_check_exists():
    results = collect_executable_info()
    docker = next(c for c in results if c["check"] == "docker")
    assert docker["status"] in ("PASS", "WARNING", "NOT_INSTALLED")


def test_nvidia_smi_check_exists():
    results = collect_executable_info()
    nvsmi = next(c for c in results if c["check"] == "nvidia_smi")
    assert nvsmi["status"] in ("PASS", "WARNING", "NOT_INSTALLED")


def test_redis_db_config_no_secrets():
    """Redis/DB checks must not expose full connection strings."""
    results = collect_executable_info()
    redis_check = next(c for c in results if c["check"] == "redis_configured")
    db_check = next(c for c in results if c["check"] == "database_configured")
    # Only booleans / types, never raw URLs
    assert isinstance(redis_check["value"], bool)
    assert isinstance(db_check["value"], str)  # "sqlite" or "postgresql" or "unknown"
    assert "://" not in str(db_check["value"])
