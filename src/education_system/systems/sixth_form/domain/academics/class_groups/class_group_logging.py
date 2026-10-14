"""Logging bridge for Sixth Form class groups.

Every class-group module logs through :mod:`logging` in the normal way,
but membership changes are the kind of thing somebody asks about months
later ("who moved this student out of 12M-2, and when?"). The sixth-form
system already has a durable answer to that: ``infrastructure.log_store``
installs a SQLite handler that mirrors every record into ``system_logs``,
with a dedicated ``student_id`` column so the GUI can filter a log view
down to one learner.

That column only populates two ways: the handler scrapes a ``Cxxxxxxx``
id out of the rendered message, or the caller passes it explicitly via
``extra={"student_id": ...}``. Scraping is fragile — it misses any
message that names the student some other way, and it picks the *first*
id out of a message that mentions two (a transfer names both the mover
and nobody else, but a swap names two learners and would file itself
under the wrong one). So class-group code goes through the helpers here,
which always pass the id explicitly.

Typical use at the top of a sibling module::

    from education_system.systems.sixth_form.domain.academics.class_groups \\
        import class_group_logging as cg_log

    logger = cg_log.get_logger(__name__)
    ...
    cg_log.student_event(
        logger, "Moved %s from #%d to #%d", student_id, src, dst,
        student_id=student_id, group_id=dst, actor=actor,
    )

Nothing here is allowed to raise. A logging call that blows up in the
middle of a membership transaction would roll back a legitimate write
for no good reason, so every helper is wrapped and degrades to silence.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

#: Root logger name for the sixth-form package. ``log_store.install()``
#: attaches its SQLite handler here by default, so any child of this
#: name is captured without further wiring.
ROOT_LOGGER_NAME = "education_system.systems.sixth_form"

_CAPTURE_ATTEMPTED: bool = False


def get_logger(name: str) -> logging.Logger:
    """Return the module logger for ``name``.

    Thin wrapper over ``logging.getLogger`` that exists so callers have
    one obvious place to reach for, and so the capture install is
    triggered the first time any class-group module is imported.
    """
    ensure_capture()
    return logging.getLogger(name)


def ensure_capture() -> bool:
    """Install the SQLite log handler if it isn't already (idempotent).

    Returns True if the durable log store is active. Never raises: if
    ``log_store`` can't be imported or its DB can't be opened, class
    groups carry on with ordinary in-memory logging.
    """
    global _CAPTURE_ATTEMPTED
    if _CAPTURE_ATTEMPTED:
        return True
    # Set the flag *before* trying, so a persistent failure is attempted
    # once per process rather than on every single log call.
    _CAPTURE_ATTEMPTED = True
    try:
        from education_system.systems.sixth_form.infrastructure import (
            log_store,
        )
        log_store.install(logger_name=ROOT_LOGGER_NAME)
        return True
    except Exception:  # pragma: no cover - defensive
        logging.getLogger(__name__).debug(
            "Durable log capture unavailable; class-group events will "
            "only go to the in-memory handlers", exc_info=True,
        )
        return False


def _extra(student_id: str | None,
           group_id: int | None,
           actor: str | None,
           **more: Any) -> dict[str, Any]:
    """Build the ``extra`` mapping for a record.

    ``student_id`` is the one field ``log_store`` promotes to its own
    column; the rest ride along for any handler that wants them (and are
    harmless to the ones that don't).
    """
    extra: dict[str, Any] = {}
    if student_id:
        extra["student_id"] = str(student_id)
    if group_id is not None:
        extra["group_id"] = int(group_id)
    if actor:
        extra["actor"] = str(actor)
    extra.update({k: v for k, v in more.items() if v is not None})
    return extra


def student_event(logger: logging.Logger,
                  msg: str,
                  *args: Any,
                  student_id: str | None = None,
                  group_id: int | None = None,
                  actor: str | None = None,
                  level: int = logging.INFO,
                  **more: Any) -> None:
    """Log a membership event, attributed to a specific student.

    The ``student_id`` keyword is what lands in ``system_logs.student_id``
    — pass it even when the id also appears in ``msg``, because that is
    the only way a message naming two learners files itself correctly.
    """
    try:
        logger.log(level, msg, *args,
                   extra=_extra(student_id, group_id, actor, **more))
    except Exception:  # pragma: no cover - logging must never escalate
        pass


def group_event(logger: logging.Logger,
                msg: str,
                *args: Any,
                group_id: int | None = None,
                actor: str | None = None,
                level: int = logging.INFO,
                **more: Any) -> None:
    """Log a group-level event with no single student attached."""
    try:
        logger.log(level, msg, *args,
                   extra=_extra(None, group_id, actor, **more))
    except Exception:  # pragma: no cover
        pass


def rejected(logger: logging.Logger,
             msg: str,
             *args: Any,
             student_id: str | None = None,
             group_id: int | None = None,
             actor: str | None = None) -> None:
    """Log a refused operation at WARNING.

    Bulk operations skip rows rather than aborting, so a rejection is
    frequently the *only* trace that a student didn't end up where
    somebody expected. It belongs in the durable trail, not just in a
    return value the caller may ignore.
    """
    student_event(logger, msg, *args, student_id=student_id,
                  group_id=group_id, actor=actor, level=logging.WARNING)


@contextmanager
def operation(logger: logging.Logger,
              name: str,
              *,
              group_id: int | None = None,
              actor: str | None = None) -> Iterator[dict[str, Any]]:
    """Bracket a multi-step operation with start/outcome log lines.

    Yields a mutable dict; anything put in it is appended to the closing
    message, so a caller can report counts it doesn't know up front::

        with operation(logger, "transfer_all", group_id=dst) as op:
            ...
            op["moved"] = n

    An exception is logged at ERROR with its traceback and re-raised —
    this only observes, it never swallows a failure.
    """
    details: dict[str, Any] = {}
    group_event(logger, "%s: start (group #%s)", name, group_id,
                group_id=group_id, actor=actor, level=logging.DEBUG)
    try:
        yield details
    except Exception:
        group_event(logger, "%s: FAILED (group #%s) %s",
                    name, group_id, details or "",
                    group_id=group_id, actor=actor, level=logging.ERROR)
        logger.debug("%s traceback", name, exc_info=True)
        raise
    else:
        group_event(logger, "%s: done (group #%s) %s",
                    name, group_id, details or "",
                    group_id=group_id, actor=actor)
