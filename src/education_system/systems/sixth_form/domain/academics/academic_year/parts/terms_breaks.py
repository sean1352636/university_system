"""Terms and breaks (create, read, update, delete/restore) and INSET-day allowance.

Split out of ``academic_year.py``, which re-exports every name here and keeps
the database/RBAC/audit state (DB_PATH, CURRENT_ACTOR, ...). Import from
``academic_year``, not from here.
"""

from __future__ import annotations

from typing import Any
import datetime as _dt

from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    _audit,
    BREAK_AM_PM,
    BREAK_TYPES,
    _check_write,
    _connect,
    DEFAULT_BREAK_AM_PM,
    DEFAULT_BREAK_TYPE,
    DEFAULT_TERM_KIND,
    init_db,
    logger,
    NON_TEACHING_KINDS,
    _row_break,
    _row_term,
    TERM_KINDS,
    TERM_NAMES,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.models import (
    Break,
    _break_to_dict,
    InsetStatus,
    Term,
    _term_to_dict,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.validation import (
    _require,
    _validate_date,
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.years import (
    get_year,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.year_groups import (
    _validate_group_label,
)


def _assert_no_term_overlap(year_id: int, kind: str,
                             group_label: str | None,
                             start: str, end: str,
                             *, exclude_term_id: int | None = None
                             ) -> None:
    """Terms of the same kind and the same group scope must not
    overlap. Different kinds may (a Mock-Exam Week sits inside a
    Term), and so may different year groups (Y13 study leave runs
    while Y12 is still taught).
    """
    for t in list_terms(year_id=year_id, kind=kind):
        if exclude_term_id is not None and t.term_id == exclude_term_id:
            continue
        if t.group_label != group_label:
            continue
        if t.start_date <= end and start <= t.end_date:
            raise ValidationError(
                f"Overlaps existing {kind.lower()} {t.name!r} "
                f"({t.start_date} → {t.end_date})")


def _validate_term_payload(payload: dict[str, Any], *,
                             term_id: int | None = None
                             ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    year_id = payload.get("year_id")
    if year_id in (None, ""):
        raise ValidationError("Year is required")
    try:
        out["year_id"] = int(year_id)
    except (TypeError, ValueError):
        raise ValidationError("Year id must be a number") from None
    year = get_year(out["year_id"])
    if year is None:
        raise ValidationError(f"No academic year #{out['year_id']}")

    name = _require(payload.get("name"), "Term name").strip()
    if name not in TERM_NAMES:
        # Accept custom names too — schools differ — but enforce length.
        if not (1 <= len(name) <= 32):
            raise ValidationError("Term name must be 1–32 chars")
    out["name"] = name
    kind = (payload.get("kind") or DEFAULT_TERM_KIND).strip()
    if kind not in TERM_KINDS:
        raise ValidationError(
            f"Term kind must be one of: {', '.join(TERM_KINDS)}")
    out["kind"] = kind
    # Study leave is on the calendar but isn't taught. Callers can
    # override either way; unset follows the kind.
    teaching = payload.get("is_teaching")
    out["is_teaching"] = (kind not in NON_TEACHING_KINDS
                          if teaching is None else bool(teaching))

    out["start_date"] = _validate_date(payload.get("start_date"),
                                          "Start date")
    out["end_date"] = _validate_date(payload.get("end_date"),
                                        "End date")
    if out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")
    if (out["start_date"] < year.start_date
            or out["end_date"] > year.end_date):
        raise ValidationError(
            f"Term must lie within the year "
            f"({year.start_date} → {year.end_date})")
    out["group_label"] = _validate_group_label(
        out["year_id"], payload.get("group_label"))
    _assert_no_term_overlap(
        out["year_id"], out["kind"], out["group_label"],
        out["start_date"], out["end_date"], exclude_term_id=term_id)
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


def _validate_break_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    year_id = payload.get("year_id")
    if year_id in (None, ""):
        raise ValidationError("Year is required")
    try:
        out["year_id"] = int(year_id)
    except (TypeError, ValueError):
        raise ValidationError("Year id must be a number") from None
    year = get_year(out["year_id"])
    if year is None:
        raise ValidationError(f"No academic year #{out['year_id']}")

    out["name"] = _require(payload.get("name"), "Name").strip()

    out["start_date"] = _validate_date(payload.get("start_date"),
                                          "Start date")
    out["end_date"] = _validate_date(payload.get("end_date"),
                                        "End date")
    if out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")
    if (out["start_date"] < year.start_date
            or out["end_date"] > year.end_date):
        raise ValidationError(
            f"Break must lie within the year "
            f"({year.start_date} → {year.end_date})")

    btype = (payload.get("type") or DEFAULT_BREAK_TYPE).strip()
    if btype not in BREAK_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(BREAK_TYPES)}")
    out["type"] = btype
    am_pm = (payload.get("am_pm") or DEFAULT_BREAK_AM_PM).strip().upper()
    if am_pm not in BREAK_AM_PM:
        raise ValidationError(
            f"am_pm must be one of: {', '.join(BREAK_AM_PM)}")
    out["am_pm"] = am_pm
    out["group_label"] = _validate_group_label(
        out["year_id"], payload.get("group_label"))
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


# ── Term CRUD ─────────────────────────────────────────────────────

def create_term(payload: dict[str, Any]) -> Term:
    init_db()
    _check_write()
    p = _validate_term_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM academic_terms "
                "WHERE year_id = ? AND name = ? AND deleted_at IS NULL",
                (p["year_id"], p["name"])).fetchone():
            raise ValidationError(
                f"Term {p['name']!r} already exists for this year")
        cur = conn.execute(
            """INSERT INTO academic_terms
                   (year_id, name, start_date, end_date, notes, kind,
                    group_label, is_teaching, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["year_id"], p["name"], p["start_date"], p["end_date"],
             p["notes"], p["kind"], p["group_label"],
             1 if p["is_teaching"] else 0),
        )
        new_id = cur.lastrowid
        _audit(conn, entity="term", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_term(new_id)
    assert out is not None
    logger.info("Created term #%d %r in year #%d", new_id, p["name"],
                p["year_id"])
    return out


def get_term(term_id: int, *,
              include_deleted: bool = False) -> Term | None:
    init_db()
    extra = "" if include_deleted else " AND deleted_at IS NULL"
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_terms "
            f"WHERE term_id = ?{extra}", (term_id,)).fetchone()
        return _row_term(r) if r else None


def list_terms(*, year_id: int | None = None,
                kind: str | None = None,
                group_label: str | None = None,
                include_shared: bool = True,
                include_deleted: bool = False) -> list[Term]:
    """List terms. ``group_label`` narrows to one year group; with
    ``include_shared`` (the default) college-wide terms come back too.
    """
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if group_label is not None:
        if include_shared:
            clauses.append("(group_label IS NULL OR group_label = ?)")
        else:
            clauses.append("group_label = ?")
        args.append(group_label)
    if kind is not None:
        if kind not in TERM_KINDS:
            raise ValidationError(
                f"Term kind must be one of: {', '.join(TERM_KINDS)}")
        clauses.append("kind = ?")
        args.append(kind)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_terms {where} "
           "ORDER BY start_date ASC, term_id ASC")
    with _connect() as conn:
        return [_row_term(r) for r in conn.execute(sql, args).fetchall()]


def update_term(term_id: int, payload: dict[str, Any]) -> Term:
    init_db()
    _check_write()
    existing = get_term(term_id)
    if existing is None:
        raise ValidationError(f"No term #{term_id}")
    merged = {
        "year_id":    existing.year_id,
        "name":       payload.get("name", existing.name),
        "start_date": payload.get("start_date", existing.start_date),
        "end_date":   payload.get("end_date", existing.end_date),
        "kind":       payload.get("kind", existing.kind),
        "notes":      payload.get("notes", existing.notes),
        "group_label": payload.get("group_label", existing.group_label),
        "is_teaching": payload.get("is_teaching", existing.is_teaching),
    }
    p = _validate_term_payload(merged, term_id=term_id)
    with _connect() as conn:
        row = conn.execute(
            "SELECT term_id FROM academic_terms "
            "WHERE year_id = ? AND name = ? AND deleted_at IS NULL",
            (p["year_id"], p["name"])).fetchone()
        if row and row["term_id"] != term_id:
            raise ValidationError(
                f"Term {p['name']!r} already exists for this year")
        conn.execute(
            """UPDATE academic_terms SET
                   name = ?, start_date = ?, end_date = ?,
                   kind = ?, notes = ?, group_label = ?,
                   is_teaching = ?, updated_at = datetime('now')
               WHERE term_id = ?""",
            (p["name"], p["start_date"], p["end_date"], p["kind"],
             p["notes"], p["group_label"],
             1 if p["is_teaching"] else 0, term_id),
        )
        _audit(conn, entity="term", entity_id=term_id,
                 action="update", old=_term_to_dict(existing), new=p)
        conn.commit()
    out = get_term(term_id)
    assert out is not None
    logger.info("Updated term #%d %r", term_id, out.name)
    return out


def delete_term(term_id: int, *, hard: bool = False) -> bool:
    init_db()
    _check_write()
    existing = get_term(term_id, include_deleted=True)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_terms WHERE term_id = ?",
                (term_id,))
        else:
            cur = conn.execute(
                "UPDATE academic_terms SET "
                "deleted_at = datetime('now'), "
                "updated_at = datetime('now') WHERE term_id = ?",
                (term_id,))
        if cur.rowcount:
            _audit(conn, entity="term", entity_id=term_id,
                     action="hard-delete" if hard else "delete",
                     old=_term_to_dict(existing))
            conn.commit()
            logger.info("%s term #%d",
                          "Hard-deleted" if hard else "Soft-deleted",
                          term_id)
            return True
        return False


def restore_term(term_id: int) -> Term:
    init_db()
    _check_write()
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_terms SET deleted_at = NULL, "
            "updated_at = datetime('now') WHERE term_id = ?",
            (term_id,))
        _audit(conn, entity="term", entity_id=term_id,
                 action="restore")
        conn.commit()
    out = get_term(term_id, include_deleted=True)
    if out is None:
        raise ValidationError(f"No term #{term_id}")
    return out


def get_break(break_id: int, *,
               include_deleted: bool = False) -> Break | None:
    init_db()
    extra = "" if include_deleted else " AND deleted_at IS NULL"
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_breaks "
            f"WHERE break_id = ?{extra}", (break_id,)).fetchone()
        return _row_break(r) if r else None


def list_breaks(*, year_id: int | None = None,
                 type: str | None = None,
                 am_pm: str | None = None,
                 group_label: str | None = None,
                 include_shared: bool = True,
                 include_deleted: bool = False) -> list[Break]:
    """List breaks. ``group_label`` narrows to one year group; with
    ``include_shared`` (the default) college-wide breaks come back too.
    """
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if group_label is not None:
        if include_shared:
            clauses.append("(group_label IS NULL OR group_label = ?)")
        else:
            clauses.append("group_label = ?")
        args.append(group_label)
    if type:
        if type not in BREAK_TYPES:
            raise ValidationError(
                f"Type must be one of: {', '.join(BREAK_TYPES)}")
        clauses.append("type = ?")
        args.append(type)
    if am_pm:
        if am_pm not in BREAK_AM_PM:
            raise ValidationError(
                f"am_pm must be one of: {', '.join(BREAK_AM_PM)}")
        clauses.append("am_pm = ?")
        args.append(am_pm)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_breaks {where} "
           "ORDER BY start_date ASC, break_id ASC")
    with _connect() as conn:
        return [_row_break(r) for r in conn.execute(sql, args).fetchall()]


def update_break(break_id: int, payload: dict[str, Any]) -> Break:
    init_db()
    _check_write()
    existing = get_break(break_id)
    if existing is None:
        raise ValidationError(f"No break #{break_id}")
    merged = {
        "year_id":    existing.year_id,
        "name":       payload.get("name", existing.name),
        "start_date": payload.get("start_date", existing.start_date),
        "end_date":   payload.get("end_date", existing.end_date),
        "type":       payload.get("type", existing.type),
        "am_pm":      payload.get("am_pm", existing.am_pm),
        "notes":      payload.get("notes", existing.notes),
        "group_label": payload.get("group_label", existing.group_label),
    }
    p = _validate_break_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE academic_breaks SET
                   name = ?, start_date = ?, end_date = ?,
                   type = ?, am_pm = ?, notes = ?, group_label = ?,
                   updated_at = datetime('now')
               WHERE break_id = ?""",
            (p["name"], p["start_date"], p["end_date"],
             p["type"], p["am_pm"], p["notes"], p["group_label"],
             break_id),
        )
        _audit(conn, entity="break", entity_id=break_id,
                 action="update", old=_break_to_dict(existing), new=p)
        conn.commit()
    out = get_break(break_id)
    assert out is not None
    logger.info("Updated break #%d %r", break_id, out.name)
    return out


def delete_break(break_id: int, *, hard: bool = False) -> bool:
    init_db()
    _check_write()
    existing = get_break(break_id, include_deleted=True)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_breaks WHERE break_id = ?",
                (break_id,))
        else:
            cur = conn.execute(
                "UPDATE academic_breaks SET "
                "deleted_at = datetime('now'), "
                "updated_at = datetime('now') WHERE break_id = ?",
                (break_id,))
        if cur.rowcount:
            _audit(conn, entity="break", entity_id=break_id,
                     action="hard-delete" if hard else "delete",
                     old=_break_to_dict(existing))
            conn.commit()
            return True
        return False


def restore_break(break_id: int) -> Break:
    init_db()
    _check_write()
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_breaks SET deleted_at = NULL, "
            "updated_at = datetime('now') WHERE break_id = ?",
            (break_id,))
        _audit(conn, entity="break", entity_id=break_id,
                 action="restore")
        conn.commit()
    out = get_break(break_id, include_deleted=True)
    if out is None:
        raise ValidationError(f"No break #{break_id}")
    return out


# ── INSET allowance ───────────────────────────────────────────────

def inset_days_planned(year_id: int, *,
                        group_label: str | None = None) -> float:
    """How many INSET days are on the calendar, counting an AM/PM
    closure as half a day and ignoring any that land at a weekend."""
    total = 0.0
    for b in list_breaks(year_id=year_id, type="INSET",
                           group_label=group_label):
        if group_label is None and b.group_label is not None:
            continue
        try:
            cur = _dt.date.fromisoformat(b.start_date)
            end = _dt.date.fromisoformat(b.end_date or b.start_date)
        except ValueError:
            continue
        one = _dt.timedelta(days=1)
        while cur <= end:
            if cur.weekday() < 5:
                total += 0.5 if b.am_pm in ("AM", "PM") else 1.0
            cur += one
    return total


def inset_status(year_id: int, *,
                  group_label: str | None = None) -> InsetStatus:
    """Compare planned INSET against the year's allowance.

    Sixth forms get a fixed number of staff-development days a year
    (five in England). Scheduling a sixth by accident is a payroll
    and parent-communication problem, and leaving one unbooked in
    July is worse — so surface both.
    """
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    planned = inset_days_planned(year_id, group_label=group_label)
    return InsetStatus(
        year_id=year_id,
        allowance=year.inset_allowance,
        planned=planned,
        remaining=year.inset_allowance - planned,
    )
