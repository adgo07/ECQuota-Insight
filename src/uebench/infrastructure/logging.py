from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_directory: Path) -> Path:
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / "uebench.log"
    root = logging.getLogger()
    if any(isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(log_path) for handler in root.handlers):
        return log_path
    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.captureWarnings(True)
    logging.getLogger(__name__).info("日志初始化完成")
    return log_path
