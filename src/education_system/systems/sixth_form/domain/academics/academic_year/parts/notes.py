"""Year notes: add, read, update, delete/restore.

Split out of ``academic_year.py``, which re-exports every name here and keeps
the database/RBAC/audit state (DB_PATH, CURRENT_ACTOR, ...). Import from
``academic_year``, not from here.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    _audit,
    _check_write,
    _connect,
    init_db,
    NOTE_CATEGORIES,
    _row_note,
    _validate_note_payload,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.models import (
    _note_to_dict,
    YearNote,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.validation import (
    ValidationError,
)


def add_note(payload: dict[str, Any]) -> YearNote:
    init_db()
    _check_write()
    p = _validate_note_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO academic_year_notes
                   (year_id, category, title, body, author, pinned)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (p["year_id"], p["category"], p["title"], p["body"],
             p["author"], 1 if p["pinned"] else 0))
        new_id = cur.lastrowid
        _audit(conn, entity="note", entity_id=new_id,
                 action="create", new=p)
        conn.commit()
    out = get_note(new_id)
    assert out is not None
    return out


def get_note(note_id: int, *,
              include_deleted: bool = False) -> YearNote | None:
    init_db()
    extra = "" if include_deleted else " AND deleted_at IS NULL"
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_year_notes "
            f"WHERE note_id = ?{extra}", (note_id,)).fetchone()
        return _row_note(r) if r else None


def list_notes(*, year_id: int | None = None,
                category: str | None = None,
                pinned_only: bool = False,
                include_deleted: bool = False) -> list[YearNote]:
    init_db()
    clauses, args = [], []
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if year_id is not None:
        clauses.append("year_id = ?")
        args.append(year_id)
    if category is not None:
        if category not in NOTE_CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(NOTE_CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if pinned_only:
        clauses.append("pinned = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM academic_year_notes {where} "
           "ORDER BY pinned DESC, note_id DESC")
    with _connect() as conn:
        return [_row_note(r) for r in conn.execute(sql, args).fetchall()]


def update_note(note_id: int, payload: dict[str, Any]) -> YearNote:
    init_db()
    _check_write()
    existing = get_note(note_id)
    if existing is None:
        raise ValidationError(f"No note #{note_id}")
    current = _note_to_dict(existing)
    merged = {k: payload.get(k, current[k]) for k in current}
    merged["year_id"] = existing.year_id
    p = _validate_note_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE academic_year_notes SET
                   category = ?, title = ?, body = ?, author = ?,
                   pinned = ?, updated_at = datetime('now')
               WHERE note_id = ?""",
            (p["category"], p["title"], p["body"], p["author"],
             1 if p["pinned"] else 0, note_id))
        _audit(conn, entity="note", entity_id=note_id,
                 action="update", old=current, new=p)
        conn.commit()
    out = get_note(note_id)
    assert out is not None
    return out


def delete_note(note_id: int, *, hard: bool = False) -> bool:
    init_db()
    _check_write()
    existing = get_note(note_id, include_deleted=True)
    if existing is None:
        return False
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM academic_year_notes WHERE note_id = ?",
                (note_id,))
        else:
            cur = conn.execute(
                "UPDATE academic_year_notes SET "
                "deleted_at = datetime('now'), "
                "updated_at = datetime('now') WHERE note_id = ?",
                (note_id,))
        if cur.rowcount:
            _audit(conn, entity="note", entity_id=note_id,
                     action="hard-delete" if hard else "delete",
                     old=_note_to_dict(existing))
            conn.commit()
            return True
        return False


def restore_note(note_id: int) -> YearNote:
    init_db()
    _check_write()
    with _connect() as conn:
        conn.execute(
            "UPDATE academic_year_notes SET deleted_at = NULL, "
            "updated_at = datetime('now') WHERE note_id = ?",
            (note_id,))
        _audit(conn, entity="note", entity_id=note_id, action="restore")
        conn.commit()
    out = get_note(note_id, include_deleted=True)
    if out is None:
        raise ValidationError(f"No note #{note_id}")
    return out
