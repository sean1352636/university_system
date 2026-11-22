"""Year groups and the group-label check terms, breaks and events use.

Split out of ``academic_year.py``, which re-exports every name here and keeps
the database/RBAC/audit state (DB_PATH, CURRENT_ACTOR, ...). Import from
``academic_year``, not from here.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    _check_write,
    _connect,
    init_db,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.models import (
    YearGroup,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.validation import (
    ValidationError,
)


def _validate_group_label(year_id: int, value: Any) -> str | None:
    """Normalise an optional year-group scope.

    ``None``/blank means "the whole college". A label must match one
    of the year's ``academic_year_groups`` rows, so a typo can't
    silently create a calendar nobody sees.
    """
    if value in (None, "") or (isinstance(value, str)
                                and not value.strip()):
        return None
    label = str(value).strip()
    known = {g.label for g in list_year_groups(year_id)}
    if label not in known:
        if not known:
            raise ValidationError(
                f"No year groups defined for year #{year_id} — create "
                f"{label!r} first (e.g. Y12 / Y13)")
        raise ValidationError(
            f"Unknown year group {label!r}. Known: "
            f"{', '.join(sorted(known))}")
    return label


def get_year_group(group_id: int) -> YearGroup | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_year_groups WHERE group_id = ?",
            (group_id,)).fetchone()
        if r is None:
            return None
        return YearGroup(group_id=r["group_id"], year_id=r["year_id"],
                          label=r["label"], notes=r["notes"],
                          created_at=r["created_at"])


def list_year_groups(year_id: int) -> list[YearGroup]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM academic_year_groups "
            "WHERE year_id = ? ORDER BY label",
            (year_id,)).fetchall()
    return [YearGroup(group_id=r["group_id"], year_id=r["year_id"],
                       label=r["label"], notes=r["notes"],
                       created_at=r["created_at"]) for r in rows]


def delete_year_group(group_id: int) -> bool:
    init_db()
    _check_write()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM academic_year_groups WHERE group_id = ?",
            (group_id,))
        conn.commit()
        return cur.rowcount > 0
