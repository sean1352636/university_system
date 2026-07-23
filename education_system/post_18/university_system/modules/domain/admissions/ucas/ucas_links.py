"""University-internal link and notes layer for UCAS applicants.

Two tables, both owned by the university (in ``student_records.db``
alongside ``admission_applications``):

* ``ucas_application_links`` — maps a sixth-form UCAS choice
  (``sf_choice_id``, the row that names *this* university) to the
  uni's own ``admission_applications`` row and, once the student is
  admitted, to a uni ``students`` row. One link per sf choice.
  Carries lightweight workflow state (``status``) and provenance
  (``linked_by`` / timestamps).
* ``ucas_admissions_notes`` — internal admissions notes tied to a
  link. These are deliberately uni-only — the sixth form never sees
  them. The public-facing offer rationale belongs in
  ``ucas_choices.offer_terms`` and ``.notes`` on the sf side; this
  table is for things like reviewer comments, interview impressions,
  document checklist progress, etc.

The link is created on demand the first time a decision is recorded
for a UCAS choice via ``ensure_link_for_choice``. Callers can also
create / attach explicitly if they want to start tracking notes
before any decision is made.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.post_18.university_system.infrastructure.database.db import (
    get_connection,
)

logger = logging.getLogger(__name__)


LINK_STATUSES: tuple[str, ...] = ("open", "withdrawn", "archived")
DEFAULT_LINK_STATUS: str = "open"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ucas_application_links (
    link_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sf_application_id    INTEGER NOT NULL,
    sf_choice_id         INTEGER NOT NULL,
    sf_student_id        TEXT NOT NULL,
    uni_application_id   INTEGER,
    uni_student_id       TEXT,
    status               TEXT NOT NULL DEFAULT 'open',
    linked_by            TEXT,
    linked_at            TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now')),
    UNIQUE(sf_choice_id)
);

CREATE INDEX IF NOT EXISTS idx_ucas_links_sf_app
    ON ucas_application_links(sf_application_id);
CREATE INDEX IF NOT EXISTS idx_ucas_links_sf_student
    ON ucas_application_links(sf_student_id);
CREATE INDEX IF NOT EXISTS idx_ucas_links_uni_app
    ON ucas_application_links(uni_application_id);
CREATE INDEX IF NOT EXISTS idx_ucas_links_status
    ON ucas_application_links(status);

CREATE TABLE IF NOT EXISTS ucas_admissions_notes (
    note_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id              INTEGER NOT NULL,
    body                 TEXT NOT NULL,
    author               TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (link_id)
        REFERENCES ucas_application_links(link_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ucas_notes_link
    ON ucas_admissions_notes(link_id);
"""


@dataclass
class UcasLink:
    link_id: int
    sf_application_id: int
    sf_choice_id: int
    sf_student_id: str
    uni_application_id: int | None
    uni_student_id: str | None
    status: str
    linked_by: str | None
    linked_at: str
    updated_at: str


@dataclass
class UcasNote:
    note_id: int
    link_id: int
    body: str
    author: str | None
    created_at: str
    updated_at: str


class UcasLinkError(Exception):
    """Raised for invalid link / notes input."""


# ── DB plumbing ────────────────────────────────────────────────────

_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    logger.debug("UCAS-links schema ready")
    _DB_READY = True


def _row_link(r) -> UcasLink:
    return UcasLink(
        link_id=r["link_id"],
        sf_application_id=r["sf_application_id"],
        sf_choice_id=r["sf_choice_id"],
        sf_student_id=r["sf_student_id"],
        uni_application_id=r["uni_application_id"],
        uni_student_id=r["uni_student_id"],
        status=r["status"],
        linked_by=r["linked_by"],
        linked_at=r["linked_at"],
        updated_at=r["updated_at"],
    )


def _row_note(r) -> UcasNote:
    return UcasNote(
        note_id=r["note_id"], link_id=r["link_id"],
        body=r["body"], author=r["author"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Link CRUD ────────────────────────────────────────────────────

def get_link_by_choice(sf_choice_id: int) -> UcasLink | None:
    init_db()
    conn = get_connection()
    try:
        r = conn.execute(
            "SELECT * FROM ucas_application_links "
            "WHERE sf_choice_id = ?",
            (sf_choice_id,),
        ).fetchone()
        return _row_link(r) if r else None
    finally:
        conn.close()


def get_link(link_id: int) -> UcasLink | None:
    init_db()
    conn = get_connection()
    try:
        r = conn.execute(
            "SELECT * FROM ucas_application_links WHERE link_id = ?",
            (link_id,),
        ).fetchone()
        return _row_link(r) if r else None
    finally:
        conn.close()


def list_links(
    *,
    sf_student_id: str | None = None,
    sf_application_id: int | None = None,
    status: str | None = None,
) -> list[UcasLink]:
    init_db()
    clauses: list[str] = []
    args: list = []
    if sf_student_id:
        clauses.append("sf_student_id = ?")
        args.append(sf_student_id)
    if sf_application_id is not None:
        clauses.append("sf_application_id = ?")
        args.append(sf_application_id)
    if status:
        if status not in LINK_STATUSES:
            raise UcasLinkError(
                f"status must be one of: {', '.join(LINK_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM ucas_application_links {where} "
           "ORDER BY linked_at DESC")
    conn = get_connection()
    try:
        return [_row_link(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def ensure_link_for_choice(
    *,
    sf_application_id: int,
    sf_choice_id: int,
    sf_student_id: str,
    linked_by: str | None = None,
) -> UcasLink:
    """Return the existing link for the given sf choice, or create
    one. Idempotent: safe to call from every workflow entry point
    that wants a link in hand.
    """
    init_db()
    existing = get_link_by_choice(sf_choice_id)
    if existing is not None:
        return existing
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO ucas_application_links
                   (sf_application_id, sf_choice_id, sf_student_id,
                    status, linked_by,
                    linked_at, updated_at)
               VALUES (?, ?, ?, 'open', ?,
                       datetime('now'), datetime('now'))""",
            (sf_application_id, sf_choice_id, sf_student_id,
             linked_by),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    out = get_link(new_id)
    assert out is not None
    logger.info(
        "Created UCAS link #%d (sf choice=%d, student=%s, by=%s)",
        new_id, sf_choice_id, sf_student_id, linked_by or "—")
    return out


def attach_uni_application(link_id: int,
                             uni_application_id: int | None) -> UcasLink:
    init_db()
    if get_link(link_id) is None:
        raise UcasLinkError(f"No link with id {link_id}")
    conn = get_connection()
    try:
        if uni_application_id is not None:
            row = conn.execute(
                "SELECT 1 FROM admission_applications "
                "WHERE application_id = ?",
                (uni_application_id,),
            ).fetchone()
            if row is None:
                raise UcasLinkError(
                    f"No admission_applications row with id "
                    f"{uni_application_id}")
        conn.execute(
            """UPDATE ucas_application_links SET
                   uni_application_id = ?,
                   updated_at = datetime('now')
               WHERE link_id = ?""",
            (uni_application_id, link_id),
        )
        conn.commit()
    finally:
        conn.close()
    out = get_link(link_id)
    assert out is not None
    logger.info(
        "Attached uni application #%s to UCAS link #%d",
        uni_application_id, link_id)
    return out


def attach_uni_student(link_id: int,
                        uni_student_id: str | None) -> UcasLink:
    init_db()
    if get_link(link_id) is None:
        raise UcasLinkError(f"No link with id {link_id}")
    conn = get_connection()
    try:
        if uni_student_id is not None:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?",
                (uni_student_id,),
            ).fetchone()
            if row is None:
                raise UcasLinkError(
                    f"No uni student with id {uni_student_id!r}")
        conn.execute(
            """UPDATE ucas_application_links SET
                   uni_student_id = ?,
                   updated_at = datetime('now')
               WHERE link_id = ?""",
            (uni_student_id, link_id),
        )
        conn.commit()
    finally:
        conn.close()
    out = get_link(link_id)
    assert out is not None
    logger.info(
        "Attached uni student %s to UCAS link #%d",
        uni_student_id, link_id)
    return out


def set_link_status(link_id: int, status: str) -> UcasLink:
    init_db()
    if status not in LINK_STATUSES:
        raise UcasLinkError(
            f"status must be one of: {', '.join(LINK_STATUSES)}")
    if get_link(link_id) is None:
        raise UcasLinkError(f"No link with id {link_id}")
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE ucas_application_links SET
                   status = ?, updated_at = datetime('now')
               WHERE link_id = ?""",
            (status, link_id),
        )
        conn.commit()
    finally:
        conn.close()
    out = get_link(link_id)
    assert out is not None
    logger.info("UCAS link #%d status -> %s", link_id, status)
    return out


# ── Note CRUD ────────────────────────────────────────────────────

def add_note(link_id: int, body: str,
              *, author: str | None = None) -> UcasNote:
    init_db()
    body = (body or "").strip()
    if not body:
        raise UcasLinkError("Note body is required")
    if get_link(link_id) is None:
        raise UcasLinkError(f"No link with id {link_id}")
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO ucas_admissions_notes
                   (link_id, body, author, created_at, updated_at)
               VALUES (?, ?, ?, datetime('now'), datetime('now'))""",
            (link_id, body, (author or "").strip() or None),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    out = get_note(new_id)
    assert out is not None
    logger.info(
        "Added internal admissions note #%d to link #%d (by %s)",
        new_id, link_id, author or "—")
    return out


def get_note(note_id: int) -> UcasNote | None:
    init_db()
    conn = get_connection()
    try:
        r = conn.execute(
            "SELECT * FROM ucas_admissions_notes WHERE note_id = ?",
            (note_id,),
        ).fetchone()
        return _row_note(r) if r else None
    finally:
        conn.close()


def list_notes(link_id: int) -> list[UcasNote]:
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM ucas_admissions_notes
               WHERE link_id = ?
               ORDER BY created_at DESC, note_id DESC""",
            (link_id,),
        ).fetchall()
        return [_row_note(r) for r in rows]
    finally:
        conn.close()


def update_note(note_id: int, body: str) -> UcasNote:
    init_db()
    body = (body or "").strip()
    if not body:
        raise UcasLinkError("Note body is required")
    if get_note(note_id) is None:
        raise UcasLinkError(f"No note with id {note_id}")
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE ucas_admissions_notes SET
                   body = ?, updated_at = datetime('now')
               WHERE note_id = ?""",
            (body, note_id),
        )
        conn.commit()
    finally:
        conn.close()
    out = get_note(note_id)
    assert out is not None
    logger.info("Updated admissions note #%d", note_id)
    return out


def delete_note(note_id: int) -> bool:
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM ucas_admissions_notes WHERE note_id = ?",
            (note_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted admissions note #%d", note_id)
            return True
        return False
    finally:
        conn.close()
