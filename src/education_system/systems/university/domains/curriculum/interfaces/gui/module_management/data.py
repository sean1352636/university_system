"""Data access for the Module Management window.

No tkinter here: every function takes an optional ``conn`` so it can be
exercised against a temporary database, and opens (and closes) its own
connection otherwise.

Which tables, and why
---------------------
* **Enrolments** are ``student_modules`` rows with status ``Enrolled`` /
  ``Withdrawn``. That is what every enrolment screen, the CLI, the
  ``v_module_occupancy`` view and the enrolment eligibility gate
  (``services/bus/enrolment_bus``) read. Withdrawing is a status change, never
  a delete, so history and any grade survive.
* **Programme links** are the union ``v_course_module_map`` reads. Only
  ``course_module_map`` rows are ours to add or remove; links that come from
  ``course_curriculum`` or from ``modules.course`` are shown with their source
  and changed where they live.
* **Module prerequisites** are ``degree_course_prerequisites``.
  ``course_prerequisites`` cannot hold a module-level rule — its
  ``course_id``/``prerequisite_course_id`` pair is NOT NULL, a foreign key to
  ``courses`` and UNIQUE — so its module-keyed rows are shown read-only. The
  eligibility gate reads both tables.
* **Rules** (specification, change control, designations, exclusions,
  waitlist, cohorts, teaching team, deliveries, timetable) live in
  ``university/application/modules/specification``, ``module_enrolment`` and
  ``module_delivery``; :func:`call` runs one and commits.
* **Retiring** a module sets ``is_active = 0``. Deleting cascades through
  schedules, attendance, assignments and grades, so this window does not.
"""

from __future__ import annotations

import csv
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable

logger = logging.getLogger(__name__)

ENROLLED = "Enrolled"
WITHDRAWN = "Withdrawn"

EXPORT_COLUMNS = [
    "module_code", "module_name", "module_type", "credits", "semester", "year",
    "course", "department", "instructor", "capacity", "is_active", "description", "level",
]
_INT_COLUMNS = {"credits", "capacity", "is_active", "level"}


# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------

@contextmanager
def _connection(conn=None):
    if conn is not None:
        yield conn
        return
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    own = get_connection()
    try:
        yield own
    finally:
        own.close()


def _rows(conn, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    """Rows as dicts, whatever row_factory the connection has."""
    cur = conn.execute(sql, tuple(params))
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _one(conn, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    rows = _rows(conn, sql, params)
    return rows[0] if rows else None


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
        (name,)).fetchone() is not None


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def call(fn, *args, conn=None, **kwargs):
    """Run an application-layer rule ``fn(conn, ...)`` and commit.

    The module rules live in ``university/application`` (shared with the CLI
    and the student catalogue) and leave committing to the caller.
    """
    with _connection(conn) as c:
        try:
            result = fn(c, *args, **kwargs)
            c.commit()
        except Exception:
            c.rollback()
            raise
        return result


def _ensure_schema(conn) -> None:
    """The module catalogue tables and ``modules.level`` (idempotent, cached)."""
    from education_system.systems.university.infrastructure.database.schemas import (
        module_catalogue_schema,
    )
    module_catalogue_schema.apply_to_connection(conn)


def _module_exists(conn, code: str) -> bool:
    return conn.execute("SELECT 1 FROM modules WHERE module_code = ?",
                        (code,)).fetchone() is not None


# ---------------------------------------------------------------------------
# catalogue
# ---------------------------------------------------------------------------

def list_modules(search: str = "", *, include_inactive: bool = False,
                 instructor: str | None = None, conn=None) -> list[dict[str, Any]]:
    """Modules for the catalogue list, with their live enrolment count.

    *instructor* limits the list to modules taught by that username; the
    ``modules`` row records the instructor by name or by ``users.id``
    depending on how it was assigned, so either matches.
    """
    # Rows with a blank code exist in live data; they cannot be selected or
    # edited by code, so the catalogue leaves them to validate() to report.
    clauses: list[str] = ["TRIM(COALESCE(m.module_code, '')) != ''"]
    params: list[Any] = []
    if not include_inactive:
        clauses.append("COALESCE(m.is_active, 1) = 1")
    if search:
        clauses.append("(m.module_code LIKE ? ESCAPE '\\' "
                       "OR m.module_name LIKE ? ESCAPE '\\')")
        params += [_like(search), _like(search)]
    if instructor:
        clauses.append("(m.instructor = ? COLLATE NOCASE OR m.instructor_id IN "
                       "(SELECT id FROM users WHERE username = ? COLLATE NOCASE))")
        params += [instructor, instructor]
    where = " WHERE " + " AND ".join(clauses)
    with _connection(conn) as c:
        _ensure_schema(c)
        # db-audit: ignore[DBW001] - WHERE is built from literal clauses
        return _rows(c, f"""
            SELECT m.module_code, m.module_name, m.module_type, m.credits,
                   m.semester, m.year,
                   COALESCE(NULLIF(m.course, ''), m.department) AS course,
                   m.instructor, COALESCE(m.is_active, 1) AS is_active,
                   m.capacity, m.description, m.level,
                   (SELECT COUNT(*) FROM student_modules sm
                     WHERE sm.module_code = m.module_code
                       AND sm.status = 'Enrolled') AS enrolled
            FROM modules m{where}
            ORDER BY m.module_code""", params)


def get_module(code: str, conn=None) -> dict[str, Any] | None:
    with _connection(conn) as c:
        _ensure_schema(c)
        return _one(c, """
            SELECT m.module_code, m.module_name, m.module_type, m.credits,
                   m.semester, m.year,
                   COALESCE(NULLIF(m.course, ''), m.department) AS course,
                   m.instructor, COALESCE(m.is_active, 1) AS is_active,
                   m.capacity, m.description, m.level, m.department,
                   (SELECT COUNT(*) FROM student_modules sm
                     WHERE sm.module_code = m.module_code
                       AND sm.status = 'Enrolled') AS enrolled
            FROM modules m WHERE m.module_code = ?""", (code,))


def set_active(code: str, active: bool, conn=None) -> bool:
    """Retire (``active=False``) or reinstate a module. Nothing is deleted."""
    with _connection(conn) as c:
        cur = c.execute(
            "UPDATE modules SET is_active = ?, updated_at = ? WHERE module_code = ?",
            (1 if active else 0, _now(), code))
        c.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# programmes
# ---------------------------------------------------------------------------

def course_choices(conn=None) -> list[dict[str, str]]:
    """Every course a module can be linked to: ``[{code, name}]``."""
    with _connection(conn) as c:
        return _rows(c, """
            SELECT DISTINCT COALESCE(NULLIF(course_code, ''), code) AS code,
                   COALESCE(NULLIF(course_name, ''), name) AS name
            FROM courses
            WHERE TRIM(COALESCE(NULLIF(course_code, ''), code, '')) != ''
            ORDER BY 1""")


def list_programmes(code: str, conn=None) -> list[dict[str, Any]]:
    """Programmes the module belongs to, each with where the link comes from."""
    with _connection(conn) as c:
        links: dict[str, dict[str, Any]] = {}

        def add(course_code, source, removable):
            key = (course_code or "").strip()
            if not key:
                return
            entry = links.setdefault(key, {"course_code": key, "sources": [],
                                           "removable": False})
            entry["sources"].append(source)
            entry["removable"] = entry["removable"] or removable

        if _table_exists(c, "course_module_map"):
            for r in _rows(c, "SELECT course_code, link_source FROM course_module_map "
                              "WHERE TRIM(module_code) = ?", (code,)):
                add(r["course_code"], f"programme link ({r['link_source']})", True)
        if _table_exists(c, "course_curriculum"):
            for r in _rows(c, "SELECT DISTINCT course_code FROM course_curriculum "
                              "WHERE TRIM(module_code) = ?", (code,)):
                add(r["course_code"], "course curriculum", False)
        module = _one(c, "SELECT course FROM modules WHERE module_code = ?", (code,))
        if module and module["course"]:
            add(module["course"], "module record", False)

        names = {r["code"]: r["name"] for r in course_choices(conn=c)}
        out = []
        for key in sorted(links):
            entry = links[key]
            out.append({"course_code": key, "course_name": names.get(key) or "",
                        "source": ", ".join(entry["sources"]),
                        "removable": entry["removable"]})
        return out


def add_programme(code: str, course_code: str, conn=None) -> bool:
    """Link *code* to *course_code*. False when the link already existed."""
    course_code = (course_code or "").strip()
    with _connection(conn) as c:
        if not _module_exists(c, code):
            raise ValueError(f"Module {code} does not exist")
        if course_code not in {r["code"] for r in course_choices(conn=c)}:
            raise ValueError(f"Course {course_code} does not exist")
        cur = c.execute(
            "INSERT OR IGNORE INTO course_module_map (course_code, module_code, link_source) "
            "VALUES (?, ?, 'manual')", (course_code, code))
        c.commit()
        return cur.rowcount > 0


def remove_programme(code: str, course_code: str, conn=None) -> bool:
    """Remove a ``course_module_map`` link. Links from elsewhere are untouched."""
    with _connection(conn) as c:
        cur = c.execute("DELETE FROM course_module_map "
                        "WHERE TRIM(module_code) = ? AND TRIM(course_code) = ?",
                        (code, course_code))
        c.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# prerequisites
# ---------------------------------------------------------------------------

def list_prerequisites(code: str, conn=None) -> list[dict[str, Any]]:
    with _connection(conn) as c:
        out: list[dict[str, Any]] = []
        if _table_exists(c, "degree_course_prerequisites"):
            for r in _rows(c, """
                    SELECT dp.prerequisite_id AS id, dp.prerequisite_module_code AS code,
                           COALESCE(m.module_name, '') AS name, dp.min_grade,
                           COALESCE(dp.is_corequisite, 0) AS is_corequisite
                    FROM degree_course_prerequisites dp
                    LEFT JOIN modules m ON m.module_code = dp.prerequisite_module_code
                    WHERE dp.module_code = ? ORDER BY dp.prerequisite_module_code""",
                    (code,)):
                out.append(dict(r, source="module rule", removable=True))
        if _table_exists(c, "course_prerequisites"):
            cols = {r[1] for r in c.execute("PRAGMA table_info(course_prerequisites)")}
            if {"module_code", "prerequisite_module_code"} <= cols:
                for r in _rows(c, """
                        SELECT cp.id, cp.prerequisite_module_code AS code,
                               COALESCE(m.module_name, '') AS name, cp.min_grade,
                               COALESCE(cp.is_corequisite, 0) AS is_corequisite
                        FROM course_prerequisites cp
                        LEFT JOIN modules m ON m.module_code = cp.prerequisite_module_code
                        WHERE cp.module_code = ? AND cp.prerequisite_module_code IS NOT NULL""",
                        (code,)):
                    out.append(dict(r, source="course rule", removable=False))
        return out


def _requires(conn, code: str) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT prerequisite_module_code FROM degree_course_prerequisites "
        "WHERE module_code = ?", (code,))]


def add_prerequisite(code: str, prerequisite: str, *, min_grade: str | None = None,
                     corequisite: bool = False, conn=None) -> int:
    """Require *prerequisite* before (or alongside) *code*. Returns the rule id."""
    code, prerequisite = (code or "").strip(), (prerequisite or "").strip()
    if not code or not prerequisite:
        raise ValueError("Both modules are required")
    if code == prerequisite:
        raise ValueError("A module cannot be its own prerequisite")
    with _connection(conn) as c:
        for m in (code, prerequisite):
            if not _module_exists(c, m):
                raise ValueError(f"Module {m} does not exist")
        # Walk what the prerequisite itself requires: reaching *code* means the
        # new rule would close a loop no student could ever satisfy.
        seen, stack = set(), [prerequisite]
        while stack:
            current = stack.pop()
            if current == code:
                raise ValueError(f"{prerequisite} already depends on {code}; "
                                 "adding this would create a cycle")
            if current not in seen:
                seen.add(current)
                stack.extend(_requires(c, current))
        if c.execute("SELECT 1 FROM degree_course_prerequisites "
                     "WHERE module_code = ? AND prerequisite_module_code = ?",
                     (code, prerequisite)).fetchone():
            raise ValueError(f"{code} already requires {prerequisite}")
        cur = c.execute(
            "INSERT INTO degree_course_prerequisites "
            "(module_code, prerequisite_module_code, min_grade, is_corequisite) "
            "VALUES (?, ?, ?, ?)",
            (code, prerequisite, (min_grade or "").strip() or None,
             1 if corequisite else 0))
        c.commit()
        return int(cur.lastrowid)


def remove_prerequisite(rule_id: int, conn=None) -> bool:
    with _connection(conn) as c:
        cur = c.execute("DELETE FROM degree_course_prerequisites WHERE prerequisite_id = ?",
                        (rule_id,))
        c.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# enrolments
# ---------------------------------------------------------------------------

def list_enrolments(code: str, *, include_withdrawn: bool = True,
                    conn=None) -> list[dict[str, Any]]:
    status_clause = "" if include_withdrawn else " AND sm.status = 'Enrolled'"
    with _connection(conn) as c:
        # db-audit: ignore[DBW001] - status_clause is one of two literals
        return _rows(c, f"""
            SELECT sm.student_id,
                   TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) AS name,
                   sm.status, sm.enrollment_date,
                   COALESCE((SELECT mg.final_grade FROM module_grades mg
                              WHERE mg.student_id = sm.student_id
                                AND mg.module_code = sm.module_code
                              ORDER BY mg.id DESC LIMIT 1), sm.grade) AS grade,
                   (SELECT mg.final_score FROM module_grades mg
                     WHERE mg.student_id = sm.student_id
                       AND mg.module_code = sm.module_code
                     ORDER BY mg.id DESC LIMIT 1) AS score
            FROM student_modules sm
            LEFT JOIN students s ON s.student_id = sm.student_id
            WHERE sm.module_code = ?{status_clause}
            ORDER BY sm.status, sm.student_id""", (code,))


def student_choices(conn=None) -> list[dict[str, str]]:
    with _connection(conn) as c:
        return _rows(c, """
            SELECT student_id,
                   TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS name
            FROM students ORDER BY student_id""")


def check_eligibility(student_id: str, code: str, conn=None):
    """The shared enrolment gate (registration window, requisites, capacity)."""
    from education_system.systems.university.services.bus.enrolment_bus import (
        check_enrolment_eligibility,
    )
    return check_enrolment_eligibility(student_id, code, conn=conn)


def enrol_student(code: str, student_id: str, section_id=None, conn=None) -> str:
    """Enrol a student: ``'enrolled'``, ``'reinstated'`` or ``'already'``.

    The write (and resolving any waitlist place) is the shared rule in
    ``application/modules/enrolment``; the eligibility check is the caller's.
    """
    from education_system.systems.university.application.modules import (
        enrolment as module_enrolment,
    )
    return call(module_enrolment.enrol, code, student_id, section_id, conn=conn)


def withdraw_student(code: str, student_id: str, conn=None) -> bool:
    """Mark an enrolment withdrawn. The row and any grade are kept."""
    from education_system.systems.university.application.modules import (
        enrolment as module_enrolment,
    )
    return call(module_enrolment.withdraw, code, student_id, conn=conn)


def withdraw_and_promote(code: str, student_ids, actor: str | None = None,
                         conn=None) -> dict:
    """Withdraw students, then give each freed seat to the first eligible
    student on the waitlist. ``{withdrawn: [...], promoted: [...]}``."""
    from education_system.systems.university.application.modules import (
        enrolment as module_enrolment,
    )
    return call(module_enrolment.bulk_withdraw, code, list(student_ids), actor, conn=conn)


def student_emails(code: str, conn=None) -> list[dict[str, str]]:
    """Enrolled students on *code* who have an email address."""
    with _connection(conn) as c:
        return _rows(c, """
            SELECT sm.student_id, s.email_address AS email
            FROM student_modules sm JOIN students s ON s.student_id = sm.student_id
            WHERE sm.module_code = ? AND sm.status = 'Enrolled'
              AND TRIM(COALESCE(s.email_address, '')) LIKE '%@%'
            ORDER BY sm.student_id""", (code,))


# ---------------------------------------------------------------------------
# staffing
# ---------------------------------------------------------------------------

def instructor_choices(conn=None) -> list[dict[str, str]]:
    """Accounts that can teach: every non-student user."""
    with _connection(conn) as c:
        return _rows(c, """
            SELECT username,
                   TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS name,
                   role
            FROM users
            WHERE COALESCE(role, '') != 'student' AND TRIM(COALESCE(username, '')) != ''
            ORDER BY username""")


def assign_instructor(code: str, username: str | None, conn=None) -> None:
    """Set (or with ``None`` clear) the module's instructor.

    ``modules`` keeps the display name and the ``users.id``; both are written
    so the name-based and id-based lookups elsewhere agree. The id is resolved
    by username in *this* database — auth.db ids are a different id space.
    """
    username = (username or "").strip() or None
    with _connection(conn) as c:
        if not _module_exists(c, code):
            raise ValueError(f"Module {code} does not exist")
        user_id = None
        if username:
            row = c.execute("SELECT id FROM users WHERE username = ? COLLATE NOCASE",
                            (username,)).fetchone()
            if row is None:
                raise ValueError(f"No user account named {username}")
            user_id = row[0]
        c.execute("UPDATE modules SET instructor = ?, instructor_id = ?, updated_at = ? "
                  "WHERE module_code = ?", (username, user_id, _now(), code))
        c.commit()


# ---------------------------------------------------------------------------
# assessment
# ---------------------------------------------------------------------------

def list_assessments(code: str, conn=None) -> list[dict[str, Any]]:
    with _connection(conn) as c:
        if not _table_exists(c, "assessments"):
            return []
        return _rows(c, """
            SELECT assessment_name, assessment_type, weight, max_points, due_date, status
            FROM assessments WHERE module_code = ?
            ORDER BY COALESCE(due_date, ''), assessment_name""", (code,))


def grade_summary(code: str, conn=None) -> dict[str, Any]:
    """Final-mark summary from ``module_grades`` plus the assessment weighting."""
    with _connection(conn) as c:
        marks = _one(c, """
            SELECT COUNT(*) AS graded, AVG(final_score) AS average,
                   SUM(CASE WHEN final_grade IS NOT NULL AND TRIM(final_grade) != ''
                             AND UPPER(final_grade) NOT LIKE 'F%' THEN 1 ELSE 0 END) AS passed
            FROM module_grades WHERE module_code = ?""", (code,)) or {}
        weight = None
        if _table_exists(c, "assessments"):
            weight = c.execute("SELECT SUM(weight), COUNT(*) FROM assessments "
                               "WHERE module_code = ?", (code,)).fetchone()
        return {
            "graded": marks.get("graded") or 0,
            "average": marks.get("average"),
            "passed": marks.get("passed") or 0,
            "assessments": (weight[1] if weight else 0) or 0,
            "total_weight": (weight[0] if weight else None),
        }


# ---------------------------------------------------------------------------
# reports and bulk
# ---------------------------------------------------------------------------

def report_lines(conn=None) -> list[str]:
    modules = list_modules(include_inactive=True, conn=conn)
    lines = [f"Module Report — {datetime.now():%Y-%m-%d %H:%M}",
             f"{len(modules)} modules "
             f"({sum(1 for m in modules if not m['is_active'])} retired)", ""]
    header = f"{'Code':<12} {'Name':<40} {'Credits':>7} {'Enrolled':>8}  {'Instructor':<16} Status"
    lines += [header, "-" * len(header)]
    for m in modules:
        lines.append(
            f"{(m['module_code'] or '')[:12]:<12} {(m['module_name'] or '')[:40]:<40} "
            f"{m['credits'] if m['credits'] is not None else '-':>7} {m['enrolled']:>8}  "
            f"{(m['instructor'] or 'Unassigned')[:16]:<16} "
            f"{'Active' if m['is_active'] else 'Retired'}")
    return lines


def export_csv(path: str, conn=None) -> int:
    with _connection(conn) as c:
        _ensure_schema(c)
        # db-audit: ignore[DBW001] - column list is the EXPORT_COLUMNS literal
        rows = c.execute(
            f"SELECT {', '.join(EXPORT_COLUMNS)} FROM modules ORDER BY module_code"
        ).fetchall()
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(EXPORT_COLUMNS)
        writer.writerows(tuple(r) for r in rows)
    return len(rows)


def import_csv(path: str, conn=None) -> tuple[int, list[str]]:
    """Add modules from a CSV. Existing codes are skipped, never overwritten.

    ``module_code`` and ``module_name`` are required; any other
    :data:`EXPORT_COLUMNS` present are imported too, so an export round-trips.
    """
    problems: list[str] = []
    imported = 0
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = [f for f in (reader.fieldnames or []) if f]
        if not {"module_code", "module_name"} <= set(fields):
            raise ValueError("CSV needs module_code and module_name columns")
        columns = [f for f in EXPORT_COLUMNS if f in fields]
        with _connection(conn) as c:
            _ensure_schema(c)
            for line, row in enumerate(reader, start=2):
                code = (row.get("module_code") or "").strip().upper()
                name = (row.get("module_name") or "").strip()
                if not code or not name:
                    problems.append(f"line {line}: missing module_code or module_name")
                    continue
                if _module_exists(c, code):
                    problems.append(f"line {line}: {code} already exists (skipped)")
                    continue
                values = []
                try:
                    for col in columns:
                        raw = (row.get(col) or "").strip()
                        if col == "module_code":
                            values.append(code)
                        elif col in _INT_COLUMNS:
                            values.append(int(raw) if raw else None)
                        else:
                            values.append(raw or None)
                except ValueError:
                    problems.append(f"line {line}: credits, capacity and is_active "
                                    "must be whole numbers")
                    continue
                # db-audit: ignore[DBW001] - columns filtered against EXPORT_COLUMNS
                c.execute(f"INSERT INTO modules ({', '.join(columns)}) "
                          f"VALUES ({', '.join('?' for _ in columns)})", values)
                imported += 1
            c.commit()
    return imported, problems


def validate(conn=None) -> list[str]:
    """Read-only integrity checks. Returns one line per problem found."""
    issues: list[str] = []
    with _connection(conn) as c:
        def count(sql):
            return c.execute(sql).fetchone()[0]

        n = count("SELECT COUNT(*) FROM modules WHERE TRIM(COALESCE(module_code, '')) = ''")
        if n:
            issues.append(f"{n} module(s) have no module code")
        n = count("SELECT COUNT(*) FROM modules WHERE TRIM(COALESCE(module_name, '')) = ''")
        if n:
            issues.append(f"{n} module(s) have no name")
        for code, times in c.execute(
                "SELECT module_code, COUNT(*) FROM modules "
                "GROUP BY module_code HAVING COUNT(*) > 1"):
            issues.append(f"module code {code} appears {times} times")
        n = count("SELECT COUNT(*) FROM modules WHERE COALESCE(is_active, 1) = 1 "
                  "AND COALESCE(credits, 0) <= 0")
        if n:
            issues.append(f"{n} active module(s) have no credit value")
        n = count("SELECT COUNT(DISTINCT sm.module_code) FROM student_modules sm "
                  "LEFT JOIN modules m ON m.module_code = sm.module_code "
                  "WHERE m.module_code IS NULL")
        if n:
            issues.append(f"{n} enrolled module code(s) have no module record")
        if _table_exists(c, "module_schedule"):
            n = count("SELECT COUNT(DISTINCT ms.module_code) FROM module_schedule ms "
                      "LEFT JOIN modules m ON m.module_code = ms.module_code "
                      "WHERE m.module_code IS NULL")
            if n:
                issues.append(f"{n} scheduled module code(s) have no module record")
        if _table_exists(c, "degree_course_prerequisites"):
            n = count("SELECT COUNT(*) FROM degree_course_prerequisites dp "
                      "LEFT JOIN modules m ON m.module_code = dp.prerequisite_module_code "
                      "WHERE m.module_code IS NULL")
            if n:
                issues.append(f"{n} prerequisite rule(s) point at a missing module")
        if _table_exists(c, "course_module_map"):
            known = {r["code"] for r in course_choices(conn=c)}
            missing = {r[0] for r in c.execute("SELECT DISTINCT course_code FROM course_module_map")
                       if r[0] not in known}
            if missing:
                issues.append("programme link(s) to unknown course(s): "
                              + ", ".join(sorted(missing)))
        n = count("SELECT COUNT(*) FROM modules WHERE COALESCE(is_active, 1) = 1 "
                  "AND TRIM(COALESCE(instructor, '')) = '' AND instructor_id IS NULL")
        if n:
            issues.append(f"{n} active module(s) have no instructor")
        from education_system.systems.university.application.modules import (
            enrolment as module_enrolment,
        )
        _ensure_schema(c)
        n = count("SELECT COUNT(*) FROM modules WHERE COALESCE(is_active, 1) = 1 "
                  "AND TRIM(COALESCE(module_code, '')) != '' AND level IS NULL")
        if n:
            issues.append(f"{n} active module(s) have no FHEQ level")
        n = _table_exists(c, "learning_outcomes") and count(
            "SELECT COUNT(*) FROM modules m WHERE COALESCE(m.is_active, 1) = 1 "
            "AND TRIM(COALESCE(m.module_code, '')) != '' AND NOT EXISTS "
            "(SELECT 1 FROM learning_outcomes lo WHERE lo.module_code = m.module_code)")
        if n:
            issues.append(f"{n} active module(s) have no learning outcomes")
        issues += module_enrolment.programme_credit_issues(c)
    return issues
