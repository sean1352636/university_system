"""Academic years: create, read, update, approve, current-year flag, delete/restore.

Split out of ``academic_year.py``, which re-exports every name here and keeps
the database/RBAC/audit state (DB_PATH, CURRENT_ACTOR, ...). Import from
``academic_year``, not from here.
"""

from __future__ import annotations

from typing import Any
import datetime as _dt

from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    _audit,
    _check_write,
    _clear_current,
    _connect,
    DEFAULT_CYCLE_WEEKS,
    DEFAULT_INSET_ALLOWANCE,
    DEFAULT_YEAR_STATUS,
    init_db,
    logger,
    MAX_CYCLE_WEEKS,
    MAX_INSET_ALLOWANCE,
    _row_year,
    UNSET,
    _Unset,
    _YEAR_NAME_RE,
    YEAR_STATUSES,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.models import (
    AcademicYear,
    _year_to_dict,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.validation import (
    _require,
    _validate_date,
    ValidationError,
)


def _validate_year_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = _require(payload.get("name"), "Name").strip()
    if not _YEAR_NAME_RE.match(name):
        raise ValidationError(
            "Name must be 2–32 chars (letters, digits, space, / . _ -)")
    out["name"] = name
    out["start_date"] = _validate_date(payload.get("start_date"),
                                          "Start date")
    out["end_date"] = _validate_date(payload.get("end_date"),
                                        "End date")
    if out["end_date"] <= out["start_date"]:
        raise ValidationError("End date must be after start date")
    status = (payload.get("status") or DEFAULT_YEAR_STATUS).strip()
    if status not in YEAR_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(YEAR_STATUSES)}")
    out["status"] = status
    out["is_current"] = bool(payload.get("is_current"))
    if out["is_current"] and out["status"] == "Archived":
        raise ValidationError(
            "A year cannot be both Archived and current.")
    out["notes"] = (payload.get("notes") or "").strip() or None
    cid = payload.get("campus_id")
    out["campus_id"] = (cid.strip() if isinstance(cid, str) and cid.strip()
                          else None)

    cw = payload.get("cycle_weeks", DEFAULT_CYCLE_WEEKS)
    if cw in (None, ""):
        cw = DEFAULT_CYCLE_WEEKS
    try:
        cw = int(cw)
    except (TypeError, ValueError):
        raise ValidationError("Cycle weeks must be a number") from None
    if not (1 <= cw <= MAX_CYCLE_WEEKS):
        raise ValidationError(
            f"Cycle weeks must be between 1 and {MAX_CYCLE_WEEKS}")
    out["cycle_weeks"] = cw

    anchor = _validate_date(payload.get("cycle_anchor"), "Cycle anchor",
                              required=False)
    if anchor is not None:
        if _dt.date.fromisoformat(anchor).weekday() != 0:
            raise ValidationError("Cycle anchor must be a Monday")
        if anchor > out["end_date"]:
            raise ValidationError(
                "Cycle anchor must not be after the year ends")
    out["cycle_anchor"] = anchor

    allow = payload.get("inset_allowance", DEFAULT_INSET_ALLOWANCE)
    if allow in (None, ""):
        allow = DEFAULT_INSET_ALLOWANCE
    try:
        allow = int(allow)
    except (TypeError, ValueError):
        raise ValidationError("INSET allowance must be a number") from None
    if not (0 <= allow <= MAX_INSET_ALLOWANCE):
        raise ValidationError(
            f"INSET allowance must be between 0 and {MAX_INSET_ALLOWANCE}")
    out["inset_allowance"] = allow
    return out


def create_year(payload: dict[str, Any]) -> AcademicYear:
    init_db()
    _check_write()
    p = _validate_year_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM academic_years "
                "WHERE name = ? AND deleted_at IS NULL",
                (p["name"],)).fetchone():
            raise ValidationError(
                f"An academic year named {p['name']!r} already exists")
        if p["is_current"]:
            _clear_current(conn, campus_id=p.get("campus_id"))
        cur = conn.execute(
            """INSERT INTO academic_years
                   (name, start_date, end_date, is_current,
                    status, notes, campus_id,
                    cycle_weeks, cycle_anchor, inset_allowance,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["name"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["status"], p["notes"],
             p.get("campus_id"), p["cycle_weeks"], p["cycle_anchor"],
             p["inset_allowance"]),
        )
        new_id = cur.lastrowid
        _audit(conn, entity="year", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_year(new_id)
    assert out is not None
    logger.info("Created academic year #%d %r (%s..%s, current=%s)",
                new_id, p["name"], p["start_date"], p["end_date"],
                p["is_current"])
    return out


def get_year(year_id: int, *,
              include_deleted: bool = False) -> AcademicYear | None:
    init_db()
    extra = "" if include_deleted else " AND deleted_at IS NULL"
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_years "
            f"WHERE year_id = ?{extra}", (year_id,)).fetchone()
        return _row_year(r) if r else None


def get_year_by_name(name: str) -> AcademicYear | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_years "
            "WHERE name = ? AND deleted_at IS NULL",
            (name.strip(),),
        ).fetchone()
        return _row_year(r) if r else None


def list_years(*, status: str | None = None,
                campus_id: Any = UNSET,
                include_deleted: bool = False) -> list[AcademicYear]:
    """List years. Omit ``campus_id`` for every campus; pass ``None``
    for the years with no campus set, or a string for one campus."""
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if status:
        if status not in YEAR_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(YEAR_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if not isinstance(campus_id, _Unset):
        clauses.append("campus_id IS ?")
        args.append(campus_id or None)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_years {where} "
           "ORDER BY start_date DESC, year_id DESC")
    with _connect() as conn:
        return [_row_year(r) for r in conn.execute(sql, args).fetchall()]


def current_year(*, campus_id: Any = UNSET) -> AcademicYear | None:
    """The current year. Omit ``campus_id`` to take whichever campus's
    year is current (warning if several are), pass ``None`` for the
    un-sited year, or a string for one campus."""
    init_db()
    args: list[Any] = []
    extra = ""
    if not isinstance(campus_id, _Unset):
        extra = " AND campus_id IS ?"
        args.append(campus_id or None)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM academic_years "
            "WHERE is_current = 1 AND deleted_at IS NULL"
            + extra + " ORDER BY campus_id IS NULL DESC, year_id ASC",
            args).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        logger.warning(
            "%d years are flagged current (campuses: %s) — returning "
            "%r. Pass campus_id= to disambiguate.",
            len(rows), ", ".join(str(r["campus_id"]) for r in rows),
            rows[0]["name"])
    return _row_year(rows[0])


def current_years() -> list[AcademicYear]:
    """Every campus's current year, one row per campus."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM academic_years "
            "WHERE is_current = 1 AND deleted_at IS NULL "
            "ORDER BY campus_id IS NULL DESC, campus_id ASC").fetchall()
    return [_row_year(r) for r in rows]


def update_year(year_id: int, payload: dict[str, Any]) -> AcademicYear:
    init_db()
    _check_write()
    existing = get_year(year_id)
    if existing is None:
        raise ValidationError(f"No academic year #{year_id}")
    merged = {
        "name":        payload.get("name", existing.name),
        "start_date":  payload.get("start_date", existing.start_date),
        "end_date":    payload.get("end_date", existing.end_date),
        "status":      payload.get("status", existing.status),
        "is_current":  payload.get("is_current", existing.is_current),
        "notes":       payload.get("notes", existing.notes),
        "campus_id":   payload.get("campus_id", existing.campus_id),
        "cycle_weeks": payload.get("cycle_weeks", existing.cycle_weeks),
        "cycle_anchor": payload.get("cycle_anchor",
                                     existing.cycle_anchor),
    }
    p = _validate_year_payload(merged)
    with _connect() as conn:
        row = conn.execute(
            "SELECT year_id FROM academic_years "
            "WHERE name = ? AND deleted_at IS NULL",
            (p["name"],)).fetchone()
        if row and row["year_id"] != year_id:
            raise ValidationError(
                f"An academic year named {p['name']!r} already exists")
        if p["is_current"]:
            _clear_current(conn, campus_id=p.get("campus_id"),
                            exclude_year_id=year_id)
        conn.execute(
            """UPDATE academic_years SET
                   name = ?, start_date = ?, end_date = ?,
                   is_current = ?, status = ?, notes = ?,
                   campus_id = ?, cycle_weeks = ?, cycle_anchor = ?,
                   updated_at = datetime('now')
               WHERE year_id = ?""",
            (p["name"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["status"], p["notes"],
             p.get("campus_id"), p["cycle_weeks"], p["cycle_anchor"],
             year_id),
        )
        _audit(conn, entity="year", entity_id=year_id,
                 action="update", old=_year_to_dict(existing), new=p)
        conn.commit()
    out = get_year(year_id)
    assert out is not None
    logger.info("Updated academic year #%d %r (current=%s, status=%s)",
                year_id, out.name, out.is_current, out.status)
    return out


def approve_year(year_id: int, *, approver: str) -> AcademicYear:
    """Stamp a year as approved (sign-off workflow). Status must be
    'Planning' or 'Active'."""
    init_db()
    _check_write()
    existing = get_year(year_id)
    if existing is None:
        raise ValidationError(f"No academic year #{year_id}")
    if existing.status == "Archived":
        raise ValidationError("Cannot approve an archived year")
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_years SET "
            "approved_at = datetime('now'), approved_by = ?, "
            "updated_at = datetime('now') WHERE year_id = ?",
            (approver, year_id))
        _audit(conn, entity="year", entity_id=year_id,
                 action="approve", new={"approved_by": approver})
        conn.commit()
    out = get_year(year_id)
    assert out is not None
    return out


def unapprove_year(year_id: int) -> AcademicYear:
    init_db()
    _check_write()
    if get_year(year_id) is None:
        raise ValidationError(f"No academic year #{year_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_years SET "
            "approved_at = NULL, approved_by = NULL, "
            "updated_at = datetime('now') WHERE year_id = ?",
            (year_id,))
        _audit(conn, entity="year", entity_id=year_id,
                 action="unapprove")
        conn.commit()
    out = get_year(year_id)
    assert out is not None
    return out


def restore_year(year_id: int) -> AcademicYear:
    init_db()
    _check_write()
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_years SET deleted_at = NULL, "
            "updated_at = datetime('now') WHERE year_id = ?",
            (year_id,))
        _audit(conn, entity="year", entity_id=year_id,
                 action="restore")
        conn.commit()
    out = get_year(year_id, include_deleted=True)
    if out is None:
        raise ValidationError(f"No academic year #{year_id}")
    return out


def set_current(year_id: int) -> AcademicYear:
    """Flag a year current for its campus. Other campuses keep theirs."""
    init_db()
    _check_write()
    existing = get_year(year_id)
    if existing is None:
        raise ValidationError(f"No academic year #{year_id}")
    if existing.status == "Archived":
        raise ValidationError(
            "An archived year cannot be the current year")
    with _connect() as conn:
        _clear_current(conn, campus_id=existing.campus_id,
                        exclude_year_id=year_id)
        conn.execute(
            "UPDATE academic_years SET is_current = 1, "
            "updated_at = datetime('now') "
            "WHERE year_id = ? AND deleted_at IS NULL",
            (year_id,))
        _audit(conn, entity="year", entity_id=year_id,
                 action="set-current",
                 old={"is_current": existing.is_current},
                 new={"is_current": True,
                       "campus_id": existing.campus_id})
        conn.commit()
    out = get_year(year_id)
    assert out is not None
    logger.info("Set current academic year → #%d %r (campus %s)",
                year_id, out.name, out.campus_id or "-")
    return out


def clear_current(*, campus_id: Any = UNSET) -> int:
    """Clear the current-year flag. Omit ``campus_id`` to clear every
    campus. Returns how many rows were cleared."""
    init_db()
    _check_write()
    with _connect() as conn:
        if isinstance(campus_id, _Unset):
            cleared = conn.execute(
                "UPDATE academic_years SET is_current = 0 "
                "WHERE deleted_at IS NULL AND is_current = 1").rowcount
        else:
            cleared = _clear_current(conn, campus_id=campus_id or None)
        _audit(conn, entity="year", entity_id=0, action="clear-current",
                 new={"campus_id": (None
                                     if isinstance(campus_id, _Unset)
                                     else campus_id),
                       "cleared": cleared})
        conn.commit()
    logger.info("Cleared current academic year (%d row(s))", cleared)
    return cleared


def delete_year(year_id: int, *, hard: bool = False) -> bool:
    """Soft-delete by default — sets ``deleted_at`` on the year and
    cascades the same to its terms/breaks. Pass ``hard=True`` to
    physically delete (the original FK cascade applies)."""
    init_db()
    _check_write()
    existing = get_year(year_id, include_deleted=True)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_years WHERE year_id = ?",
                (year_id,))
        else:
            now_sql = "datetime('now')"
            cur = conn.execute(
                f"UPDATE academic_years SET deleted_at = {now_sql}, "
                f"is_current = 0, updated_at = {now_sql} "
                f"WHERE year_id = ?", (year_id,))
            conn.execute(
                f"UPDATE academic_terms SET deleted_at = {now_sql}, "
                f"updated_at = {now_sql} "
                f"WHERE year_id = ? AND deleted_at IS NULL",
                (year_id,))
            for table in ("academic_breaks", "academic_periods",
                            "academic_year_notes"):
                conn.execute(
                    f"UPDATE {table} SET deleted_at = {now_sql}, "
                    f"updated_at = {now_sql} "
                    f"WHERE year_id = ? AND deleted_at IS NULL",
                    (year_id,))
        if cur.rowcount:
            _audit(conn, entity="year", entity_id=year_id,
                     action="hard-delete" if hard else "delete",
                     old=_year_to_dict(existing))
            conn.commit()
            logger.info(
                "%s academic year #%d (cascade: terms+breaks)",
                "Hard-deleted" if hard else "Soft-deleted", year_id)
            return True
        return False
