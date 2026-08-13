from pathlib import Path

from core.task_storage import StorageService


def test_model_dir_uses_safe_placeholder_and_stays_under_storage_root(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("core.task_storage.STORAGE_ROOT", str(tmp_path))
    directory = Path(
        StorageService.model_dir(
            "a" * 32,
            "b" * 32,
            "c" * 32,
            "ffmpeg_normalizer",
            "1.0.0",
        )
    )

    assert directory.name == "1.0.0"
    assert directory.is_dir()
