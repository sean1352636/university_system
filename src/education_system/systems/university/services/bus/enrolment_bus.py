"""Enrolment eligibility rules — the single gate every registration path uses.

Before this module the rules existed but nothing consulted them at the point
of registration:

* ``check_prerequisites`` (``academics.interfaces.gui._cross_services``) was
  only called by assignment submission and the degree-audit "what-if" screens,
  so ``course_prerequisites`` was advisory.
* The capacity check in ``student_registration/enrollment.py`` was dead code
  (``max_capacity = None`` followed by ``if max_capacity:``), and
  ``course_catalog_gui`` silently treated a lookup failure as "uncapped".

The rules live here, in the domain layer, so the GUI paths and the REST route
share one implementation. Each interface decides how to *present* a block:
the student GUI refuses, the catalogue offers the waitlist when the only
block is capacity, staff may override with an audited confirmation, and the
API raises the matching domain exception.

Design notes
------------
The gate covers the registration window (``registration_calendar``),
prerequisites and co-requisites, module capacity, and — where a module runs in
sections — the chosen section's capacity and timetable fit.

* **Fail closed on a rule, open on an outage.** A missing prerequisite is a
  block; an unreadable ``course_prerequisites`` table is not — a schema
  problem must not lock every student out of registration. Outages are logged
  and surface as ``degraded=True`` so a caller can tell the difference.
* **No rules configured means eligible.** ``course_prerequisites`` currently
  holds 0 rows and every ``modules.capacity`` is NULL, so this gate is a
  no-op on today's data. It starts enforcing the moment a rule is entered,
  which is the point.
* Rules key on ``module_code``: that is what ``student_modules`` stores and
  what students actually enrol against.

Placement
---------
This lives in ``services/bus/`` beside ``finance_bus`` rather than inside the
Academics slice for two reasons. The REST route is owned by **Learners**, and
the slice ratchet (``tests/unit/systems/university/domains/conftest.py``)
forbids one domain importing another's package — cross-domain work goes
through a port, which is exactly what ``services/bus`` is. It also keeps the
gate off the ``course_management`` package, whose ``__init__`` eagerly imports
the CLI menu stack (~1.4 s) that would otherwise land on the enrolment path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import (
    sqlite3,
    get_connection,
)
from education_system.systems.university.services.bus.registration_calendar import (
    registration_state,
)

logger = logging.getLogger(__name__)

# Block kinds, so callers can branch without matching on message text.
BLOCK_PREREQUISITE = "prerequisite"
BLOCK_COREQUISITE = "corequisite"
BLOCK_CAPACITY = "capacity"
BLOCK_WINDOW = "window"              # registration is not open at this date
BLOCK_SECTION_REQUIRED = "section_required"   # the module runs in sections
BLOCK_SECTION_CAPACITY = "section_capacity"   # the chosen section is full
BLOCK_SECTION_CLASH = "section_clash"         # it collides with the timetable


@dataclass
class Block:
    """One reason an enrolment is not permitted."""

    kind: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Eligibility:
    """Outcome of the eligibility check for one (student, module) pair."""

    ok: bool
    blocks: list[Block] = field(default_factory=list)
    capacity: Optional[int] = None
    enrolled: int = 0
    degraded: bool = False
    #: Sections to choose from when the module runs in sections.
    sections: list[dict[str, Any]] = field(default_factory=list)
    #: The registration-window verdict that was applied (see registration_calendar).
    window: Optional[dict[str, Any]] = None

    _CAPACITY_KINDS = (BLOCK_CAPACITY, BLOCK_SECTION_CAPACITY)

    @property
    def is_full(self) -> bool:
        return any(b.kind in self._CAPACITY_KINDS for b in self.blocks)

    @property
    def only_capacity(self) -> bool:
        """True when capacity is the *sole* obstacle — the waitlist case."""
        return bool(self.blocks) and all(
            b.kind in self._CAPACITY_KINDS for b in self.blocks
        )

    @property
    def needs_section(self) -> bool:
        """True when the caller must ask the student to choose a section."""
        return any(b.kind == BLOCK_SECTION_REQUIRED for b in self.blocks)

    def reason(self) -> str:
        """A single human-readable summary of every block."""
        return "\n".join(b.message for b in self.blocks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blocks": [
                {"kind": b.kind, "message": b.message, "details": b.details}
                for b in self.blocks
            ],
            "capacity": self.capacity,
            "enrolled": self.enrolled,
            "degraded": self.degraded,
            "sections": self.sections,
            "window": self.window,
        }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def ensure_section_column(conn=None) -> bool:
    """Add ``student_modules.section_id`` when it is missing.

    Nullable by design: enrolment stays module-level (``section_id IS NULL``)
    for every module that has no sections, which is all of them today. Only
    modules that grow sections start requiring one.
    """
    own = conn is None
    try:
        if own:
            conn = get_connection()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(student_modules)")}
        if "section_id" not in cols:
            conn.execute("ALTER TABLE student_modules ADD COLUMN section_id INTEGER")
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("could not ensure student_modules.section_id: %s", exc)
        return False
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

def module_capacity(conn, module_code: str) -> Optional[int]:
    """Return the module's seat limit, or ``None`` when uncapped.

    ``modules.capacity`` is nullable and currently NULL for all 388 rows;
    NULL, 0 and a missing column all mean "no limit".
    """
    try:
        row = conn.execute(
            "SELECT capacity FROM modules WHERE module_code = ?",
            (module_code,),
        ).fetchone()
    except sqlite3.OperationalError:
        # Column absent on an older schema — uncapped rather than an error.
        return None
    if not row:
        return None
    try:
        cap = row["capacity"]
    except (IndexError, KeyError, TypeError):
        cap = row[0]
    if cap is None:
        return None
    try:
        cap = int(cap)
    except (TypeError, ValueError):
        return None
    return cap if cap > 0 else None


def enrolled_count(conn, module_code: str, *, exclude_student: str | int | None = None) -> int:
    """Seats currently taken on *module_code* (status 'Enrolled')."""
    sql = (
        "SELECT COUNT(*) FROM student_modules "
        "WHERE module_code = ? AND status = 'Enrolled'"
    )
    params: list[Any] = [module_code]
    if exclude_student is not None:
        sql += " AND student_id <> ?"
        params.append(str(exclude_student))
    row = conn.execute(sql, params).fetchone()
    return int(row[0]) if row else 0


def _passed_modules(conn, student_id: str | int) -> set[str]:
    """Modules the student has a passing final grade in.

    Pass = any final grade that is not 'F' / NULL, read from either canonical
    grade table. Mirrors the rule ``_cross_services.check_prerequisites``
    already used, so the advisory screens and this gate agree.
    """
    passed: set[str] = set()
    for sql, grade_col in (
        ("SELECT module_code, final_grade FROM module_grades WHERE student_id = ?",
         "final_grade"),
        ("SELECT module_code, grade FROM student_grades "
         "WHERE student_id = ? AND COALESCE(is_final, 1) = 1", "grade"),
    ):
        try:
            for r in conn.execute(sql, (str(student_id),)).fetchall():
                grade = r[grade_col] if hasattr(r, "keys") else r[1]
                code = r["module_code"] if hasattr(r, "keys") else r[0]
                if grade and "F" not in str(grade).upper().split("/")[0]:
                    passed.add(code)
        except sqlite3.OperationalError:
            continue
    return passed


def _currently_enrolled(conn, student_id: str | int) -> set[str]:
    """Modules the student is enrolled in right now (for co-requisites)."""
    try:
        rows = conn.execute(
            "SELECT module_code FROM student_modules "
            "WHERE student_id = ? AND status = 'Enrolled'",
            (str(student_id),),
        ).fetchall()
    except sqlite3.OperationalError:
        return set()
    return {r[0] for r in rows}


def missing_requisites(conn, student_id: str | int, module_code: str) -> tuple[list[dict], list[dict]]:
    """Return ``(missing_prerequisites, missing_corequisites)``.

    A rule flagged ``is_corequisite`` or ``can_be_concurrent`` is satisfied by
    concurrent enrolment; a plain prerequisite needs a completed pass.
    Optional rules (``is_required = 0``) never block.
    """
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name IN ('course_prerequisites', 'degree_course_prerequisites')"
    ).fetchall()}
    rules: list = []
    if "course_prerequisites" in tables:
        rules += conn.execute(
            """
            SELECT cp.prerequisite_module_code AS code,
                   COALESCE(m.module_name, cp.prerequisite_module_code) AS name,
                   cp.min_grade AS min_grade,
                   COALESCE(cp.is_required, 1) AS required,
                   COALESCE(cp.is_corequisite, 0) AS is_coreq,
                   COALESCE(cp.can_be_concurrent, 0) AS concurrent
            FROM course_prerequisites cp
            LEFT JOIN modules m
                   ON m.module_code = cp.prerequisite_module_code
            WHERE cp.module_code = ?
              AND cp.prerequisite_module_code IS NOT NULL
            """,
            (module_code,),
        ).fetchall()
    if "degree_course_prerequisites" in tables:
        # Module-level rules entered in Module Management. course_prerequisites
        # cannot hold them: its course_id/prerequisite_course_id pair is
        # NOT NULL, a foreign key to courses, and UNIQUE.
        rules += conn.execute(
            """
            SELECT dp.prerequisite_module_code AS code,
                   COALESCE(m.module_name, dp.prerequisite_module_code) AS name,
                   dp.min_grade AS min_grade,
                   1 AS required,
                   COALESCE(dp.is_corequisite, 0) AS is_coreq,
                   0 AS concurrent
            FROM degree_course_prerequisites dp
            LEFT JOIN modules m
                   ON m.module_code = dp.prerequisite_module_code
            WHERE dp.module_code = ?
            """,
            (module_code,),
        ).fetchall()
    if not rules:
        return [], []

    passed = _passed_modules(conn, student_id)
    concurrent_ok = _currently_enrolled(conn, student_id)

    missing_pre: list[dict] = []
    missing_co: list[dict] = []
    seen: set[str] = set()
    for rule in rules:
        code = rule["code"]
        if not int(rule["required"] or 0) or code in seen:
            continue
        seen.add(code)
        entry = {
            "code": code,
            "name": rule["name"],
            "min_grade": rule["min_grade"] or "Pass",
        }
        if int(rule["is_coreq"] or 0) or int(rule["concurrent"] or 0):
            # Satisfied by having passed it OR taking it alongside.
            if code not in passed and code not in concurrent_ok:
                missing_co.append(entry)
        elif code not in passed:
            missing_pre.append(entry)
    return missing_pre, missing_co


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def sections_for_module(conn, module_code: str, *, term_id=None) -> list[dict]:
    """Open sections of *module_code*, newest term first.

    ``course_sections`` keys on ``course_code``, which in that table holds the
    code a student registers against. Modules without sections return [], and
    that is the normal case today (1 section row exists in total), so
    section rules stay dormant until sections are actually created.
    """
    try:
        sql = ("SELECT id, course_code, term_id, section_number, instructor, "
               "capacity, delivery_mode, location, status "
               "FROM course_sections WHERE course_code = ? "
               "AND LOWER(COALESCE(status, 'open')) NOT IN ('cancelled', 'closed')")
        params: list[Any] = [module_code]
        if term_id is not None:
            sql += " AND term_id = ?"
            params.append(term_id)
        sql += " ORDER BY term_id DESC, section_number"
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []
    out = []
    for r in rows:
        row = dict(r) if hasattr(r, "keys") else dict(zip(
            ("id", "course_code", "term_id", "section_number", "instructor",
             "capacity", "delivery_mode", "location", "status"), r))
        row["enrolled"] = _section_enrolled(conn, row["id"])
        cap = row.get("capacity") or 0
        row["full"] = bool(cap) and row["enrolled"] >= cap
        out.append(row)
    return out


def _section_enrolled(conn, section_id) -> int:
    """Seats taken on a section (0 when enrolments are not section-aware yet)."""
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM student_modules "
            "WHERE section_id = ? AND status = 'Enrolled'",
            (section_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0]) if row else 0


def _section_meetings(conn, section_id) -> list[dict]:
    try:
        rows = conn.execute(
            "SELECT day_of_week, start_time, end_time, location "
            "FROM section_meetings WHERE section_id = ?",
            (section_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(r) if hasattr(r, "keys") else dict(zip(
        ("day_of_week", "start_time", "end_time", "location"), r)) for r in rows]


def _overlaps(a: dict, b: dict) -> bool:
    """Do two meetings collide? Same day and overlapping times."""
    if not a.get("day_of_week") or not b.get("day_of_week"):
        return False
    if str(a["day_of_week"]).strip().lower()[:3] != str(b["day_of_week"]).strip().lower()[:3]:
        return False
    a_start, a_end = str(a.get("start_time") or ""), str(a.get("end_time") or "")
    b_start, b_end = str(b.get("start_time") or ""), str(b.get("end_time") or "")
    if not (a_start and a_end and b_start and b_end):
        return False
    return a_start < b_end and b_start < a_end


def section_clashes(conn, student_id, section_id) -> list[dict]:
    """Meetings of the student's existing sections that collide with this one."""
    candidate = _section_meetings(conn, section_id)
    if not candidate:
        return []
    try:
        held = conn.execute(
            "SELECT sm.section_id, sm.module_code, cs.section_number "
            "FROM student_modules sm "
            "LEFT JOIN course_sections cs ON cs.id = sm.section_id "
            "WHERE sm.student_id = ? AND sm.status = 'Enrolled' "
            "AND sm.section_id IS NOT NULL AND sm.section_id <> ?",
            (str(student_id), section_id),
        ).fetchall()
    except sqlite3.OperationalError:
        return []

    clashes = []
    for row in held:
        other_id = row[0] if not hasattr(row, "keys") else row["section_id"]
        module = row[1] if not hasattr(row, "keys") else row["module_code"]
        for existing in _section_meetings(conn, other_id):
            for want in candidate:
                if _overlaps(existing, want):
                    clashes.append({
                        "module_code": module,
                        "section_id": other_id,
                        "day": want.get("day_of_week"),
                        "time": f"{want.get('start_time')}–{want.get('end_time')}",
                    })
                    break
    return clashes


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def check_enrolment_eligibility(
    student_id: str | int,
    module_code: str,
    *,
    section_id=None,
    when=None,
    term_id=None,
    conn=None,
) -> Eligibility:
    """Evaluate every enrolment rule for *student_id* on *module_code*.

    Rules applied, in the order a registry would apply them: the registration
    window for the date, prerequisites and co-requisites, module capacity,
    and — when the module runs in sections — the chosen section's capacity and
    timetable fit. ``section_id`` names the section being joined; ``when``
    overrides today's date (for testing and for backdated registry work).

    Pass an open ``conn`` to run inside a caller's transaction; otherwise a
    connection is opened and closed here.

    Never raises: an infrastructure failure is logged and returned as
    ``ok=True, degraded=True`` so a broken table cannot block registration.
    """
    result = Eligibility(ok=True)
    if not student_id or not module_code:
        return result

    own_conn = conn is None
    try:
        if own_conn:
            conn = get_connection()

        # 1. Is registration open at all on this date?
        window = registration_state(when=when, term_id=term_id, conn=conn)
        result.window = window
        if not window["open"]:
            result.blocks.append(Block(
                BLOCK_WINDOW, window["reason"],
                {"phase": window["phase"], "deadline": window["deadline"]},
            ))
        # 2. Module capacity. Excluding the student keeps a re-enrolment from
        #    counting itself.
        cap = module_capacity(conn, module_code)
        taken = enrolled_count(conn, module_code, exclude_student=student_id)
        result.capacity = cap
        result.enrolled = taken

        missing_pre, missing_co = missing_requisites(conn, student_id, module_code)

        if missing_pre:
            names = ", ".join(m["code"] for m in missing_pre)
            result.blocks.append(Block(
                BLOCK_PREREQUISITE,
                f"Missing required prerequisite(s): {names}",
                {"missing": missing_pre},
            ))
        if missing_co:
            names = ", ".join(m["code"] for m in missing_co)
            result.blocks.append(Block(
                BLOCK_COREQUISITE,
                f"Missing co-requisite(s) — must be taken concurrently: {names}",
                {"missing": missing_co},
            ))
        if cap is not None and taken >= cap:
            result.blocks.append(Block(
                BLOCK_CAPACITY,
                f"{module_code} is full ({taken}/{cap}).",
                {"capacity": cap, "enrolled": taken},
            ))

        # 3. Sections, when the module runs in them. A module with no sections
        #    behaves exactly as before: nothing to choose, nothing to check.
        #    The column check is a PRAGMA, and only writes on the first run.
        ensure_section_column(conn)
        sections = sections_for_module(conn, module_code, term_id=term_id)
        result.sections = sections
        if sections:
            chosen = None
            if section_id is not None:
                chosen = next(
                    (s for s in sections if str(s["id"]) == str(section_id)), None)
            if chosen is None:
                if section_id is not None:
                    result.blocks.append(Block(
                        BLOCK_SECTION_REQUIRED,
                        f"Section {section_id} is not an open section of {module_code}.",
                        {"sections": sections},
                    ))
                else:
                    labels = ", ".join(str(s["section_number"]) for s in sections)
                    result.blocks.append(Block(
                        BLOCK_SECTION_REQUIRED,
                        f"{module_code} runs in sections — choose one ({labels}).",
                        {"sections": sections},
                    ))
            else:
                sec_cap = chosen.get("capacity") or 0
                sec_taken = chosen["enrolled"]
                if sec_cap and sec_taken >= sec_cap:
                    result.blocks.append(Block(
                        BLOCK_SECTION_CAPACITY,
                        f"Section {chosen['section_number']} of {module_code} is full "
                        f"({sec_taken}/{sec_cap}).",
                        {"section_id": chosen["id"], "capacity": sec_cap,
                         "enrolled": sec_taken},
                    ))
                clashes = section_clashes(conn, student_id, chosen["id"])
                if clashes:
                    detail = "; ".join(
                        f"{c['module_code']} ({c['day']} {c['time']})" for c in clashes)
                    result.blocks.append(Block(
                        BLOCK_SECTION_CLASH,
                        f"Section {chosen['section_number']} clashes with: {detail}.",
                        {"clashes": clashes},
                    ))

        result.ok = not result.blocks
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "check_enrolment_eligibility(%s, %s) failed: %s — allowing enrolment",
            student_id, module_code, exc,
        )
        result.ok = True
        result.blocks = []
        result.degraded = True
    finally:
        if own_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
    return result
