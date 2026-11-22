"""Programme (course) record tables for Course Management.

Shared by migration ``e2b4d6f8a1c3`` and :func:`apply_to_connection`. Idempotent.

* ``course_specifications`` — what the programme is: award title, UCAS and
  HECoS codes, mode of study, awarding body, campus, entry requirements and
  progression rules. One row per ``courses`` code. A side table rather than
  more ``courses`` columns: that table has 31 columns and an unfinished
  code/course_code rename.
* ``course_exit_awards`` — the awards a student can leave with (CertHE,
  DipHE, Ordinary degree, Honours…) and the credits each needs.
* ``course_intake_targets`` — planned intake per academic year and mode.
* ``course_external_examiners`` — programme-level examiners, their term of
  office and the annual report / response cycle.
* ``course_outcome_modules`` — which modules (and which of their outcomes)
  teach and assess each programme learning outcome.
* ``course_survey_results`` — NSS-style survey results per theme and year.

Reused rather than duplicated: tuition fees go in finance's ``program_fees``;
governance (versions, validation, accreditation, teach-out) is
``governed_programmes`` keyed on the same programme code.
"""

from __future__ import annotations

MODES = ("full-time", "part-time", "sandwich", "placement year", "distance learning")
COVERAGE = ("introduced", "developed", "assessed")

TABLES = (
    """CREATE TABLE IF NOT EXISTS course_specifications (
        course_code TEXT PRIMARY KEY,
        award_title TEXT,
        ucas_code TEXT,
        hecos_code TEXT,
        mode_of_study TEXT,
        awarding_body TEXT,
        campus TEXT,
        typical_offer TEXT,
        required_subjects TEXT,
        english_requirement TEXT,
        pass_mark REAL CHECK (pass_mark IS NULL OR pass_mark BETWEEN 0 AND 100),
        progression_credits INTEGER CHECK (progression_credits IS NULL OR progression_credits >= 0),
        max_compensated_credits INTEGER
            CHECK (max_compensated_credits IS NULL OR max_compensated_credits >= 0),
        compensation_min_mark REAL
            CHECK (compensation_min_mark IS NULL OR compensation_min_mark BETWEEN 0 AND 100),
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS course_exit_awards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL,
        award_name TEXT NOT NULL,
        total_credits INTEGER NOT NULL CHECK (total_credits > 0),
        credits_at_level INTEGER NOT NULL DEFAULT 0 CHECK (credits_at_level >= 0),
        at_level INTEGER CHECK (at_level IS NULL OR at_level BETWEEN 3 AND 8),
        is_final INTEGER NOT NULL DEFAULT 0,
        UNIQUE (course_code, award_name)
    )""",
    """CREATE TABLE IF NOT EXISTS course_intake_targets (
        course_code TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        mode_of_study TEXT NOT NULL DEFAULT 'full-time',
        target INTEGER NOT NULL CHECK (target >= 0),
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (course_code, academic_year, mode_of_study)
    )""",
    """CREATE TABLE IF NOT EXISTS course_external_examiners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL,
        examiner_id INTEGER NOT NULL REFERENCES external_examiners(examiner_id),
        appointed_from TEXT NOT NULL,
        appointed_to TEXT NOT NULL,
        report_due TEXT,
        report_received_at TEXT,
        report_summary TEXT,
        response TEXT,
        responded_at TEXT,
        responded_by TEXT,
        CHECK (appointed_to > appointed_from)
    )""",
    """CREATE TABLE IF NOT EXISTS course_outcome_modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        outcome_id INTEGER NOT NULL REFERENCES course_learning_outcomes(id) ON DELETE CASCADE,
        module_code TEXT NOT NULL,
        module_outcome_code TEXT NOT NULL DEFAULT '',
        coverage TEXT NOT NULL CHECK (coverage IN ('introduced', 'developed', 'assessed')),
        UNIQUE (outcome_id, module_code, module_outcome_code)
    )""",
    """CREATE TABLE IF NOT EXISTS course_survey_results (
        course_code TEXT NOT NULL,
        survey TEXT NOT NULL DEFAULT 'NSS',
        academic_year TEXT NOT NULL,
        theme TEXT NOT NULL,
        agree_pct REAL NOT NULL CHECK (agree_pct BETWEEN 0 AND 100),
        respondents INTEGER CHECK (respondents IS NULL OR respondents >= 0),
        PRIMARY KEY (course_code, survey, academic_year, theme)
    )""",
)


def apply(execute) -> None:
    for ddl in TABLES:
        execute(ddl)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` on an open connection, once per database file.

    Inside a caller's open transaction it applies without committing (and is
    not remembered), so it can never commit half of someone else's work; the
    caller's commit or rollback decides. In-memory databases are never
    remembered: a connection id can be reused by a new database.
    """
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
