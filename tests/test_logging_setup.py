import logging

from syncausha.logging_setup import setup_logging


def test_logs_go_to_rotating_file(tmp_path):
    path = setup_logging(tmp_path / "logs")
    root = logging.getLogger()
    try:
        logging.getLogger("syncausha.test").info("bonjour")
        for handler in root.handlers:
            handler.flush()
        assert path == tmp_path / "logs" / "syncausha.log"
        assert "bonjour" in path.read_text(encoding="utf-8")
        assert logging.getLogger("httpx").level == logging.WARNING
    finally:
        for handler in list(root.handlers):
            if getattr(handler, "baseFilename", "").startswith(str(tmp_path)):
                root.removeHandler(handler)
                handler.close()
