"""University academic integrity: similarity checks tied to assignment
submissions, every matched source with its passages, staff review of each
result, referral into an integrity case with stages, outcomes, penalties
and appeals, reviewer roles, settings, the student notice, and an audit.

``document_repository``, ``plagiarism_results``, ``integrity_cases`` and
``course_integrity_settings`` already exist (the last two were created at
runtime); this adds the columns the workflows need.

Later additions (migration ``d1f3a5c7e9b2``): ``integrity_cases`` is the
university's one misconduct case record, whatever raised it (a similarity
result, AI detection, an exam incident, a disciplinary record, by hand, or a
case copied from the old ``academic_misconduct_cases``), so it is rebuilt
once to accept the wider case types. Student statements, case evidence,
failed automatic checks, reminder bookkeeping, AI-detection reviews and
external-source searches get tables of their own.

AI-writing indicators (migration ``e2a4c6e8f0b3``): the detector's
``ai_detector_submissions`` / ``ai_detector_results`` stay the store, with
the real ids (``assignment_submission_id``, the student number, the module
code, the assignment id) and the method, level and checker recorded; the
student's comment on a result goes in ``ai_result_comments``.

Shared by migrations ``c0e2a4b6d8f1`` / ``d1f3a5c7e9b2`` / ``e2a4c6e8f0b3`` and
:func:`apply_to_connection` (``university/application/integrity/``,
``plagiarism_*``). Idempotent.
"""

from __future__ import annotations

COLUMNS = (
    ("document_repository", "submission_id", "INTEGER"),
    ("document_repository", "assignment_id", "INTEGER"),
    ("document_repository", "student_id", "TEXT"),
    ("document_repository", "academic_year", "TEXT"),
    ("document_repository", "kind", "TEXT DEFAULT 'submission'"),
    ("document_repository", "purged", "INTEGER DEFAULT 0"),
    ("plagiarism_results", "submission_id", "INTEGER"),
    ("plagiarism_results", "assignment_id", "INTEGER"),
    ("plagiarism_results", "words_checked", "INTEGER"),
    ("plagiarism_results", "words_excluded", "INTEGER"),
    ("plagiarism_results", "review_status", "TEXT DEFAULT 'not_needed'"),
    ("plagiarism_results", "reviewed_by", "TEXT"),
    ("plagiarism_results", "reviewed_at", "TEXT"),
    ("plagiarism_results", "review_note", "TEXT"),
    ("plagiarism_results", "case_id", "INTEGER"),
    ("plagiarism_results", "released_to_student", "INTEGER DEFAULT 0"),
    ("integrity_cases", "result_id", "INTEGER"),
    ("integrity_cases", "submission_id", "INTEGER"),
    ("integrity_cases", "stage", "TEXT DEFAULT 'referred'"),
    ("integrity_cases", "decided_by", "TEXT"),
    ("integrity_cases", "decided_at", "TEXT"),
    ("integrity_cases", "grade_before", "REAL"),
    ("integrity_cases", "appeal_deadline", "TEXT"),
    ("integrity_cases", "source", "TEXT DEFAULT 'manual'"),
    ("integrity_cases", "source_ref", "TEXT"),
    ("integrity_cases", "legacy_case_id", "TEXT"),
    ("integrity_cases", "module_code", "TEXT"),
    ("integrity_cases", "severity", "TEXT"),
    ("integrity_cases", "offence_number", "INTEGER"),
    ("integrity_cases", "tariff", "TEXT"),
    ("integrity_cases", "tariff_departure", "TEXT"),
    ("integrity_cases", "response_due", "TEXT"),
    ("integrity_cases", "closed_at", "TEXT"),
    ("document_repository", "source_url", "TEXT"),
    ("plagiarism_results", "paraphrase_score", "REAL"),
    ("plagiarism_results", "obfuscated_chars", "INTEGER DEFAULT 0"),
    ("plagiarism_results", "external_checked_at", "TEXT"),
    ("plagiarism_matches", "match_kind", "TEXT DEFAULT 'exact'"),
    ("plagiarism_matches", "counted", "INTEGER DEFAULT 1"),
    ("assignment_submissions", "misconduct_penalty", "TEXT"),
    ("assignment_submissions", "misconduct_case_id", "INTEGER"),
    ("ai_detector_submissions", "assignment_submission_id", "INTEGER"),
    ("ai_detector_submissions", "checked_by", "TEXT"),
    ("ai_detector_submissions", "file_type", "TEXT"),
    ("ai_detector_submissions", "purged", "INTEGER DEFAULT 0"),
    ("ai_detector_results", "method", "TEXT"),
    ("ai_detector_results", "level", "TEXT"),
)

CASE_TYPES = ("plagiarism", "collusion", "cheating", "contract_cheating", "ai_misuse",
              "fabrication", "other")

# The full case table. An older table (four case types in its CHECK) is
# rebuilt into this shape once by :func:`_widen_cases`.
CASES_DDL = """CREATE TABLE IF NOT EXISTS integrity_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        assignment_id INTEGER,
        case_type TEXT NOT NULL CHECK(case_type IN ({types})),
        description TEXT,
        evidence_path TEXT,
        status TEXT NOT NULL DEFAULT 'open'
            CHECK(status IN ('open','investigating','resolved','dismissed')),
        outcome TEXT,
        penalty TEXT,
        created_by TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        resolved_at TEXT,
        evidence TEXT,
        updated_at TEXT,
        result_id INTEGER,
        submission_id INTEGER,
        stage TEXT DEFAULT 'referred',
        decided_by TEXT,
        decided_at TEXT,
        grade_before REAL,
        appeal_deadline TEXT,
        source TEXT DEFAULT 'manual',
        source_ref TEXT,
        legacy_case_id TEXT,
        module_code TEXT,
        severity TEXT,
        offence_number INTEGER,
        tariff TEXT,
        tariff_departure TEXT,
        response_due TEXT,
        closed_at TEXT
    )""".format(types=", ".join(f"'{t}'" for t in CASE_TYPES))

TABLES = (
    CASES_DDL,
    """CREATE TABLE IF NOT EXISTS course_integrity_settings (
        module_code TEXT PRIMARY KEY,
        ai_detection_enabled INTEGER DEFAULT 1,
        plagiarism_enabled INTEGER DEFAULT 1,
        similarity_threshold REAL DEFAULT 0.3,
        allow_collaboration INTEGER DEFAULT 0,
        notes TEXT,
        updated_at TEXT DEFAULT (datetime('now')),
        updated_by TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS plagiarism_matches (
        match_id INTEGER PRIMARY KEY AUTOINCREMENT,
        result_id INTEGER NOT NULL REFERENCES plagiarism_results (id) ON DELETE CASCADE,
        matched_document_id INTEGER REFERENCES document_repository (id) ON DELETE SET NULL,
        score REAL NOT NULL,
        matched_words INTEGER NOT NULL DEFAULT 0,
        passages TEXT NOT NULL DEFAULT '[]'
    )""",
    "CREATE INDEX IF NOT EXISTS ix_plagiarism_matches_result ON plagiarism_matches (result_id)",
    """CREATE TABLE IF NOT EXISTS integrity_roles (
        username TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('reviewer', 'officer')),
        granted_by TEXT,
        granted_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (username, role)
    )""",
    """CREATE TABLE IF NOT EXISTS integrity_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS integrity_case_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        stage TEXT NOT NULL,
        note TEXT,
        actor TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_integrity_case_events ON integrity_case_events (case_id)",
    """CREATE TABLE IF NOT EXISTS integrity_appeals (
        appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        grounds TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'lodged' CHECK (status IN ('lodged', 'upheld', 'rejected')),
        lodged_by TEXT NOT NULL,
        lodged_at TEXT NOT NULL DEFAULT (datetime('now')),
        decided_by TEXT,
        decided_at TEXT,
        decision_note TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS integrity_acknowledgements (
        username TEXT NOT NULL,
        notice_version TEXT NOT NULL,
        acknowledged_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (username, notice_version)
    )""",
    """CREATE TABLE IF NOT EXISTS integrity_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id TEXT,
        action TEXT NOT NULL,
        actor TEXT,
        detail TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS integrity_statements (
        statement_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        author TEXT NOT NULL,
        statement TEXT NOT NULL,
        submitted_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_integrity_statements_case ON integrity_statements (case_id)",
    """CREATE TABLE IF NOT EXISTS integrity_evidence (
        evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('file', 'note', 'meeting_record', 'similarity_result',
                                           'ai_result', 'exam_incident', 'disciplinary_record',
                                           'legacy')),
        title TEXT NOT NULL,
        detail TEXT,
        file_name TEXT,
        file_path TEXT,
        sha256 TEXT,
        ref TEXT,
        visible_to_student INTEGER NOT NULL DEFAULT 1,
        added_by TEXT,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        removed_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_integrity_evidence_case ON integrity_evidence (case_id)",
    """CREATE TABLE IF NOT EXISTS integrity_check_failures (
        submission_id INTEGER PRIMARY KEY,
        attempts INTEGER NOT NULL DEFAULT 1,
        last_error TEXT,
        first_failed_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_attempt_at TEXT NOT NULL DEFAULT (datetime('now')),
        resolved_at TEXT,
        resolved_by TEXT,
        resolution TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS integrity_reminders (
        kind TEXT NOT NULL,
        ref TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        PRIMARY KEY (kind, ref)
    )""",
    """CREATE TABLE IF NOT EXISTS integrity_ai_reviews (
        ai_result_id INTEGER PRIMARY KEY,
        decision TEXT NOT NULL CHECK (decision IN ('no_concern', 'refer')),
        note TEXT,
        reviewed_by TEXT,
        reviewed_at TEXT NOT NULL DEFAULT (datetime('now')),
        case_id INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        submission_text TEXT NOT NULL,
        title TEXT,
        course_code TEXT,
        assignment_id TEXT,
        submission_date TEXT NOT NULL,
        word_count INTEGER,
        character_count INTEGER,
        institution_id TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER NOT NULL REFERENCES ai_detector_submissions (id),
        ai_score REAL NOT NULL,
        confidence REAL NOT NULL,
        detailed_results TEXT,
        created_at TEXT NOT NULL,
        style_deviation REAL
    )""",
    """CREATE TABLE IF NOT EXISTS ai_result_comments (
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ai_result_id INTEGER NOT NULL,
        author TEXT NOT NULL,
        comment TEXT NOT NULL,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_ai_result_comments ON ai_result_comments (ai_result_id)",
    """CREATE TABLE IF NOT EXISTS integrity_external_searches (
        search_id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        provider TEXT NOT NULL,
        queries INTEGER NOT NULL DEFAULT 0,
        sources_added INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        ran_by TEXT,
        ran_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
)

# Indexes on columns added above, so applied after COLUMNS.
INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_document_repository_assignment "
    "ON document_repository (assignment_id, kind)",
    "CREATE INDEX IF NOT EXISTS ix_document_repository_module ON document_repository (module_code)",
    "CREATE INDEX IF NOT EXISTS ix_plagiarism_results_review "
    "ON plagiarism_results (review_status)",
    "CREATE INDEX IF NOT EXISTS ix_integrity_cases_student ON integrity_cases (student_id, stage)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_integrity_cases_legacy ON integrity_cases "
    "(legacy_case_id) WHERE legacy_case_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_document_repository_hash ON document_repository "
    "(content_hash, kind)",
    "CREATE INDEX IF NOT EXISTS ix_ai_detector_submissions_sub ON ai_detector_submissions "
    "(assignment_submission_id)",
    "CREATE INDEX IF NOT EXISTS ix_ai_detector_submissions_student ON ai_detector_submissions "
    "(student_id, course_code)",
)

# Old university case types -> integrity case types, for the copy below.
_LEGACY_TYPES = {"plagiarism": "plagiarism", "collusion": "collusion", "cheating": "cheating",
                 "exam cheating": "cheating", "contract cheating": "contract_cheating",
                 "contract_cheating": "contract_cheating", "fabrication": "fabrication",
                 "falsification": "fabrication", "ai": "ai_misuse", "ai misuse": "ai_misuse",
                 "unauthorised ai use": "ai_misuse", "unauthorized ai use": "ai_misuse"}
_LEGACY_CLOSED = ("resolved", "closed", "dismissed", "no case", "no_case", "withdrawn")


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def _widen_cases(execute) -> None:
    """Rebuild an old ``integrity_cases`` whose CHECK allows only the first
    four case types. Nothing references the table by foreign key."""
    row = execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND "
                  "name = 'integrity_cases'").fetchone()
    if not row or "ai_misuse" in (row[0] or ""):
        return
    old = _columns(execute, "integrity_cases")
    execute(CASES_DDL.replace("integrity_cases (", "integrity_cases_widened (", 1))
    new = _columns(execute, "integrity_cases_widened")
    keep = ", ".join(f'"{c}"' for c in sorted(old & new))
    execute(f"INSERT INTO integrity_cases_widened ({keep}) SELECT {keep} FROM integrity_cases")
    execute("DROP TABLE integrity_cases")
    execute("ALTER TABLE integrity_cases_widened RENAME TO integrity_cases")


def _copy_legacy_cases(execute) -> None:
    """Copy the university's cases from the old ``academic_misconduct_cases``
    (and their history and evidence) into ``integrity_cases``, once each.
    The old rows stay where they are."""
    old = _columns(execute, "academic_misconduct_cases")
    if not old:
        return
    system = "AND COALESCE(system_key, 'university') = 'university'" if "system_key" in old else ""
    pick = [c for c in ("id", "case_id", "student_id", "violation_type", "status", "severity",
                        "date_filed", "notes", "ruling", "ruling_rationale", "created_at",
                        "course") if c in old]
    rows = execute(f"SELECT {', '.join(pick)} FROM academic_misconduct_cases "  # nosec B608
                   f"WHERE student_id IS NOT NULL {system}").fetchall()
    for values in rows:
        r = dict(zip(pick, values))
        ref = str(r.get("case_id") or r.get("id"))
        if execute("SELECT 1 FROM integrity_cases WHERE legacy_case_id = ?", (ref,)).fetchone():
            continue
        status = str(r.get("status") or "").strip().lower()
        closed = status in _LEGACY_CLOSED
        kind = _LEGACY_TYPES.get(str(r.get("violation_type") or "").strip().lower(), "other")
        filed = str(r.get("date_filed") or r.get("created_at") or "")[:19] or None
        description = "\n\n".join(str(x) for x in (r.get("violation_type"), r.get("notes")) if x)
        outcome_text = "; ".join(str(x) for x in (r.get("ruling"), r.get("ruling_rationale")) if x)
        cur = execute(
            "INSERT INTO integrity_cases (student_id, case_type, description, status, stage, "
            "penalty, created_by, created_at, updated_at, source, source_ref, legacy_case_id, "
            "severity, closed_at) VALUES (?, ?, ?, ?, ?, ?, 'legacy', ?, ?, 'legacy', ?, ?, ?, ?)",
            (str(r["student_id"]), kind, description or "Copied from the old case list",
             "resolved" if closed else "investigating", "closed" if closed else "investigating",
             outcome_text or None, filed, filed, ref, ref, r.get("severity"),
             filed if closed else None))
        case_id = cur.lastrowid
        execute("INSERT INTO integrity_case_events (case_id, stage, note, actor, at) VALUES "
                "(?, ?, ?, 'legacy', COALESCE(?, datetime('now')))",
                (case_id, "closed" if closed else "investigating",
                 f"Copied from academic misconduct case {ref} (status {r.get('status')})",
                 filed))
        hist = _columns(execute, "academic_misconduct_history")
        if {"case_id", "event_description"} <= hist:
            date_col = "event_date" if "event_date" in hist else "NULL"
            by_col = "created_by" if "created_by" in hist else "NULL"
            for at, note, by in execute(
                    f"SELECT {date_col}, event_description, {by_col} FROM "  # nosec B608
                    "academic_misconduct_history WHERE case_id = ?", (ref,)).fetchall():
                execute("INSERT INTO integrity_case_events (case_id, stage, note, actor, at) "
                        "VALUES (?, 'history', ?, ?, COALESCE(?, datetime('now')))",
                        (case_id, note, by or "legacy", at))
        ev = _columns(execute, "academic_misconduct_evidence")
        if {"case_id", "file_name"} <= ev:
            path_col = "file_path" if "file_path" in ev else "NULL"
            for name, path in execute(f"SELECT file_name, {path_col} FROM "  # nosec B608
                                      "academic_misconduct_evidence WHERE case_id = ?",
                                      (ref,)).fetchall():
                execute("INSERT INTO integrity_evidence (case_id, kind, title, file_name, "
                        "file_path, added_by) VALUES (?, 'legacy', ?, ?, ?, 'legacy')",
                        (case_id, name or "Evidence", name, path))


def _normalise_ai_ids(execute) -> None:
    """The retired AI detector GUI saved display labels — "Name (5853694)",
    "ACC-Y1-2 - Management Accounting", "test 2 (Due: 2026-09-02)" — where
    ids belong. Turn them back into the student number, module code and
    assignment id (left empty when it cannot be told), once."""
    cols = _columns(execute, "ai_detector_submissions")
    if not {"student_id", "course_code", "assignment_id"} <= cols:
        return
    rows = execute("SELECT id, student_id, course_code, assignment_id FROM "
                   "ai_detector_submissions WHERE student_id LIKE '%(%)' OR course_code LIKE "
                   "'% - %' OR (assignment_id IS NOT NULL AND assignment_id GLOB '*[^0-9]*')"
                   ).fetchall()
    for row_id, student, module, assignment in rows:
        student = str(student or "")
        if student.endswith(")") and "(" in student:
            student = student[student.rindex("(") + 1:-1].strip()
        module = str(module or "")
        if " - " in module:
            module = module.split(" - ", 1)[0].strip()
        found = None
        text = str(assignment or "")
        if text and not text.isdigit():
            title = text.split(" (Due:", 1)[0].strip()
            match = execute("SELECT id FROM assignments WHERE title = ? AND module_code = ?",
                            (title, module)).fetchall() if _columns(execute, "assignments") else []
            found = str(match[0][0]) if len(match) == 1 else None
        else:
            found = text or None
        execute("UPDATE ai_detector_submissions SET student_id = ?, course_code = ?, "
                "assignment_id = ? WHERE id = ?", (student, module or None, found, row_id))


def apply(execute) -> None:
    _widen_cases(execute)
    for ddl in TABLES:
        execute(ddl)
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in INDEXES:
        execute(ddl)
    _copy_legacy_cases(execute)
    _normalise_ai_ids(execute)


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
