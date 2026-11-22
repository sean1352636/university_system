"""Lecturer evaluation: students rate each lecturer who teaches them on a
module, once per module survey (module and academic year), in the module
survey's window. Lecturers are staff logins (``staff.username``);
timetabled ``instructors`` reach theirs through ``instructors.staff_id``.

Shared by migration ``d7a9c1e3f5b8`` and :func:`apply_to_connection`
(``university/application/evaluation/lecturer``). Idempotent.

``lecturer_evaluations`` used to key a lecturer by ``instructors.id`` and
store the student id next to the ratings; it never held a row on the live
database because its insert was broken. :func:`rebuild_legacy` replaces it
(keeping any rows in ``lecturer_evaluations_legacy`` with the student id
swapped for a token).
"""

from __future__ import annotations

import secrets

CRITERIA = ("knowledge", "communication", "preparation", "engagement", "fairness",
            "availability", "overall")

TABLES = (
    "CREATE TABLE IF NOT EXISTS lecturer_evaluations (\n"
    "    evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    form_id INTEGER NOT NULL REFERENCES evaluation_forms(id),\n"
    "    module_code TEXT NOT NULL,\n"
    "    academic_year TEXT NOT NULL,\n"
    "    lecturer TEXT NOT NULL,\n"
    "    respondent TEXT NOT NULL,\n"
    + "".join(f"    {c} INTEGER NOT NULL CHECK ({c} BETWEEN 1 AND 5),\n" for c in CRITERIA)
    + "    comments TEXT,\n"
    "    submitted_at TEXT NOT NULL\n"
    ")",
    "CREATE INDEX IF NOT EXISTS ix_lecturer_evaluations_lecturer ON lecturer_evaluations "
    "(lecturer, academic_year)",
    """CREATE TABLE IF NOT EXISTS lecturer_eval_invitations (
        form_id INTEGER NOT NULL REFERENCES evaluation_forms(id),
        lecturer TEXT NOT NULL,
        student_id TEXT NOT NULL,
        invited_at TEXT NOT NULL DEFAULT (date('now')),
        reminded_at TEXT,
        responded INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (form_id, lecturer, student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS lecturer_eval_comment_reviews (
        evaluation_id INTEGER PRIMARY KEY REFERENCES lecturer_evaluations(evaluation_id),
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'released', 'withheld')),
        reviewed_by TEXT,
        reviewed_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS lecturer_reflections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        form_id INTEGER NOT NULL REFERENCES evaluation_forms(id),
        lecturer TEXT NOT NULL,
        reflection TEXT NOT NULL,
        actions TEXT,
        you_said TEXT,
        we_did TEXT,
        published INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        published_at TEXT
    )""",
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def rebuild_legacy(execute) -> None:
    """Replace the old instructor-id table with the new shape."""
    cols = _columns(execute, "lecturer_evaluations")
    if not cols or "lecturer" in cols:
        return
    rows = execute("SELECT COUNT(*) FROM lecturer_evaluations").fetchone()[0]
    if rows and not _columns(execute, "lecturer_evaluations_legacy"):
        execute("ALTER TABLE lecturer_evaluations RENAME TO lecturer_evaluations_legacy")
        for (row_id,) in execute("SELECT evaluation_id FROM lecturer_evaluations_legacy"
                                 ).fetchall():
            execute("UPDATE lecturer_evaluations_legacy SET student_id = ?, submitted_at = "
                    "substr(submitted_at, 1, 10) WHERE evaluation_id = ?",
                    (f"tok-{secrets.token_hex(16)}", row_id))
    else:
        execute("DROP TABLE lecturer_evaluations")


def link_instructors(execute) -> None:
    """``instructors.staff_id`` (the link ``services/staff_provisioning``
    uses): set from the staff record with the same email where unset. A
    lecturer's login is that staff record's ``username``."""
    cols = _columns(execute, "instructors")
    if not cols:
        return
    if "staff_id" not in cols:
        execute('ALTER TABLE "instructors" ADD COLUMN "staff_id" INTEGER')
    if _columns(execute, "staff"):
        execute("UPDATE instructors SET staff_id = (SELECT s.id FROM staff s WHERE "
                "LOWER(s.email) = LOWER(instructors.email) LIMIT 1) WHERE staff_id IS NULL "
                "AND COALESCE(email, '') <> ''")


def apply(execute) -> None:
    if not _columns(execute, "evaluation_forms"):
        return
    rebuild_legacy(execute)
    for ddl in TABLES:
        execute(ddl)
    link_instructors(execute)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file. Inside a caller's open
    transaction it applies without committing or caching."""
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute)
    if busy:
        return
    conn.commit()
    if key:
        _APPLIED.add(key)
