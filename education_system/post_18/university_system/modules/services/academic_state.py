"""Shared academic state — current term + current selection.

Every scheduling GUI used to roll its own term picker and selection
tracking. That meant Module Scheduling could be showing Autumn 2025
while the Course list next to it was still on Spring 2026, with no
way to keep them in sync. Same for "the user is now looking at
module CS101" — each window noticed independently or not at all.

This module owns two pieces of process-wide state:

* **Current term** — ``(year, semester)`` tuple, broadcast on
  ``EVENT_TERM_CHANGED``.
* **Current selection** — the module / course / exam / instructor
  the user most recently clicked on. A *soft* pointer: subscribers
  highlight the relevant row, they do **not** force a context
  switch. Broadcast on ``EVENT_SELECTION_CHANGED``.

Both are best-effort and pure in-memory — restart wipes them.
Callers read with the getters and write with the setters.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Term
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Term:
    year: int
    semester: str  # e.g. "Autumn", "Spring", "Summer"

    def label(self) -> str:
        return f"{self.semester} {self.year}"


_current_term: Term | None = None


def get_current_term() -> Term | None:
    with _lock:
        return _current_term


def set_current_term(year: int, semester: str) -> Term:
    """Update the global term and broadcast ``EVENT_TERM_CHANGED``.

    Subscribers re-filter their views; ours is the single source so
    drift between windows is impossible by construction.
    """
    global _current_term
    with _lock:
        _current_term = Term(int(year), str(semester).strip())
        term = _current_term
    _publish_term(term)
    return term


def _publish_term(term: Term) -> None:
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui._event_bus import (
            publish, EVENT_TERM_CHANGED,
        )
        publish(EVENT_TERM_CHANGED, year=term.year, semester=term.semester,
                label=term.label())
    except Exception as exc:
        logger.debug("term bus publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Selection:
    module_code: str | None = None
    course_code: str | None = None
    exam_id: int | None = None
    instructor_id: int | None = None
    student_id: str | None = None
    source: str | None = None   # which GUI raised the selection

    def to_payload(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "")}


_current_selection: Selection | None = None


def get_current_selection() -> Selection | None:
    with _lock:
        return _current_selection


def set_current_selection(**fields: Any) -> Selection:
    """Update the soft selection pointer and broadcast.

    ``fields`` accepts the same keys as ``Selection``. Pass the bits
    you have; everything else stays None. The broadcast carries
    *only* the keys you set so subscribers can tell what changed.
    """
    global _current_selection
    valid = {"module_code", "course_code", "exam_id",
             "instructor_id", "student_id", "source"}
    payload = {k: v for k, v in fields.items() if k in valid}
    with _lock:
        _current_selection = Selection(**payload)
        sel = _current_selection
    _publish_selection(sel)
    return sel


def clear_selection() -> None:
    global _current_selection
    with _lock:
        _current_selection = None
    _publish_selection(Selection())


def _publish_selection(sel: Selection) -> None:
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui._event_bus import (
            publish, EVENT_SELECTION_CHANGED,
        )
        publish(EVENT_SELECTION_CHANGED, **sel.to_payload())
    except Exception as exc:
        logger.debug("selection bus publish failed: %s", exc)


__all__ = [
    "Term", "Selection",
    "get_current_term", "set_current_term",
    "get_current_selection", "set_current_selection", "clear_selection",
]
