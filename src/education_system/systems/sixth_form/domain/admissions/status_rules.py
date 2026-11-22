"""Which applicant status changes are allowed.

Before this, ``set_status``/``update_applicant`` accepted any status from
any other, so a rejected applicant could be set to "Offer Accepted" and
converted, a finished decision could be quietly reopened, and an
enrolled applicant could be unlinked from their student record.

Rules:

* each status lists the statuses it may move to (:data:`TRANSITIONS`);
* "Enrolled" is set only by :func:`conversion.convert_to_student`
  (inside :func:`converting`), never by hand;
* a closed application (declined, rejected, withdrawn) reopens only
  through :func:`admissions.reopen_application`, which needs a reason
  and is logged (inside :func:`reopening`);
* nothing moves out of "Enrolled" — the learner is managed in the
  Student Directory from then on.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Iterator

ONLINE_UNVERIFIED = "Online - unverified"

_DECIDE = ("Offer Made", "Waitlisted", "Rejected", "Withdrawn")

#: status -> statuses it may move to.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    ONLINE_UNVERIFIED: ("Submitted", "Rejected", "Withdrawn"),
    "Submitted": ("Under Review", "Interview Scheduled") + _DECIDE,
    "Under Review": ("Interview Scheduled",) + _DECIDE,
    "Interview Scheduled": ("Interview Scheduled", "Interviewed",
                            "Under Review") + _DECIDE,
    "Interviewed": ("Interview Scheduled",) + _DECIDE,
    "Waitlisted": ("Under Review", "Offer Made", "Rejected", "Withdrawn"),
    # Results day may withdraw an offer whose conditions were not met
    # (Rejected) or make an alternative offer (Offer Made again).
    "Offer Made": ("Offer Made", "Offer Accepted", "Offer Declined",
                   "Deferred", "Waitlisted", "Rejected", "Withdrawn"),
    "Offer Accepted": ("Offer Made", "Deferred", "Rejected", "Withdrawn",
                       "Enrolled"),
    "Deferred": ("Offer Made", "Offer Accepted", "Withdrawn"),
    "Offer Declined": (),
    "Rejected": (),
    "Withdrawn": (),
    "Enrolled": (),
}

#: Closed statuses :func:`admissions.reopen_application` can reopen.
REOPENABLE: tuple[str, ...] = ("Offer Declined", "Rejected", "Withdrawn")
REOPEN_TO = "Under Review"

_converting: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "adm_converting", default=False)
_reopening: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "adm_reopening", default=False)


class TransitionError(ValueError):
    """A status change the rules do not allow."""


@contextlib.contextmanager
def converting() -> Iterator[None]:
    """Conversion is the only path to "Enrolled" and the only writer of
    ``converted_student_id``."""
    token = _converting.set(True)
    try:
        yield
    finally:
        _converting.reset(token)


@contextlib.contextmanager
def reopening() -> Iterator[None]:
    token = _reopening.set(True)
    try:
        yield
    finally:
        _reopening.reset(token)


def is_converting() -> bool:
    return _converting.get()


def allowed_next(status: str) -> tuple[str, ...]:
    """Statuses a person may choose next (excludes "Enrolled", which only
    conversion sets)."""
    return tuple(s for s in TRANSITIONS.get(status, ()) if s != "Enrolled")


def check(current: str, new: str) -> None:
    """Raise :class:`TransitionError` unless *current* → *new* is allowed."""
    if new == current:
        return
    if new == "Enrolled" and not _converting.get():
        raise TransitionError(
            "An applicant becomes Enrolled only by converting them to a "
            "student (Convert / Enrol).")
    if _reopening.get() and current in REOPENABLE and new == REOPEN_TO:
        return
    if new not in TRANSITIONS.get(current, ()):
        if current in REOPENABLE:
            raise TransitionError(
                f"The application is closed ({current}). Reopen it with a "
                "reason first.")
        if current == "Enrolled":
            raise TransitionError(
                "The applicant is already enrolled; change the learner in "
                "the Student Directory instead.")
        nxt = ", ".join(allowed_next(current)) or "none"
        raise TransitionError(
            f"Cannot move from {current!r} to {new!r}. Allowed next: {nxt}.")
