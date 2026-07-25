import os
import sys
import logging
from logging.handlers import RotatingFileHandler

def get_log_dir() -> str:
    """Return absolute path to centralized log directory."""
    from education_system.systems.university.infrastructure import paths
    return str(paths.LOG_DIR)

def get_log_file(name: str) -> str:
    """Return absolute path to a log file inside centralized logs directory."""
    from education_system.systems.university.infrastructure import paths
    return str(paths.LOG_DIR / name)

def configure_logging(level=logging.INFO, name=None):
    """Configure root logger with rotating file handler in core/logs/app.log and return a named logger."""
    logfile = get_log_file("app.log")

    root_logger = logging.getLogger()

    # Check if handler already exists for this file
    existing = False
    for h in root_logger.handlers:
        if isinstance(h, RotatingFileHandler):
            try:
                if os.path.abspath(getattr(h, "baseFilename", "")) == os.path.abspath(logfile):
                    existing = True
                    break
            except Exception:
                continue

    # Only create the file handler if it doesn't exist. The console is owned
    # solely by the application entry point (setup_structured_logging / run.py)
    # so output stays a single consistent "datetime - message" stream; this
    # helper only adds the persistent rotating app.log file handler.
    if not existing:
        fmt = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        formatter = logging.Formatter(fmt)

        file_handler = RotatingFileHandler(logfile, maxBytes=5_242_880, backupCount=5)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        root_logger.setLevel(level)

    return logging.getLogger(name) if name else logging.getLogger()


_messagebox_patched = False


def patch_messagebox_logging():
    """Monkey-patch tkinter messagebox so showerror/showwarning also log to file and console.

    Call this once at GUI startup.  Every subsequent ``messagebox.showerror``
    or ``messagebox.showwarning`` call anywhere in the codebase will
    automatically emit a ``logging.error`` / ``logging.warning`` with the
    dialog title and message (plus the active traceback, if any).
    """
    global _messagebox_patched
    if _messagebox_patched:
        return
    _messagebox_patched = True

    try:
        from tkinter import messagebox
    except ImportError:
        return  # no tkinter available (headless / CLI-only)

    _original_showerror = messagebox.showerror
    _original_showwarning = messagebox.showwarning

    _mb_logger = logging.getLogger("university_system.messagebox")

    def _logged_showerror(title=None, message=None, **kwargs):
        # Log with traceback when called from inside an except block
        exc = sys.exc_info()[1]
        if exc is not None:
            _mb_logger.error("Dialog [%s]: %s", title, message, exc_info=True)
        else:
            _mb_logger.error("Dialog [%s]: %s", title, message)
        return _original_showerror(title, message, **kwargs)

    def _logged_showwarning(title=None, message=None, **kwargs):
        # Warnings are user-facing nudges ("Please select…", "Enter a value…").
        # The active exception (if any) is incidental — most often Tk's own
        # simpledialog.validate catching a ValueError on empty input — and
        # logging the traceback every time produces a lot of noise. Stick
        # to the message; errors keep traceback context separately.
        _mb_logger.warning("Dialog [%s]: %s", title, message)
        return _original_showwarning(title, message, **kwargs)

    messagebox.showerror = _logged_showerror
    messagebox.showwarning = _logged_showwarning
