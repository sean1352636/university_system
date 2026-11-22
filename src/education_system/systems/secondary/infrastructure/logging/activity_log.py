"""User activity log for the Secondary School System.

Records what each signed-in person does - signing in and out, every screen
opened or refused, every pupil viewed, searched, added, changed or deleted -
as one line per action in ``var/logs/secondary/activity.log``
(``paths.SECONDARY_ACTIVITY_LOG``)::

    2026-11-03 09:14:02 | session=3f9a1c2e | user=admin2 | role=admin | gui | pupil.update | target=SEC000004 | outcome=ok | fields=form_group,year_group

Fields, always in this order: time, session (groups one sign-in's lines),
user, role, interface (gui/cli), action, target, outcome, then any details
as ``key=value``.

What is *not* written: the values of personal data. A change records which
fields changed, not what they changed to (the full before/after lives in the
database's ``pupil_audit`` table, which has access control); a search records
its filters and how many pupils matched, not the text typed. Pupils are
identified by admission number. That keeps the file useful for "who did what,
when" without turning it into a second copy of pupil records.

The file rotates at 5 MB, keeping 10 old files, and is created readable by
its owner only. Writing to it can never stop the application: any failure is
reported once to the normal application log and the action carries on.

Usage::

    from education_system.systems.secondary.infrastructure import activity_log
    activity_log.start_session(principal, "gui")
    activity_log.record("pupil.view", target="SEC000004")
    activity_log.end_session("logout")
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from education_system import paths

LOGGER_NAME = "education_system.secondary.activity"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 10

_app_logger = logging.getLogger(__name__)
_activity = logging.getLogger(LOGGER_NAME)
# Keep these lines out of the console and the general application log.
_activity.propagate = False
_activity.setLevel(logging.INFO)

_lock = threading.Lock()
_handler: logging.Handler | None = None
_override: Path | None = None
_warned = False

_session: dict[str, str | None] = {
    "id": None, "user": None, "role": None, "interface": None,
}


# ── File setup ───────────────────────────────────────────────────────

def log_path() -> Path:
    """The activity log file in use."""
    return _override or paths.SECONDARY_ACTIVITY_LOG


def use_log_file(path: str | Path | None) -> None:
    """Write to *path* instead (``None`` restores the default). For tests."""
    global _override
    with _lock:
        _override = Path(path) if path is not None else None
        _close_handler()


def _close_handler() -> None:
    global _handler
    if _handler is not None:
        _activity.removeHandler(_handler)
        try:
            _handler.close()
        except Exception:
            pass
        _handler = None


def _ensure_handler() -> bool:
    """Attach the rotating file handler on first use. False if unavailable."""
    global _handler, _warned
    if _handler is not None:
        return True
    with _lock:
        if _handler is not None:
            return True
        path = log_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                # Create it owner-only before the handler opens it.
                os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
            handler = RotatingFileHandler(path, maxBytes=MAX_BYTES,
                                          backupCount=BACKUP_COUNT, encoding="utf-8")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
            _activity.addHandler(handler)
            _handler = handler
            return True
        except OSError:
            if not _warned:
                _app_logger.exception("Secondary activity log unavailable at %s", path)
                _warned = True
            return False


# ── Sessions ─────────────────────────────────────────────────────────

def start_session(principal: Any, interface: str) -> str:
    """Remember who is signed in, then log ``session.start``. Returns the
    session id that groups this sign-in's lines."""
    _session.update(
        id=uuid.uuid4().hex[:8],
        user=getattr(principal, "username", None) or None,
        role=getattr(principal, "role", None) or None,
        interface=interface,
    )
    record("session.start")
    return _session["id"] or ""


def end_session(reason: str) -> None:
    """Log ``session.end`` with *reason* (logout, idle, switch, shutdown...)."""
    if _session["id"] is None:
        return
    record("session.end", reason=reason)
    _session.update(id=None, user=None, role=None, interface=None)


def current_session() -> dict[str, str | None]:
    return dict(_session)


# ── Recording ────────────────────────────────────────────────────────

def _clean(value: Any) -> str:
    """One-line, delimiter-safe text, so a typed value can't forge a line."""
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ").replace("|", "/")
    return text[:200]


def record(action: str, *, target: Any = None, outcome: str = "ok",
           principal: Any = None, interface: str | None = None, **details: Any) -> None:
    """Write one activity line. Never raises.

    *principal* / *interface* default to the current session. *details* are
    appended as ``key=value``; lists are joined with commas.
    """
    try:
        if not _ensure_handler():
            return
        user = getattr(principal, "username", None) if principal else _session["user"]
        role = getattr(principal, "role", None) if principal else _session["role"]
        parts = [
            f"session={_session['id'] or '-'}",
            f"user={_clean(user or '-')}",
            f"role={_clean(role or '-')}",
            _clean(interface or _session["interface"] or "-"),
            _clean(action),
            f"target={_clean(target) if target not in (None, '') else '-'}",
            f"outcome={_clean(outcome)}",
        ]
        for key, value in details.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                value = ",".join(sorted(str(v) for v in value))
            parts.append(f"{_clean(key)}={_clean(value)}")
        _activity.info(" | ".join(parts))
    except Exception:
        global _warned
        if not _warned:
            _app_logger.exception("Could not write to the secondary activity log")
            _warned = True
