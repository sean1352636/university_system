"""Name-based access to a ``courses`` row.

The detail views used to read the row by position — ``course[15]`` for the
enrolment cap, ``course[16]`` for the current enrolment, and so on. That map
was written against an older column order. The live table's order is::

    id, code, name, credits, department, instructor_id, academic_year_id,
    semester_id, status, date_added, course_code, course_name, level,
    credit_hours, current_enrollment, max_enrollment, description, duration,
    course_type, ...

so index 16 is ``description``, not the current enrolment. ``Available
Spots`` therefore tried ``max_enrollment - "BSc Computer Science — ..."``,
failed its ``isinstance`` check and rendered "N/A", while the Course List
tab — which selects the same two values *by name* — showed the real
``10/120``. The same slip mislabelled most of the other fields.

``course_fields()`` resolves a row to a plain dict keyed by column name, so
neither the order nor future column additions can reintroduce this.
"""

from __future__ import annotations

#: The historic positional map, kept only for rows fetched by a caller that
#: did not set a ``row_factory``. Ordered exactly as the old code indexed it.
_LEGACY_ORDER = (
    "id", "course_code", "course_name", "description", "duration", "level",
    "department", "credit_hours", "contact_hours_per_week", "learning_outcomes",
    "assessment_methods", "required_textbooks", "course_fee", "lab_required",
    "online_available", "max_enrollment", "current_enrollment", "status",
    "course_type", "tags", "availability_periods", "created_at", "updated_at",
)

#: Column pairs where the table carries both a modern and a legacy spelling.
#: The modern one wins when populated; ``courses`` holds both for historic rows.
_ALIASES = (
    ("course_code", "code"),
    ("course_name", "name"),
    ("credit_hours", "credits"),
    ("availability_periods", "availability"),
)


def course_fields(course) -> dict:
    """Return *course* as a ``{column_name: value}`` dict.

    Accepts a ``sqlite3.Row`` (or any mapping exposing ``keys()``), which is
    what callers should pass, and falls back to the legacy positional map for
    a plain tuple so existing callers keep working.
    """
    if course is None:
        return {}

    if hasattr(course, "keys"):
        data = {k: course[k] for k in course.keys()}
    else:
        data = dict(zip(_LEGACY_ORDER, course))

    for modern, legacy in _ALIASES:
        if data.get(modern) in (None, "") and data.get(legacy) not in (None, ""):
            data[modern] = data[legacy]
    return data


def is_legacy(course) -> bool:
    """True for a short row from the pre-enhancement schema."""
    if course is None:
        return True
    if hasattr(course, "keys"):
        return len(course.keys()) < 10
    return len(course) < 10


def available_spots(data: dict):
    """Free places on the course, or ``"N/A"`` when either figure is missing.

    Both values are coerced, because SQLite will hand back a numeric column as
    a string when the row was written through a text binding — which is the
    other way this used to fall through to "N/A".
    """
    def _num(value):
        if isinstance(value, bool) or value in (None, ""):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    max_e = _num(data.get("max_enrollment"))
    cur_e = _num(data.get("current_enrollment"))
    if max_e is None or cur_e is None:
        return "N/A"
    return max(0, max_e - cur_e)


def enrolment_pair(data: dict) -> str:
    """``"current/max"`` — the same shape the Course List tab shows."""
    cur = data.get("current_enrollment")
    mx = data.get("max_enrollment")
    return f"{cur if cur not in (None, '') else 0}/{mx if mx not in (None, '') else 0}"


__all__ = ["course_fields", "is_legacy", "available_spots", "enrolment_pair"]
