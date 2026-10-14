"""The courses a learner can name as a UCAS destination here.

A UCAS choice carries a free-text university, a course name and a course
code, and staff typed all three. For the four choices at institutions
this platform does not run, typing is the only option there is. For the
one that *is* this university, it never should have been: the course
catalogue is sitting in the university's own database, and a hand-typed
``"Comp Sci"`` / ``"CS1"`` is a choice that will not match anything when
the learner is handed over — ``sixthform_intake`` looks the firm choice's
``course_code`` up against that same catalogue, and the import picker
pre-selects the course from it.

So this module offers the catalogue as a picker and leaves the free text
alone. Selecting fills the code and the name together, which is the point:
the two agreeing is what makes the handover land on a real programme.

What the catalogue *is* is not this module's business. Both facts it needs
— our name and our courses — are the university's to publish, and it now
publishes them from one place: ``university.application.prospectus``. This
module used to read the institution setting and the Academics course
service itself, which meant the sixth form knew the shape of two of the
university's internals and would break when either moved. It now knows one
name.

Everything here is best-effort and lazily imported. A sixth form running
without the university installed gets an empty list and its plain text
fields, exactly as before.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CourseOption:
    """One course from the university's catalogue, ready for a picker."""

    code: str
    name: str
    min_tariff: int = 0
    duration: str = ""

    @property
    def label(self) -> str:
        """``"Computer Science (CS)"`` — what a dropdown row reads as."""
        return f"{self.name} ({self.code})"


def _prospectus():
    """The university's published-facts port, or ``None`` if absent."""
    try:
        from education_system.systems.university.application import prospectus
        return prospectus
    except Exception:
        logger.debug("University prospectus unavailable", exc_info=True)
        return None


def home_institution_name() -> str | None:
    """What this platform's university calls itself, or ``None``.

    Used to fill in the ``university`` field when a learner picks one of
    our courses, so the choice does not end up with a course code from
    here and an institution left blank.
    """
    port = _prospectus()
    return port.institution_name() if port is not None else None


def home_courses() -> list[CourseOption]:
    """This university's published courses, name-sorted. Empty if it has
    none to publish, or is not installed at all."""
    port = _prospectus()
    if port is None:
        logger.info("University course catalogue unavailable — UCAS choices "
                    "will fall back to free text")
        return []
    out = [CourseOption(code=c.code, name=c.name,
                        min_tariff=c.min_tariff, duration=c.duration)
           for c in port.published_courses()]
    logger.debug("Offering %d university course(s) as UCAS destinations",
                 len(out))
    return out


def by_label(options: list[CourseOption], label: str) -> CourseOption | None:
    """Look a picked dropdown row back up.

    By exact label rather than by splitting the string on its brackets: a
    course legitimately named "Business (with Placement)" would defeat any
    attempt to parse the code back out of its own display text.
    """
    target = (label or "").strip()
    return next((o for o in options if o.label == target), None)


def by_code(options: list[CourseOption], code: str) -> CourseOption | None:
    """Find the catalogue entry for a code already on a choice, so an
    existing record opens with its dropdown pre-selected."""
    target = (code or "").strip().upper()
    if not target:
        return None
    return next((o for o in options if o.code.upper() == target), None)


def by_name(options: list[CourseOption], name: str) -> CourseOption | None:
    """Find the catalogue entry a free-text course name refers to.

    The fallback for the records that predate the picker, where somebody
    typed "Computer Science" and left the code blank. Case- and
    whitespace-insensitive, and nothing more: "Comp Sci" does not match,
    and should not — a fuzzy match that silently attaches the wrong course
    code to somebody's firm choice is worse than leaving it unset.
    """
    target = " ".join((name or "").split()).lower()
    if not target:
        return None
    return next((o for o in options
                 if " ".join(o.name.split()).lower() == target), None)


def resolve(options: list[CourseOption], *, code: str = "",
            name: str = "") -> CourseOption | None:
    """The catalogue entry a stored choice refers to, code first."""
    return by_code(options, code) or by_name(options, name)


__all__ = [
    "CourseOption",
    "home_institution_name",
    "home_courses",
    "by_label",
    "by_code",
    "by_name",
    "resolve",
]
