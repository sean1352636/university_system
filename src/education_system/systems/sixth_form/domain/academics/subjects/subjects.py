"""Subjects & qualifications offered by the Sixth Form.

This module is the source of truth for which subjects students can pick
and which subjects courses can be tagged with. On first run the table
is seeded from `students.A_LEVEL_SUBJECTS` so existing students /
courses keep validating; after that, staff manage the catalogue
through the GUI / CLI.

Soft-delete is supported: marking a subject inactive removes it from
new student/course dropdowns but leaves existing references alone.
Hard delete is only allowed when the subject is not referenced by any
student or course — see `is_in_use`.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_SUBJECTS_DB

QUALIFICATIONS: tuple[str, ...] = (
    "A-Level",
    "AS-Level",
    "BTEC",
    "T-Level",
    "Extended Project Qualification",
    # Added with learning aims: a 16-19 study programme also carries
    # GCSE resits, Core Maths and Functional Skills.
    "GCSE",
    "Core Maths",
    "Functional Skills",
)

#: Catalogue qualification label -> grade_scales qualification type.
#: "BTEC" is ambiguous in size; it maps to the single award and a
#: subject can set ``qualification_type`` explicitly for double/triple.
QUALIFICATION_TYPE_FOR_LABEL: dict[str, str] = {
    "A-Level": "A Level",
    "AS-Level": "AS Level",
    "BTEC": "BTEC Extended Certificate",
    "T-Level": "T Level",
    "Extended Project Qualification": "EPQ",
    "GCSE": "GCSE",
    "Core Maths": "Core Maths",
    "Functional Skills": "Functional Skills",
}

# One awarding-body list for the whole system, owned by the exams
# office (exams_office/boards.py); re-exported here for existing callers.
from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (  # noqa: E402
    EXAM_BOARDS,
    normalise_board,
)

DEFAULT_QUALIFICATION: str = "A-Level"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    subject_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    qualification TEXT NOT NULL DEFAULT 'A-Level',
    exam_board    TEXT,
    description   TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_subjects_active        ON subjects(is_active);
CREATE INDEX IF NOT EXISTS idx_subjects_qualification ON subjects(qualification);
"""


@dataclass
class Subject:
    subject_id: int
    name: str
    qualification: str
    exam_board: str | None
    description: str | None
    is_active: bool
    created_at: str
    #: Explicit grade_scales qualification type; None = derive from
    #: ``qualification`` via QUALIFICATION_TYPE_FOR_LABEL.
    qualification_type: str | None = None
    #: Default planned (guided learning) hours per year for an aim.
    guided_learning_hours: float | None = None
    #: Default aim / QAN code for aims in this subject.
    aim_code: str | None = None

    @property
    def effective_qualification_type(self) -> str:
        return (self.qualification_type
                or QUALIFICATION_TYPE_FOR_LABEL.get(self.qualification)
                or "A Level")


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _row(r: sqlite3.Row) -> Subject:
    return Subject(
        subject_id=r["subject_id"],
        name=r["name"],
        qualification=r["qualification"],
        exam_board=r["exam_board"],
        description=r["description"],
        is_active=bool(r["is_active"]),
        created_at=r["created_at"],
        qualification_type=(r["qualification_type"]
                            if "qualification_type" in r.keys() else None),
        guided_learning_hours=(r["guided_learning_hours"]
                               if "guided_learning_hours" in r.keys() else None),
        aim_code=(r["aim_code"] if "aim_code" in r.keys() else None),
    )


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    """Create the table and seed it from the legacy constant list once."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(subjects)")}
        for col, ddl in (("qualification_type",    "TEXT"),
                         ("guided_learning_hours", "REAL"),
                         ("aim_code",              "TEXT")):
            if col not in cols:
                conn.execute(f"ALTER TABLE subjects ADD COLUMN {col} {ddl}")
                logger.info("Subjects: added column %s", col)
        # First-run seed: only fires when the table is empty so we don't
        # re-add subjects the admin has deliberately deleted.
        row = conn.execute("SELECT COUNT(*) AS n FROM subjects").fetchone()
        if row["n"] == 0:
            # Import lazily to avoid a circular dependency at module load.
            from education_system.systems.sixth_form.domain.learners.students.students import (
                A_LEVEL_SUBJECTS as _SEED,
            )
            conn.executemany(
                "INSERT OR IGNORE INTO subjects (name, qualification) VALUES (?, ?)",
                [(name, DEFAULT_QUALIFICATION) for name in _SEED],
            )
            logger.info("Seeded %d default subjects", len(_SEED))
        conn.commit()
    logger.debug("Subjects schema ready at %s", DB_PATH)

    _DB_READY = True


# ── Validation ──────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid subject-form input."""


def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(data.get("name"), "Subject name")
    qual = (data.get("qualification") or DEFAULT_QUALIFICATION).strip()
    if qual not in QUALIFICATIONS:
        raise ValidationError(
            f"Qualification must be one of: {', '.join(QUALIFICATIONS)}")
    out["qualification"] = qual
    raw_board = (data.get("exam_board") or "").strip()
    board = normalise_board(raw_board) if raw_board else None
    if raw_board and board is None:
        raise ValidationError(
            f"Exam board must be blank or one of: {', '.join(EXAM_BOARDS)}")
    out["exam_board"] = board
    out["description"] = (data.get("description") or "").strip() or None
    is_active = data.get("is_active", True)
    out["is_active"] = 1 if bool(is_active) else 0

    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales as _gs,
    )
    qtype_raw = (data.get("qualification_type") or "").strip()
    if qtype_raw:
        qtype = _gs.canonical_type(qtype_raw)
        if qtype is None:
            raise ValidationError(
                "Qualification type must be blank or one of: "
                + ", ".join(_gs.QUALIFICATION_TYPES))
        out["qualification_type"] = qtype
    else:
        out["qualification_type"] = None
    glh = data.get("guided_learning_hours")
    if glh in (None, "") or (isinstance(glh, str) and not glh.strip()):
        out["guided_learning_hours"] = None
    else:
        try:
            g = float(glh)
        except (TypeError, ValueError):
            raise ValidationError("Guided learning hours must be a number") from None
        if g < 0 or g > 2000:
            raise ValidationError("Guided learning hours must be 0-2000")
        out["guided_learning_hours"] = round(g, 1)
    out["aim_code"] = ((data.get("aim_code") or "").strip().upper()
                       .replace(" ", "") or None)
    return out


# ── Read API used by other modules ──────────────────────────────────

def get_active_names() -> list[str]:
    """Names of active subjects, alphabetical — used by student/course
    forms to populate Combobox values."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT name FROM subjects WHERE is_active = 1 ORDER BY name"
        ).fetchall()
        return [r["name"] for r in rows]


def qualification_type_for_subject(name: str) -> str | None:
    """grade_scales qualification type for a catalogue subject, or None."""
    s = get_subject_by_name(name)
    return s.effective_qualification_type if s else None


def is_valid_subject(name: str) -> bool:
    """True if ``name`` exists in the table, regardless of active flag.

    We deliberately accept inactive subjects on validation so that
    *editing* an existing student/course doesn't fail merely because
    their currently-set subject was deactivated after the fact.
    """
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM subjects WHERE name = ?", (name.strip(),)
        ).fetchone()
        return row is not None


def is_in_use(name: str) -> dict[str, int]:
    """Return how many students / courses reference this subject."""
    init_db()
    name = name.strip()
    counts = {"students": 0, "courses": 0}
    with _connect() as conn:
        # Students reference subjects via three columns.
        try:
            counts["students"] = conn.execute(
                """SELECT COUNT(*) AS n FROM students
                   WHERE subject_1 = ? OR subject_2 = ? OR subject_3 = ?""",
                (name, name, name),
            ).fetchone()["n"]
        except sqlite3.OperationalError:
            pass  # students table not initialised yet — fine
        try:
            counts["courses"] = conn.execute(
                "SELECT COUNT(*) AS n FROM courses WHERE subject = ?",
                (name,),
            ).fetchone()["n"]
        except sqlite3.OperationalError:
            pass
        # Learning aims (any status) are funding records: a subject with
        # aims behind it must be deactivated, never deleted.
        try:
            counts["aims"] = conn.execute(
                "SELECT COUNT(*) AS n FROM learning_aims WHERE subject = ?",
                (name,),
            ).fetchone()["n"]
        except sqlite3.OperationalError:
            counts["aims"] = 0
    return counts


# ── CRUD ────────────────────────────────────────────────────────────

def create_subject(data: dict[str, Any]) -> Subject:
    init_db()
    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_subject validation failed: %s", e)
        raise

    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO subjects
                   (name, qualification, exam_board, description, is_active,
                    qualification_type, guided_learning_hours, aim_code)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["name"], payload["qualification"],
                 payload["exam_board"], payload["description"],
                 payload["is_active"], payload["qualification_type"],
                 payload["guided_learning_hours"], payload["aim_code"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning("create_subject: duplicate name %s", payload["name"])
            raise ValidationError(
                f"Subject '{payload['name']}' already exists") from e
        logger.exception("create_subject DB error")
        raise ValidationError(f"Database error: {e}") from e

    s = get_subject(new_id)
    assert s is not None
    logger.info("Created subject #%d (%s, %s)", new_id, s.name, s.qualification)
    return s


def get_subject(subject_id: int) -> Subject | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM subjects WHERE subject_id = ?", (subject_id,)
        ).fetchone()
        return _row(row) if row else None


def get_subject_by_name(name: str) -> Subject | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM subjects WHERE name = ?", (name.strip(),)
        ).fetchone()
        return _row(row) if row else None


def list_subjects(
    *,
    qualification: str | None = None,
    exam_board: str | None = None,
    include_inactive: bool = True,
    search: str | None = None,
) -> list[Subject]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if qualification:
        clauses.append("qualification = ?")
        args.append(qualification)
    if exam_board:
        clauses.append("exam_board = ?")
        args.append(exam_board)
    if not include_inactive:
        clauses.append("is_active = 1")
    if search:
        q = f"%{search.strip()}%"
        clauses.append("(name LIKE ? OR description LIKE ?)")
        args.extend([q, q])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM subjects {where} ORDER BY name"
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_subject(subject_id: int, data: dict[str, Any]) -> Subject:
    init_db()
    existing = get_subject(subject_id)
    if existing is None:
        logger.warning("update_subject: unknown id %d", subject_id)
        raise ValidationError(f"No subject with id {subject_id}")

    # Callers written before these fields existed don't send them; keep
    # the stored values rather than blanking them on every edit.
    data = dict(data)
    for key in ("qualification_type", "guided_learning_hours", "aim_code"):
        data.setdefault(key, getattr(existing, key))

    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("update_subject(%d) validation failed: %s", subject_id, e)
        raise

    # Renaming a subject also has to update student / course references
    # so we don't orphan rows that point at a name that no longer exists.
    rename = (existing.name != payload["name"])

    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE subjects SET
                       name = ?, qualification = ?, exam_board = ?,
                       description = ?, is_active = ?,
                       qualification_type = ?, guided_learning_hours = ?,
                       aim_code = ?
                   WHERE subject_id = ?""",
                (payload["name"], payload["qualification"],
                 payload["exam_board"], payload["description"],
                 payload["is_active"], payload["qualification_type"],
                 payload["guided_learning_hours"], payload["aim_code"],
                 subject_id),
            )
            if rename:
                # Best-effort rename across reference tables; tables may
                # not exist yet on a fresh install, which is fine.
                old, new = existing.name, payload["name"]
                for sql in (
                    "UPDATE students SET subject_1 = ? WHERE subject_1 = ?",
                    "UPDATE students SET subject_2 = ? WHERE subject_2 = ?",
                    "UPDATE students SET subject_3 = ? WHERE subject_3 = ?",
                    "UPDATE courses  SET subject   = ? WHERE subject   = ?",
                    "UPDATE learning_aims SET subject = ? WHERE subject = ?",
                    "UPDATE option_block_subjects SET subject = ? WHERE subject = ?",
                    "UPDATE option_choices SET subject = ? WHERE subject = ?",
                ):
                    try:
                        conn.execute(sql, (new, old))
                    except sqlite3.OperationalError:
                        pass
                logger.info(
                    "Renamed subject %d: %r -> %r (refs updated)",
                    subject_id, old, new,
                )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "update_subject(%d): duplicate name %s",
                subject_id, payload["name"],
            )
            raise ValidationError(
                f"Subject '{payload['name']}' already exists") from e
        logger.exception("update_subject DB error")
        raise ValidationError(f"Database error: {e}") from e

    s = get_subject(subject_id)
    assert s is not None
    logger.info(
        "Updated subject #%d (%s, active=%s)",
        subject_id, s.name, s.is_active,
    )
    return s


def deactivate(subject_id: int) -> Subject:
    """Soft-delete: marks the subject inactive. Always allowed."""
    init_db()
    existing = get_subject(subject_id)
    if existing is None:
        logger.warning("deactivate: unknown id %d", subject_id)
        raise ValidationError(f"No subject with id {subject_id}")
    if not existing.is_active:
        return existing
    with _connect() as conn:
        conn.execute(
            "UPDATE subjects SET is_active = 0 WHERE subject_id = ?",
            (subject_id,),
        )
        conn.commit()
    logger.info("Deactivated subject #%d (%s)", subject_id, existing.name)
    s = get_subject(subject_id)
    assert s is not None
    return s


def activate(subject_id: int) -> Subject:
    init_db()
    existing = get_subject(subject_id)
    if existing is None:
        logger.warning("activate: unknown id %d", subject_id)
        raise ValidationError(f"No subject with id {subject_id}")
    if existing.is_active:
        return existing
    with _connect() as conn:
        conn.execute(
            "UPDATE subjects SET is_active = 1 WHERE subject_id = ?",
            (subject_id,),
        )
        conn.commit()
    logger.info("Activated subject #%d (%s)", subject_id, existing.name)
    s = get_subject(subject_id)
    assert s is not None
    return s


def delete_subject(subject_id: int) -> bool:
    """Hard delete. Refuses if any student or course still references the
    subject; the caller should fall back to ``deactivate`` in that case."""
    init_db()
    existing = get_subject(subject_id)
    if existing is None:
        logger.warning("delete_subject: unknown id %d", subject_id)
        return False
    usage = is_in_use(existing.name)
    if usage["students"] or usage["courses"] or usage.get("aims"):
        logger.warning(
            "delete_subject: refusing — %s still in use (students=%d, courses=%d)",
            existing.name, usage["students"], usage["courses"],
        )
        raise ValidationError(
            f"Cannot delete '{existing.name}': still referenced by "
            f"{usage['students']} student(s), {usage['courses']} course(s) "
            f"and {usage.get('aims', 0)} learning aim(s). "
            f"Deactivate it instead."
        )
    with _connect() as conn:
        conn.execute("DELETE FROM subjects WHERE subject_id = ?", (subject_id,))
        conn.commit()
    logger.info("Deleted subject #%d (%s)", subject_id, existing.name)
    return True
