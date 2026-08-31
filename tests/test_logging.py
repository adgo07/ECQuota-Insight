from pathlib import Path

from uebench.infrastructure.logging import close_logging, configure_logging


def test_close_logging_releases_windows_file_handle(tmp_path: Path) -> None:
    log_path = configure_logging(tmp_path)
    assert log_path.exists()

    close_logging()
    log_path.unlink()
    assert not log_path.exists()
