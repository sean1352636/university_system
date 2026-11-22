"""Shared storage for the sixth form integrations (CTF, LRS, backups).

All tables live in the main sixth form DB (``paths.SIXTH_FORM_STUDENTS_DB``)
because several reference ``students``. They are created lazily by
:func:`init_db`; importing this module never touches a database.

Tables
------
* ``integration_settings``   key/value settings: school LA/establishment
  numbers for CTF headers, non-secret LRS configuration, backup retention.
* ``ctf_upn_links``           UPN <-> student_id (the students table has no
  UPN column; a CTF is matched on UPN first).
* ``ctf_imports``             one row per applied CTF, with the file's
  SHA-256 so the same file is never applied twice.
* ``ctf_import_pupils``       what happened to each pupil in an import.
* ``ctf_import_results``      raw KS2/KS4 assessment results from a CTF,
  kept whether or not they could be passed on to a prior-attainment store.
* ``ctf_import_attendance``   per-year attendance summaries from a CTF.
* ``ctf_import_sen`` / ``ctf_import_fsm``  SEN and FSM history (sensitive:
  read through :mod:`ctf` functions that check access and log).
* ``ctf_exports``             one row per CTF written for a leaver.
* ``lrs_requests``            one row per LRS call (never the password).
"""

from __future__ import annotations

import logging
from education_system.systems.sixth_form.infrastructure import database as _sql
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

_SCHEMA = """
CREATE TABLE IF NOT EXISTS integration_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  TEXT DEFAULT (datetime('now')),
    updated_by  TEXT
);

CREATE TABLE IF NOT EXISTS ctf_upn_links (
    upn         TEXT PRIMARY KEY,
    student_id  TEXT NOT NULL UNIQUE,
    source      TEXT,
    linked_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ctf_imports (
    import_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name      TEXT NOT NULL,
    file_sha256    TEXT NOT NULL UNIQUE,
    ctf_version    TEXT,
    generated_at   TEXT,
    source_la      TEXT,
    source_estab   TEXT,
    source_name    TEXT,
    pupil_count    INTEGER NOT NULL DEFAULT 0,
    created_count  INTEGER NOT NULL DEFAULT 0,
    updated_count  INTEGER NOT NULL DEFAULT 0,
    skipped_count  INTEGER NOT NULL DEFAULT 0,
    applied_by     TEXT,
    applied_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ctf_import_pupils (
    row_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id   INTEGER NOT NULL,
    upn         TEXT,
    surname     TEXT,
    forename    TEXT,
    dob         TEXT,
    student_id  TEXT,
    action      TEXT NOT NULL,
    notes       TEXT,
    address     TEXT,
    FOREIGN KEY (import_id) REFERENCES ctf_imports(import_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_ctfp_import  ON ctf_import_pupils(import_id);
CREATE INDEX IF NOT EXISTS idx_ctfp_student ON ctf_import_pupils(student_id);

CREATE TABLE IF NOT EXISTS ctf_import_results (
    result_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id     INTEGER NOT NULL,
    student_id    TEXT NOT NULL,
    stage         TEXT,
    locale        TEXT,
    year          TEXT,
    subject       TEXT,
    method        TEXT,
    component     TEXT,
    result_qualifier TEXT,
    result        TEXT,
    result_date   TEXT,
    forwarded_to  TEXT,
    forwarded_at  TEXT,
    FOREIGN KEY (import_id) REFERENCES ctf_imports(import_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ctfr_student ON ctf_import_results(student_id);

CREATE TABLE IF NOT EXISTS ctf_import_attendance (
    row_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id     INTEGER NOT NULL,
    student_id    TEXT NOT NULL,
    year          TEXT,
    source_la     TEXT,
    source_estab  TEXT,
    sessions_possible     INTEGER,
    sessions_authorised   INTEGER,
    sessions_unauthorised INTEGER,
    start_date    TEXT,
    FOREIGN KEY (import_id) REFERENCES ctf_imports(import_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ctfa_student ON ctf_import_attendance(student_id);

CREATE TABLE IF NOT EXISTS ctf_import_sen (
    row_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id   INTEGER NOT NULL,
    student_id  TEXT NOT NULL,
    start_date  TEXT,
    provision   TEXT,
    needs       TEXT,
    FOREIGN KEY (import_id) REFERENCES ctf_imports(import_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ctfs_student ON ctf_import_sen(student_id);

CREATE TABLE IF NOT EXISTS ctf_import_fsm (
    row_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id   INTEGER NOT NULL,
    student_id  TEXT NOT NULL,
    start_date  TEXT,
    end_date    TEXT,
    country     TEXT,
    review_date TEXT,
    FOREIGN KEY (import_id) REFERENCES ctf_imports(import_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ctff_student ON ctf_import_fsm(student_id);

CREATE TABLE IF NOT EXISTS ctf_exports (
    export_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT,
    file_path    TEXT NOT NULL,
    file_sha256  TEXT NOT NULL,
    dest_la      TEXT,
    dest_estab   TEXT,
    exported_by  TEXT,
    exported_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS lrs_requests (
    request_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    operation      TEXT NOT NULL,
    student_id     TEXT,
    response_code  TEXT,
    response_text  TEXT,
    ulns_returned  TEXT,
    error          TEXT,
    requested_by   TEXT,
    requested_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE SET NULL
);
"""


def connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    """Create the integration tables once per process."""
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Integrations schema ready at %s", DB_PATH)
    _DB_READY = True


# ── Settings ───────────────────────────────────────────────────────

#: Known settings and their defaults. Secrets (the LRS password) are
#: deliberately NOT here: they come from the environment only.
SETTING_DEFAULTS: dict[str, str] = {
    "school_la": "",            # 3-digit local authority number
    "school_estab": "",         # 4-digit DfE establishment number
    "school_name": "",
    "lrs_endpoint": "",
    "lrs_ukprn": "",
    "lrs_username": "",
    "lrs_vendor_id": "",
    "backup_keep": "14",
}


def get_setting(key: str) -> str:
    init_db()
    with connect() as conn:
        r = conn.execute("SELECT value FROM integration_settings WHERE key = ?",
                         (key,)).fetchone()
    if r is None or r["value"] is None:
        return SETTING_DEFAULTS.get(key, "")
    return r["value"]


def set_setting(key: str, value: Any, *, by: str | None = None) -> None:
    if key not in SETTING_DEFAULTS:
        raise ValueError(f"Unknown integration setting: {key}")
    init_db()
    with connect() as conn:
        conn.execute(
            "INSERT INTO integration_settings (key, value, updated_at, updated_by) "
            "VALUES (?, ?, datetime('now'), ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at, updated_by = excluded.updated_by",
            (key, None if value is None else str(value).strip(), by))
        conn.commit()
    logger.info("Integration setting %s updated by %s", key, by or "?")


def current_username() -> str | None:
    """The signed-in principal's username, or None."""
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def require(capability_name: str, action: str) -> str | None:
    """Require *capability_name* (an attribute of access) of the principal.

    Returns the username so callers can stamp ``*_by`` columns.
    """
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    p.require(getattr(access, capability_name), action)
    return p.username or None
