"""Deferred entry (a gap year) on a UCAS choice.

A learner can apply in this cycle for a place that starts a year later.
UCAS records that as the *entry year* of the choice; the college used to
hold only the year, so "deferred" could be read off it (an entry year
later than the application's cycle) but never *said*. Nobody could tick
"this learner is taking a gap year", and a year typed one too high by
mistake was indistinguishable from a deliberate deferral.

This module adds the explicit flag — a ``deferred_entry`` column on
``ucas_choices``, added lazily with a guarded ``ALTER`` so the UCAS data
layer itself is untouched — and keeps it consistent with the year:

* a choice flagged deferred must carry an entry year later than its
  application's cycle (:func:`validate`), so the flag and the derived
  reading always agree;
* :func:`is_deferred` answers ``True`` when the flag is set *or* the year
  says so, so a choice recorded before the flag existed still reads
  correctly — and so does every other reader that derives it from the year
  (the cross-system adapter does).

The university handover carries the answer (``confirmed_destination``),
the eligibility gate treats it as an advisory "not this year's arrival"
rather than a blocker, and the university records the deferred entry
year on the application instead of converting it this year.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_UCAS_DB

COLUMN = "deferred_entry"


class ValidationError(ValueError):
    """A deferral that contradicts the choice's entry year."""


def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_READY = False


def init_db() -> None:
    """Add ``ucas_choices.deferred_entry`` if this database lacks it."""
    global _READY
    if _READY:
        return
    from education_system.systems.sixth_form.domain.progression.university import (
        ucas as _ucas,
    )
    _ucas.init_db()
    with _connect() as conn:
        have = {r["name"] for r in conn.execute(
            "PRAGMA table_info(ucas_choices)")}
        if COLUMN not in have:
            conn.execute(
                "ALTER TABLE ucas_choices ADD COLUMN deferred_entry "
                "INTEGER NOT NULL DEFAULT 0")
            conn.commit()
    _READY = True


def _year(value: Any) -> int | None:
    try:
        text = str(value).strip() if value is not None else ""
        return int(text) if text else None
    except (TypeError, ValueError):
        return None


def validate(deferred: bool, entry_year: Any, cycle_year: Any) -> None:
    """Refuse a deferral the entry year does not support.

    A gap year means starting *after* the cycle the learner applied in, so
    a deferred choice needs an entry year and it must be later than the
    cycle. Raises :class:`ValidationError` with a sentence a member of
    staff can act on.
    """
    if not deferred:
        return
    entry = _year(entry_year)
    cycle = _year(cycle_year)
    if entry is None:
        raise ValidationError(
            "A deferred (gap year) choice needs an entry year.")
    if cycle is not None and entry <= cycle:
        raise ValidationError(
            f"A deferred choice starts after the {cycle} cycle — set the "
            f"entry year to {cycle + 1} or later, or untick deferred entry.")


def flag_for(choice_id: int) -> bool:
    """The stored flag alone (``False`` for an unknown choice)."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT deferred_entry FROM ucas_choices WHERE choice_id = ?",
            (int(choice_id),)).fetchone()
    return bool(row and row["deferred_entry"])


def flags_for(choice_ids) -> dict[int, bool]:
    """``{choice_id: flag}`` for many choices in one query."""
    ids = [int(c) for c in choice_ids if c is not None]
    if not ids:
        return {}
    init_db()
    out: dict[int, bool] = {}
    with _connect() as conn:
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            # db-audit: ignore[DBW001] - join of placeholders
            for row in conn.execute(
                    f"SELECT choice_id, deferred_entry FROM ucas_choices "
                    f"WHERE choice_id IN ({marks})", chunk):  # nosec B608
                out[int(row["choice_id"])] = bool(row["deferred_entry"])
    return out


def is_deferred(choice: Any, *, cycle_year: Any = None,
                flag: bool | None = None) -> bool:
    """Is this choice a deferred entry?

    ``choice`` is a UCAS ``Choice`` or a dict with ``choice_id`` and
    ``entry_year``. True when the stored flag is set, or when the entry
    year is later than ``cycle_year`` — the reading every choice recorded
    before the flag existed depends on.
    """
    get = (choice.get if isinstance(choice, dict)
           else lambda k, d=None: getattr(choice, k, d))
    if flag is None:
        choice_id = get("choice_id")
        try:
            flag = flag_for(choice_id) if choice_id else False
        except Exception:
            logger.exception("Could not read the deferral flag for choice %s",
                             choice_id)
            flag = False
    if flag:
        return True
    entry = _year(get("entry_year"))
    cycle = _year(cycle_year)
    return bool(entry and cycle and entry > cycle)


def set_deferred(choice_id: int, deferred: bool, *,
                 actor: str | None = None) -> bool:
    """Record (or clear) the flag on one choice. Returns the stored value.

    Checks it against the choice's own entry year and application cycle,
    so a caller cannot flag a choice the year contradicts.
    """
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """SELECT c.choice_id, c.entry_year, a.cycle_year
                 FROM ucas_choices c
                 JOIN ucas_applications a
                   ON a.application_id = c.application_id
                WHERE c.choice_id = ?""", (int(choice_id),)).fetchone()
        if row is None:
            raise ValidationError(f"No UCAS choice #{choice_id}")
        validate(deferred, row["entry_year"], row["cycle_year"])
        conn.execute(
            "UPDATE ucas_choices SET deferred_entry = ?, "
            "updated_at = datetime('now') WHERE choice_id = ?",
            (1 if deferred else 0, int(choice_id)))
        conn.commit()
    logger.info("UCAS choice #%s deferred entry %s%s", choice_id,
                "set" if deferred else "cleared",
                f" by {actor}" if actor else "")
    return bool(deferred)


def label(choice: Any, *, cycle_year: Any = None,
          flag: bool | None = None) -> str:
    """"Deferred to 2028" for a deferred choice, else ""."""
    if not is_deferred(choice, cycle_year=cycle_year, flag=flag):
        return ""
    get = (choice.get if isinstance(choice, dict)
           else lambda k, d=None: getattr(choice, k, d))
    year = _year(get("entry_year"))
    return f"Deferred to {year}" if year else "Deferred entry"


__all__ = [
    "COLUMN", "ValidationError", "init_db", "validate", "flag_for",
    "flags_for", "is_deferred", "set_deferred", "label",
]
