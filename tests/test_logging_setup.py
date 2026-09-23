import logging
import os

import pytest

from syncausha.logging_setup import setup_logging


@pytest.fixture
def log_dir(tmp_path):
    yield tmp_path / "logs"
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "baseFilename", "").startswith(str(tmp_path)):
            root.removeHandler(handler)
            handler.close()


def file_handlers(path):
    return [h for h in logging.getLogger().handlers if getattr(h, "baseFilename", None) == os.path.abspath(path)]


def test_logs_go_to_rotating_file(log_dir):
    path = setup_logging(log_dir)
    logging.getLogger("syncausha.test").info("bonjour")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert path == log_dir / "syncausha.log"
    assert "bonjour" in path.read_text(encoding="utf-8")
    assert logging.getLogger("httpx").level == logging.WARNING


def test_setup_twice_keeps_a_single_handler(log_dir):
    path = setup_logging(log_dir)
    setup_logging(log_dir)
    assert len(file_handlers(path)) == 1
