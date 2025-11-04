import os
import logging
from logging.handlers import RotatingFileHandler

def get_log_dir() -> str:
    """Return absolute path to centralized log directory."""
    from university_system.modules.shared.constants import paths
    return str(paths.LOG_DIR)

def get_log_file(name: str) -> str:
    """Return absolute path to a log file inside centralized logs directory."""
    from university_system.modules.shared.constants import paths
    return str(paths.LOG_DIR / name)

def configure_logging(level=logging.INFO, name=None):
    """Configure root logger with rotating file handler in core/logs/app.log and return a named logger."""
    logfile = get_log_file("app.log")
    handler = RotatingFileHandler(logfile, maxBytes=5_242_880, backupCount=5)
    fmt = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()

    # Avoid adding duplicate handlers for same file
    existing = False
    for h in root_logger.handlers:
        if isinstance(h, RotatingFileHandler):
            try:
                if os.path.abspath(getattr(h, "baseFilename", "")) == os.path.abspath(logfile):
                    existing = True
                    break
            except Exception:
                continue

    if not existing:
        root_logger.setLevel(level)
        root_logger.addHandler(handler)

    return logging.getLogger(name) if name else logging.getLogger()
