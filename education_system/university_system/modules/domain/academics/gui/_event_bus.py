"""In-process pub/sub for the academic GUIs.

When one of the four management windows (Exam, Grade, Module, Course)
writes data, it ``publish``-es a typed event. Other open windows that
have ``subscribe_tk``-d to that event get a callback dispatched onto
their own Tk loop via ``widget.after_idle``, so they can refresh
without the writer caring who's listening.

Design constraints:
- Pure Python module-level state. No external dependencies, no
  threading primitives beyond a single Lock for the registry.
- Callbacks for Tk widgets are marshaled onto the widget's loop —
  publishers may run from any thread, subscribers always run on the
  widget's main thread.
- Subscriptions tied to a Tk widget are auto-revoked when the widget
  is destroyed (``<Destroy>`` binding) so closed windows don't keep
  receiving events or leak.
- Failures inside subscriber callbacks are swallowed and logged — one
  broken listener must not stop the others.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event names — keep these as module-level constants so typos surface as
# import errors instead of silently mis-routing.
# ---------------------------------------------------------------------------

EVENT_EXAM_CHANGED = "exam.changed"
EVENT_GRADE_CHANGED = "grade.changed"
EVENT_MODULE_SCHEDULE_CHANGED = "module.schedule.changed"
EVENT_COURSE_CHANGED = "course.changed"
EVENT_ENROLMENT_CHANGED = "enrolment.changed"
EVENT_ASSESSMENT_CHANGED = "assessment.changed"
EVENT_ASSIGNMENT_CHANGED = "assignment.changed"
EVENT_CALENDAR_CHANGED = "calendar.changed"

ALL_EVENTS = (
    EVENT_EXAM_CHANGED,
    EVENT_GRADE_CHANGED,
    EVENT_MODULE_SCHEDULE_CHANGED,
    EVENT_COURSE_CHANGED,
    EVENT_ENROLMENT_CHANGED,
    EVENT_ASSESSMENT_CHANGED,
    EVENT_ASSIGNMENT_CHANGED,
    EVENT_CALENDAR_CHANGED,
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_subscribers: dict[str, list[Callable[..., None]]] = {}


def subscribe(event: str, callback: Callable[..., None]) -> Callable[[], None]:
    """Subscribe a raw callback. Returns an ``unsubscribe()`` function."""
    with _lock:
        _subscribers.setdefault(event, []).append(callback)

    def _unsubscribe() -> None:
        with _lock:
            try:
                _subscribers.get(event, []).remove(callback)
            except ValueError:
                pass

    return _unsubscribe


def subscribe_tk(
    event: str,
    widget: tk.Misc,
    callback: Callable[..., None],
) -> Callable[[], None]:
    """Subscribe a Tk-bound callback.

    ``callback`` will run on the widget's main loop via
    ``widget.after_idle``. Auto-unsubscribed when the widget is
    destroyed (we bind <Destroy> with add="+", filtered to the widget
    itself so child destructions don't fire it).
    """
    def _wrapped(**payload: Any) -> None:
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            widget.after_idle(_safe_call, callback, payload)
        except tk.TclError:
            # Widget disappeared between winfo_exists and after_idle
            pass

    unsub = subscribe(event, _wrapped)

    def _on_destroy(_event: "tk.Event") -> None:
        if _event.widget is widget:
            unsub()

    try:
        widget.bind("<Destroy>", _on_destroy, add="+")
    except tk.TclError:
        # Widget already gone — drop the subscription immediately
        unsub()

    return unsub


def publish(event: str, **payload: Any) -> None:
    """Fire ``event`` to every current subscriber.

    Returns immediately. Each subscriber is called inside its own
    try/except so a broken listener can't stop the others.
    """
    with _lock:
        listeners = list(_subscribers.get(event, ()))
    if not listeners:
        return
    for cb in listeners:
        try:
            cb(**payload)
        except Exception as exc:  # noqa: BLE001 — log + continue intentional
            logger.warning(
                "event-bus subscriber for %s raised: %s", event, exc,
            )


def _safe_call(callback: Callable[..., None], payload: dict[str, Any]) -> None:
    """after_idle landing target — runs on the Tk thread."""
    try:
        callback(**payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tk subscriber raised on idle: %s", exc)


def reset_for_tests() -> None:
    """Clear all subscriptions. Test-only helper."""
    with _lock:
        _subscribers.clear()


__all__ = [
    "EVENT_EXAM_CHANGED",
    "EVENT_GRADE_CHANGED",
    "EVENT_MODULE_SCHEDULE_CHANGED",
    "EVENT_COURSE_CHANGED",
    "EVENT_ENROLMENT_CHANGED",
    "EVENT_ASSESSMENT_CHANGED",
    "EVENT_ASSIGNMENT_CHANGED",
    "EVENT_CALENDAR_CHANGED",
    "ALL_EVENTS",
    "subscribe",
    "subscribe_tk",
    "publish",
    "reset_for_tests",
]
