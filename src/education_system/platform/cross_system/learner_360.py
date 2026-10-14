"""Learner 360 — one learner's whole record, every system, one call.

:func:`build_learner_360` assembles, for a canonical ``journey_id``:

==================  ====================================================
Section             Source
==================  ====================================================
overview            ``student_journey`` (canonical demographics)
current_education   open ``learner_enrolment`` rows
records             each local record the learner has had, read from
                    its system DB (every spell, not just the slot)
timeline            enrolments, year-group history, ``learner_transition``,
                    ``student_journey_transitions``, awards, merges
qualifications      :mod:`qualifications` (persisted + derivable)
attendance          per-system attendance tables via ``SYSTEM_DB_PATHS``
achievements        house points (primary), achievements (university)
progression         current phase, recommended next, transitions
transfers           completed moves and within-phase transfers
documents           links only — ids and titles, never content or paths
support             flags and counts only; safeguarding a count, gated
system_access       logins linked through ``users.journey_id``
lineage             which system and table every row came from
==================  ====================================================

The timeline and records walk the *enrolment history*, so a second spell
in the same phase (a second primary school, a returning learner) is
visible; the old view walked the per-phase slots and could only ever show
the latest.

Sensitivity follows the rules already in ``student_view`` and
``handover``: safeguarding and welfare never show detail anywhere (at most
a count, to a safeguarding role); an apprentice's portfolio, reviews and
formative judgements are never read — only the published EPA outcome
crosses. Sections a viewer may not see are ``None`` and listed in
``restricted_sections``; an unknown role gets the narrowest view.

Read-only and defensive throughout: a missing database, table or column
degrades to a partial view, never an error.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from education_system.paths import (
    SYSTEM_DB_PATHS,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
    learner_table,
)
from education_system.platform.cross_system import (
    enrolments,
    identity_service,
    person,
    qualifications,
)
from education_system.platform.cross_system.enrolment_schema import (
    OPEN_STATUSES,
)
from education_system.platform.identity.auth.db import connect as _auth_connect

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Viewer policy
# ---------------------------------------------------------------------------

#: Staff of any system: everything except safeguarding/welfare detail.
STAFF_ROLES: frozenset[str] = frozenset({
    "admin", "superadmin", "staff", "teacher", "tutor", "lecturer",
    "head", "headteacher", "senco", "pastoral", "registrar", "manager",
    "dsl", "designated_safeguarding_lead", "safeguarding_lead", "deputy_dsl",
})
#: May see that open safeguarding alerts exist — a count, never content.
SAFEGUARDING_ROLES: frozenset[str] = frozenset({
    "admin", "superadmin", "dsl", "designated_safeguarding_lead",
    "safeguarding_lead", "deputy_dsl",
})
#: The learner, or their parent/guardian: their own record, less the
#: identifiers and support flags that are staff business.
SELF_ROLES: frozenset[str] = frozenset({
    "student", "learner", "pupil", "apprentice", "parent", "guardian",
})
#: Parties outside the education provider (an apprentice's employer, the
#: end-point assessment organisation) — and any role we do not recognise.
EXTERNAL_TIER = "external"

SECTION_TITLES: tuple[tuple[str, str], ...] = (
    ("overview", "Overview"),
    ("current_education", "Current education"),
    ("records", "Records"),
    ("timeline", "Timeline"),
    ("qualifications", "Qualifications"),
    ("attendance", "Attendance"),
    ("achievements", "Achievements"),
    ("progression", "Progression"),
    ("transfers", "Transfers"),
    ("documents", "Documents"),
    ("support", "Support"),
    ("system_access", "System access"),
    ("lineage", "Lineage"),
)

# tier -> sections visible. ``internal`` is a trusted platform caller that
# passed no viewer (the pre-existing build_overview contract).
_VISIBLE: dict[str, frozenset[str]] = {
    "internal": frozenset(s for s, _t in SECTION_TITLES),
    "staff": frozenset(s for s, _t in SECTION_TITLES),
    "self": frozenset(s for s, _t in SECTION_TITLES) - {"lineage", "support"},
    EXTERNAL_TIER: frozenset({"overview", "current_education",
                              "qualifications", "attendance"}),
}

# Local record fields that are special-category or support data. Staff
# see them on the record; the learner/parent view and external parties do
# not, and they never leave the record for the bus or the timeline.
_SENSITIVE_RECORD_FIELDS = frozenset({
    "send_status", "sen_status", "has_ehcp", "learning_support",
    "support_needs", "medical_notes", "allergies",
})

# Document categories whose title alone can disclose safeguarding, welfare
# or health detail. Withheld from every viewer; a safeguarding role is told
# how many were withheld.
_SENSITIVE_DOC = re.compile(
    r"safeguard|welfare|medical|health|disclos|child.?protection|"
    r"counsel|referral|wellbeing", re.IGNORECASE)


def viewer_tier(viewer_role: str | None) -> str:
    """Map a role to a visibility tier: internal/staff/self/external."""
    if viewer_role is None:
        return "internal"
    role = str(viewer_role).strip().lower()
    if role in STAFF_ROLES:
        return "staff"
    if role in SELF_ROLES:
        return "self"
    return EXTERNAL_TIER


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _connect(path) -> sqlite3.Connection | None:
    """Read-only connection, or None if the database does not exist.

    ``mode=ro`` so a view can never create, lock or write a system DB.
    """
    if not path or not Path(path).exists():
        return None
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro",
                           uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _columns(conn, table) -> set[str]:
    try:
        return {r[1] for r in conn.execute(
            f"PRAGMA table_info({table})").fetchall()}  # nosec B608 - fixed names
    except sqlite3.Error:
        return set()


def _table_exists(conn, table) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)).fetchone() is not None


def _record(conn, table, pk_col, student_id, fields) -> dict:
    """Return the subset of ``fields`` actually present on a row."""
    cols = _columns(conn, table)
    present = [f for f in fields if f in cols]
    if not present or pk_col not in cols:
        return {}
    row = conn.execute(
        f"SELECT {', '.join(present)} FROM {table} WHERE {pk_col} = ?",  # nosec B608
        (student_id,)).fetchone()
    return {k: row[k] for k in present} if row else {}


# Marks that count as present across the systems' vocabularies: DfE
# register codes (/ \ L and the approved-activity codes), and the words.
_PRESENT_MARKS = frozenset({
    "/", "\\", "l", "p", "b", "d", "j", "k", "v", "w",
    "present", "late", "attended", "on time", "remote",
})


def _attendance_summary(conn, table, student_col, student_id,
                        mark_col) -> dict | None:
    """Count attendance rows grouped by their mark/status code."""
    if not _table_exists(conn, table):
        return None
    cols = _columns(conn, table)
    if student_col not in cols or mark_col not in cols:
        return None
    rows = conn.execute(
        f"SELECT {mark_col} AS mark, COUNT(*) AS n FROM {table} "  # nosec B608
        f"WHERE {student_col} = ? GROUP BY {mark_col}",
        (student_id,)).fetchall()
    by_mark = {(r["mark"] or "?"): r["n"] for r in rows}
    total = sum(by_mark.values())
    if not total:
        return None
    present = sum(n for m, n in by_mark.items()
                  if str(m).strip().lower() in _PRESENT_MARKS)
    return {"total": total, "by_mark": by_mark,
            "present_pct": round(present / total * 100, 1)}


# system -> (table, learner column, mark column)
ATTENDANCE_SOURCES: dict[str, tuple[str, str, str]] = {
    "nursery": ("attendance_records", "pupil_id", "status"),
    "primary": ("attendance_records", "pupil_id", "mark"),
    "secondary": ("attendance_records", "pupil_id", "mark"),
    "sixth_form": ("attendance_records", "student_id", "status"),
    "fe_college": ("attendance", "student_id", "mark"),
    "apprenticeships": ("session_attendance", "apprentice_id", "mark"),
    "university": ("attendance", "student_id", "status"),
}


def _attendance_for(system, conn, sid) -> dict | None:
    spec = ATTENDANCE_SOURCES.get(system)
    return _attendance_summary(conn, spec[0], spec[1], sid, spec[2]) if spec else None


# ---------------------------------------------------------------------------
# Per-system record extractors — each returns {record, attendance, results}
# ---------------------------------------------------------------------------

def _phase_nursery(conn, sid) -> dict:
    return {
        "record": _record(conn, "pupils", "pupil_id", sid, [
            "first_name", "last_name", "date_of_birth", "room",
            "key_person", "start_date", "status"]),
        "attendance": _attendance_for("nursery", conn, sid),
    }


def _phase_primary(conn, sid) -> dict:
    return {
        "record": _record(conn, "pupils", "pupil_id", sid, [
            "first_name", "last_name", "date_of_birth", "year_group",
            "class_name", "send_status", "email", "roll_status"]),
        "attendance": _attendance_for("primary", conn, sid),
    }


def _phase_secondary(conn, sid) -> dict:
    out: dict = {
        "record": _record(conn, "pupils", "pupil_id", sid, [
            "first_name", "last_name", "date_of_birth", "year_group",
            "form_group", "send_status", "email", "roll_status"]),
        "attendance": _attendance_for("secondary", conn, sid),
    }
    if _table_exists(conn, "gradebook_entries"):
        rows = conn.execute(
            "SELECT subject_id, assessment_name, assessment_date, "
            "mark_pct, grade FROM gradebook_entries WHERE pupil_id = ? "
            "ORDER BY assessment_date DESC LIMIT 10", (sid,)).fetchall()
        out["results"] = [dict(r) for r in rows]
    return out


def _phase_college(conn, sid) -> dict:
    out: dict = {
        "record": _record(conn, "students", "student_id", sid, [
            "first_name", "middle_name", "last_name", "date_of_birth",
            "subject_1", "subject_2", "subject_3", "status", "email"]),
        "attendance": _attendance_for("sixth_form", conn, sid),
    }
    if _table_exists(conn, "mock_results") and _table_exists(conn, "mock_exams"):
        rows = conn.execute(
            "SELECT m.subject, m.title, m.date_sat, m.max_marks, "
            "r.marks, r.grade FROM mock_results r "
            "JOIN mock_exams m ON m.mock_id = r.mock_id "
            "WHERE r.student_id = ? ORDER BY m.date_sat DESC LIMIT 10",
            (sid,)).fetchall()
        out["results"] = [dict(r) for r in rows]
    return out


def _phase_university(conn, sid) -> dict:
    out: dict = {
        "record": _record(conn, "students", "student_id", sid, [
            "first_name", "last_name", "date_of_birth", "course",
            "status", "email", "enrollment_date"]),
        "attendance": _attendance_for("university", conn, sid),
    }
    # University grade tables vary; surface whichever common one exists.
    for table, cols in (
        ("grades", "module_id, grade, score, graded_at"),
        ("enrollments", "module_id, status, grade"),
    ):
        if _table_exists(conn, table) and "student_id" in _columns(conn, table):
            present = [c.strip() for c in cols.split(",")
                       if c.strip() in _columns(conn, table)]
            if present:
                rows = conn.execute(
                    f"SELECT {', '.join(present)} FROM {table} "  # nosec B608
                    "WHERE student_id = ? LIMIT 20", (sid,)).fetchall()
                out["results"] = [dict(r) for r in rows]
                break
    return out


def _phase_fe_college(conn, sid) -> dict:
    out: dict = {
        "record": _record(conn, "students", "student_id", sid, [
            "first_name", "last_name", "date_of_birth", "learner_type",
            "mode_of_study", "tutor_group", "status", "email"]),
        "attendance": _attendance_for("fe_college", conn, sid),
    }
    # An FE learner's "results" are their learning aims and the grades
    # against them, which is the vocational equivalent of a result set.
    if _table_exists(conn, "enrolments"):
        rows = conn.execute(
            "SELECT c.title AS course, e.academic_year, e.status, "
            "e.predicted_grade, e.final_grade FROM enrolments e "
            "LEFT JOIN courses c ON c.course_id = e.course_id "
            "WHERE e.student_id = ? "
            "ORDER BY e.is_main_aim DESC, e.academic_year DESC LIMIT 10",
            (sid,)).fetchall()
        out["results"] = [dict(r) for r in rows]
    return out


def _phase_apprenticeships(conn, sid) -> dict:
    """The apprentice's record, off-the-job attendance and EPA outcome.

    Deliberately does not surface portfolio evidence or formative
    judgements: this view is read by staff across the whole platform, and
    the provider's in-progress assessment of an apprentice is not theirs
    to see. The EPA grade is the published outcome and does cross.
    """
    out: dict = {
        "record": _record(conn, "apprentices", "apprentice_id", sid, [
            "given_name", "family_name", "date_of_birth", "uln", "status",
            "start_date", "planned_end_date", "actual_end_date",
            "weekly_hours", "email"]),
        "attendance": _attendance_for("apprenticeships", conn, sid),
    }
    if _table_exists(conn, "epa_results"):
        rows = conn.execute(
            "SELECT method, grade, assessed_date, attempt FROM epa_results "
            "WHERE apprentice_id = ? ORDER BY assessed_date DESC LIMIT 10",
            (sid,)).fetchall()
        out["results"] = [dict(r) for r in rows]
    # The employer is half of an apprenticeship; a view that omits it
    # describes a course, not an apprenticeship.
    if _table_exists(conn, "employers"):
        row = conn.execute(
            "SELECT e.name FROM apprentices a "
            "JOIN employers e ON e.employer_id = a.employer_id "
            "WHERE a.apprentice_id = ?", (sid,)).fetchone()
        if row is not None:
            out["record"]["employer"] = row["name"]
    return out


PHASE_EXTRACTORS = {
    "nursery":    _phase_nursery,
    "primary":    _phase_primary,
    "secondary":     _phase_secondary,
    "sixth_form":    _phase_college,
    "fe_college": _phase_fe_college,
    "apprenticeships": _phase_apprenticeships,
    "university": _phase_university,
}


# ---------------------------------------------------------------------------
# Achievements, documents, support flags (per system DB)
# ---------------------------------------------------------------------------

def _achievements(system, conn, sid) -> dict | None:
    if system == "primary" and {"pupil_id", "points"} <= _columns(
            conn, "house_point_awards"):
        agg = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(points), 0) AS pts "
            "FROM house_point_awards WHERE pupil_id = ?", (sid,)).fetchone()
        if agg["n"]:
            recent = conn.execute(
                "SELECT awarded_on, points, reason FROM house_point_awards "
                "WHERE pupil_id = ? ORDER BY awarded_on DESC LIMIT 5",
                (sid,)).fetchall()
            return {"kind": "house_points", "count": agg["n"],
                    "total_points": agg["pts"],
                    "recent": [dict(r) for r in recent]}
    if system == "university" and {"student_id", "title"} <= _columns(
            conn, "achievements"):
        rows = conn.execute(
            "SELECT title, achievement_type, date_achieved, points "
            "FROM achievements WHERE student_id = ? "
            "ORDER BY date_achieved DESC", (sid,)).fetchall()
        if rows:
            return {"kind": "achievements", "count": len(rows),
                    "total_points": sum((r["points"] or 0) for r in rows),
                    "recent": [dict(r) for r in rows[:5]]}
    return None


# system -> (table, learner col, id col, title col, category col)
_DOCUMENT_SOURCES: dict[str, tuple[str, str, str, str, str]] = {
    "apprenticeships": ("documents", "apprentice_id", "document_id",
                        "title", "category"),
    "university": ("documents", "owner_id", "document_id",
                   "document_name", "document_type"),
}


def _documents(system, conn, sid) -> tuple[list[dict], int]:
    """(links, withheld count). Never file paths, names on disk or bytes."""
    spec = _DOCUMENT_SOURCES.get(system)
    if not spec:
        return [], 0
    table, learner_col, id_col, title_col, cat_col = spec
    cols = _columns(conn, table)
    if not {learner_col, id_col} <= cols:
        return [], 0
    title = title_col if title_col in cols else "NULL"
    cat = cat_col if cat_col in cols else "NULL"
    created = "created_at" if "created_at" in cols else "NULL"
    extra = ""
    if system == "university" and "owner_type" in cols:
        extra = " AND COALESCE(owner_type, 'student') = 'student'"
    rows = conn.execute(
        f"SELECT {id_col} AS doc_id, {title} AS title, {cat} AS category, "  # nosec B608
        f"{created} AS created_at FROM {table} WHERE {learner_col} = ?{extra} "
        f"ORDER BY {id_col} DESC LIMIT 50", (sid,)).fetchall()
    links, withheld = [], 0
    for r in rows:
        if _SENSITIVE_DOC.search(f"{r['category'] or ''} {r['title'] or ''}"):
            withheld += 1
            continue
        links.append({"system": system, "document_id": r["doc_id"],
                      "title": r["title"], "category": r["category"],
                      "created_at": r["created_at"],
                      "link": f"{system}:{table}:{r['doc_id']}"})
    return links, withheld


def _support_flags(system, conn, sid, record: dict) -> tuple[list[str], dict]:
    """Flag names and counts — never the detail behind them."""
    flags: list[str] = []
    counts: dict[str, int] = {}
    send = str(record.get("send_status") or "").strip().lower()
    if send and send not in ("none", "n", "no", "0", "false"):
        flags.append("SEND support recorded")
    if system == "fe_college":
        row = _record(conn, "students", "student_id", sid,
                      ["has_ehcp", "learning_support"])
        if row.get("has_ehcp"):
            flags.append("EHCP")
        if str(row.get("learning_support") or "").strip():
            flags.append("Learning support recorded")
        if {"student_id", "status"} <= _columns(conn, "support_plans"):
            n = conn.execute(
                "SELECT COUNT(*) FROM support_plans WHERE student_id = ? "
                "AND status IN ('proposed', 'active', 'under_review')",
                (sid,)).fetchone()[0]
            if n:
                counts["open_support_plans"] = n
    if system == "apprenticeships":
        row = _record(conn, "apprentices", "apprentice_id", sid,
                      ["support_needs"])
        if str(row.get("support_needs") or "").strip():
            flags.append("Support needs recorded")
    return flags, counts


# ---------------------------------------------------------------------------
# auth.db reads
# ---------------------------------------------------------------------------

def _auth_rows(auth_db, sql: str, args: tuple) -> list[dict]:
    conn = _auth_connect(auth_db)
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _legacy_transitions(journey_id, auth_db) -> list[dict]:
    return _auth_rows(
        auth_db,
        "SELECT from_system, to_system, reason, occurred_at "
        "FROM student_journey_transitions WHERE journey_id = ? "
        "ORDER BY occurred_at, id", (journey_id,))


def _workflow_transitions(journey_id, auth_db) -> list[dict]:
    # Named columns only: handover_json and consent_reference stay out of
    # every view — the handover belongs to the destination's admissions.
    return _auth_rows(
        auth_db,
        "SELECT transition_id, source_system, destination_system, status, "
        "initiated_at, completed_at, reason, cancelled_reason, "
        "application_reference, source_enrolment_id, destination_enrolment_id "
        "FROM learner_transition WHERE journey_id = ? ORDER BY initiated_at",
        (journey_id,))


def _open_safeguarding_alerts(journey_id, auth_db) -> int:
    rows = _auth_rows(
        auth_db, "SELECT COUNT(*) AS n FROM safeguarding_alerts "
        "WHERE journey_id = ? AND status = 'open'", (journey_id,))
    return int(rows[0]["n"]) if rows else 0


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _label(system: str | None) -> str:
    return SYSTEM_LABELS.get(system or "", (system or "").replace("_", " ").title())


def _current_education(rows: list[dict], journey: dict) -> dict:
    open_rows = [r for r in rows if r["status"] in OPEN_STATUSES]
    if not rows and journey.get("current_system") in identity_service.SYSTEM_SLOTS:
        # Pre-enrolment data: the slot is all there is.
        system = journey["current_system"]
        sid = journey.get(identity_service.SYSTEM_SLOTS[system][1])
        open_rows = [{"enrolment_id": None, "system": system,
                      "local_student_id": sid, "status": "active",
                      "source_system": "student_journey slot"}]

    def view(r: dict) -> dict:
        return {
            "enrolment_id": r.get("enrolment_id"),
            "system": r["system"], "label": _label(r["system"]),
            "institution": r.get("institution_id") or _label(r["system"]),
            "institution_id": r.get("institution_id"),
            "local_student_id": r.get("local_student_id"),
            "status": r.get("status"), "programme": r.get("programme"),
            "year_group": r.get("year_group"),
            "start_date": r.get("start_date"),
            "source_system": r.get("source_system") or r["system"],
        }

    active = [view(r) for r in open_rows if r.get("status") == "active"]
    pending = [view(r) for r in open_rows if r.get("status") != "active"]
    return {"active": active, "pending": pending,
            "institutions": sorted({a["institution"] for a in active})}


def _timeline(rows, year_history, workflow, legacy, quals, merges) -> list[dict]:
    events: list[dict] = []

    def add(date, kind, system, detail, source):
        events.append({"date": (str(date) if date else None), "kind": kind,
                       "system": system, "label": _label(system),
                       "detail": detail, "source": source})

    for r in rows:
        src = f"learner_enrolment:{r['enrolment_id']}"
        bits = [r.get("programme"), r.get("institution_id"),
                f"Year {r['year_group']}" if r.get("year_group") else None]
        add(r.get("start_date") or r.get("created_at"), "enrolment_started",
            r["system"], " · ".join(b for b in bits if b) or "enrolled", src)
        if r["status"] not in OPEN_STATUSES:
            detail = r["status"]
            if r.get("exit_reason"):
                detail += f" — {r['exit_reason']}"
            if r.get("outcome"):
                detail += f" (outcome: {r['outcome']})"
            add(r.get("end_date") or r.get("updated_at"), "enrolment_ended",
                r["system"], detail, src)
    for h in year_history:
        add(h.get("recorded_at"), "year_group", h.get("system"),
            f"{h['change_type']}: {h.get('from_year_group') or '—'} → "
            f"{h['to_year_group']}"
            + (f" ({h['academic_year']})" if h.get("academic_year") else ""),
            f"enrolment_year_history:{h['history_id']}")
    for t in workflow:
        add(t.get("initiated_at"), "transition", t.get("destination_system"),
            f"{_label(t.get('source_system'))} → "
            f"{_label(t.get('destination_system'))}: {t.get('status')}",
            f"learner_transition:{t['transition_id']}")
    for t in legacy:
        add(t.get("occurred_at"), "move", t.get("to_system"),
            f"{_label(t.get('from_system')) if t.get('from_system') else '(entry)'}"
            f" → {_label(t.get('to_system'))}"
            + (f" · {t['reason']}" if t.get("reason") else ""),
            "student_journey_transitions")
    for q in quals:
        if q.get("awarded_on"):
            add(q["awarded_on"], "qualification", q.get("source_system"),
                f"{q.get('title')}" + (f" — {q['grade']}" if q.get("grade") else ""),
                q.get("source_ref") or "learner_qualification")
    for m in merges:
        add(m.get("merged_at"), "identity_merge", None,
            f"duplicate journey {m.get('duplicate_id')} merged in",
            f"student_journey_merges:{m.get('merge_id')}")
    events.sort(key=lambda e: (e["date"] is None, e["date"] or ""))
    return events


def _transfers(rows, workflow, legacy) -> list[dict]:
    out = []
    for t in workflow:
        if t.get("status") == "completed":
            out.append({"date": t.get("completed_at"),
                        "from_system": t.get("source_system"),
                        "to_system": t.get("destination_system"),
                        "kind": "progression", "reason": t.get("reason"),
                        "source": f"learner_transition:{t['transition_id']}"})
    for t in legacy:
        out.append({"date": t.get("occurred_at"),
                    "from_system": t.get("from_system"),
                    "to_system": t.get("to_system"), "kind": "move",
                    "reason": t.get("reason"),
                    "source": "student_journey_transitions"})
    for r in rows:
        if r["status"] == "transferred":
            out.append({"date": r.get("end_date") or r.get("updated_at"),
                        "from_system": r["system"], "to_system": None,
                        "kind": "left institution",
                        "institution_id": r.get("institution_id"),
                        "reason": r.get("exit_reason"),
                        "source": f"learner_enrolment:{r['enrolment_id']}"})
    out.sort(key=lambda t: str(t.get("date") or ""))
    return out


_TRANSITION_EVENT_FIELDS = ("step", "from_status", "actor", "at",
                            "effective_date", "released_fields",
                            "withheld_fields")


def _destinations(journey_id: str, auth_db, *, staffish: bool) -> list[dict]:
    try:
        from education_system.platform.cross_system import destinations
        rows = destinations.destinations_for(journey_id, db_path=auth_db)
    except Exception:
        logger.debug("Destination read failed for %s", journey_id,
                     exc_info=True)
        return []
    # Free-text notes are staff business; the destination itself is not.
    return [r if staffish else {k: v for k, v in r.items() if k != "notes"}
            for r in rows]


def _progression(journey: dict, workflow: list[dict], auth_db, *,
                 staffish: bool, destinations: list[dict]) -> dict:
    current = journey.get("current_system")
    recommended = None
    try:
        from education_system.platform.cross_system import progression
        recommended = progression.next_phase(current) if current else None
    except Exception:
        logger.debug("next_phase lookup failed", exc_info=True)
    try:
        from education_system.platform.cross_system import transitions
        for t in workflow:
            fields = _TRANSITION_EVENT_FIELDS + (("note",) if staffish else ())
            # Field *keys* released/withheld only — never handover values.
            t["events"] = [
                {k: e.get(k) for k in fields}
                for e in transitions.list_transition_events(
                    t["transition_id"], db_path=auth_db)]
    except Exception:
        logger.debug("Transition event read failed", exc_info=True)
    live = [t for t in workflow
            if t.get("status") not in ("completed", "cancelled")]
    return {
        "current_system": current, "current_label": _label(current),
        "recommended_next": recommended,
        "recommended_label": _label(recommended) if recommended else None,
        "open_transitions": live,
        "completed": [t for t in workflow if t.get("status") == "completed"],
        "cancelled": [t for t in workflow if t.get("status") == "cancelled"],
        "destinations": destinations,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_learner_360(journey_id: str, *, viewer_role: str | None = None,
                      viewer_system: str | None = None,
                      db_paths: dict | None = None,
                      auth_db: str | None = None) -> dict:
    """Assemble one learner's Learner 360 (see the module docstring).

    ``viewer_role`` selects the visibility tier (``None`` = trusted
    platform caller). ``viewer_system`` marks each record/attendance row
    with ``cross_system`` so a screen can show what came from elsewhere.
    ``db_paths`` / ``auth_db`` override the registry locations (tests).
    """
    paths = db_paths if db_paths is not None else SYSTEM_DB_PATHS
    resolved = identity_service.resolve_journey_id(journey_id, db_path=auth_db)
    journey = identity_service.get(resolved, db_path=auth_db) if resolved else None
    if journey is None:
        return {"journey_id": journey_id, "found": False}
    jid = journey["journey_id"]
    tier = viewer_tier(viewer_role)
    visible = _VISIBLE[tier]
    can_see_safeguarding = (viewer_role or "").strip().lower() in SAFEGUARDING_ROLES
    staffish = tier in ("internal", "staff")

    rows = enrolments.list_enrolments(jid, db_path=auth_db)
    year_history = enrolments.year_group_history(journey_id=jid,
                                                 db_path=auth_db)
    workflow = _workflow_transitions(jid, auth_db)
    legacy = _legacy_transitions(jid, auth_db)
    merges = [m for m in identity_service.list_merges(jid, db_path=auth_db)
              if m.get("survivor_id") == jid]
    lineage: list[dict] = [
        {"section": "enrolments", "system": r["system"],
         "source_system": r.get("source_system") or r["system"],
         "source": f"auth.db:learner_enrolment:{r['enrolment_id']}",
         "local_student_id": r.get("local_student_id")} for r in rows]

    # ── Per-record reads: one connection per system DB ─────────────────
    records, attendance, achievements, documents = [], [], [], []
    support_flags: list[dict] = []
    support_counts: dict[str, int] = {}
    withheld_docs = 0
    by_system: dict[str, list[str]] = {}
    for system, local_id in person.all_local_records(jid, db_path=auth_db):
        by_system.setdefault(system, []).append(local_id)
    spells = {}
    for r in rows:
        spells.setdefault((r["system"], str(r.get("local_student_id") or "")),
                          []).append(r)
    for system in SYSTEM_ORDER:
        ids = by_system.get(system)
        if not ids:
            continue
        conn = _connect(paths.get(system))
        try:
            for sid in ids:
                phase: dict[str, Any] = {
                    "system": system, "label": _label(system),
                    "student_id": sid, "record": {},
                    "enrolment_ids": [e["enrolment_id"]
                                      for e in spells.get((system, sid), [])],
                    "statuses": [e["status"]
                                 for e in spells.get((system, sid), [])],
                }
                if viewer_system:
                    phase["cross_system"] = system != viewer_system
                if conn is not None:
                    try:
                        phase.update(PHASE_EXTRACTORS[system](conn, sid))
                    except Exception:
                        logger.debug("Record extract failed for %s/%s",
                                     system, sid, exc_info=True)
                    try:
                        ach = _achievements(system, conn, sid)
                        if ach:
                            achievements.append({"system": system,
                                                 "label": _label(system),
                                                 "student_id": sid, **ach})
                        links, held = _documents(system, conn, sid)
                        documents.extend(links)
                        withheld_docs += held
                        flags, counts = _support_flags(
                            system, conn, sid, phase.get("record") or {})
                        support_flags += [{"system": system, "flag": f}
                                          for f in flags]
                        for k, v in counts.items():
                            support_counts[k] = support_counts.get(k, 0) + v
                    except Exception:
                        logger.debug("Secondary extract failed for %s/%s",
                                     system, sid, exc_info=True)
                phase = {k: v for k, v in phase.items() if v is not None}
                if not staffish:
                    phase["record"] = {
                        k: v for k, v in (phase.get("record") or {}).items()
                        if k not in _SENSITIVE_RECORD_FIELDS}
                records.append(phase)
                lineage.append({
                    "section": "records", "system": system,
                    "source_system": system,
                    "source": f"{system}:{learner_table(system)[0]}",
                    "local_student_id": sid})
                if phase.get("attendance"):
                    attendance.append({
                        "system": system, "label": _label(system),
                        "student_id": sid, **phase["attendance"],
                        **({"cross_system": system != viewer_system}
                           if viewer_system else {})})
                    lineage.append({
                        "section": "attendance", "system": system,
                        "source_system": system,
                        "source": f"{system}:{ATTENDANCE_SOURCES[system][0]}",
                        "local_student_id": sid})
        finally:
            if conn is not None:
                conn.close()

    quals = qualifications.collect_for_journey(jid, db_paths=paths,
                                               db_path=auth_db)
    if not staffish:
        # Results derived from a handover payload are shown to staff only;
        # anyone else reads a handover through transitions.get_handover_for,
        # which applies the per-field consent and role rules.
        quals = [q for q in quals if q.get("origin") != "handover"]
    destinations = _destinations(jid, auth_db, staffish=staffish)
    lineage += [{"section": "qualifications",
                 "system": q.get("source_system"),
                 "source_system": q.get("source_system"),
                 "source": q.get("source_ref") or "learner_qualification",
                 "origin": q.get("origin")} for q in quals]

    if tier == EXTERNAL_TIER:
        # An employer/EPAO sees the apprenticeship's attendance, nothing
        # from school, college or university.
        attendance = [a for a in attendance if a["system"] == "apprenticeships"]

    p = person.get(jid, db_path=auth_db)
    systems = sorted({s for s, _ in person.all_local_records(jid, db_path=auth_db)},
                     key=lambda s: SYSTEM_ORDER.index(s) if s in SYSTEM_ORDER else 99)
    overview: dict[str, Any] = {
        "journey_id": jid,
        "full_name": p.full_name if p else "",
        "legal_first_name": journey.get("legal_first_name"),
        "legal_last_name": journey.get("legal_last_name"),
        "current_system": journey.get("current_system"),
        "current_label": _label(journey.get("current_system")),
        "status": journey.get("status"),
        "systems": systems,
        "system_labels": [_label(s) for s in systems],
    }
    if tier != EXTERNAL_TIER:
        overview["date_of_birth"] = journey.get("date_of_birth")
    if staffish:
        overview.update({
            "nhs_number": journey.get("nhs_number"), "upn": journey.get("upn"),
            "created_at": journey.get("created_at"),
            "merged_from": [m.get("duplicate_id") for m in merges],
        })

    support = {
        "flags": support_flags,
        "counts": support_counts,
        "documents_withheld": withheld_docs if can_see_safeguarding else None,
        "safeguarding": ({"visible": True,
                          "open_alerts": _open_safeguarding_alerts(jid, auth_db)}
                         if can_see_safeguarding else
                         {"visible": False,
                          "note": "Safeguarding records are visible only to "
                                  "a designated safeguarding role, and never "
                                  "in detail."}),
        # Welfare casework is never summarised here, even as a count: its
        # existence alone can disclose a disclosure.
        "welfare": {"visible": False},
    }

    sections: dict[str, Any] = {
        "overview": overview,
        "current_education": _current_education(rows, journey),
        "records": records,
        "timeline": sorted(
            _timeline(rows, year_history, workflow, legacy, quals,
                      merges if staffish else [])
            + [{"date": d.get("recorded_on"), "kind": "destination",
                "system": d.get("source_system"),
                "label": _label(d.get("source_system")),
                "detail": f"{d.get('checkpoint')}: {d.get('destination')}"
                          + (f" — {d['detail']}" if d.get("detail") else ""),
                "source": f"learner_destination:{d.get('destination_id')}"}
               for d in destinations],
            key=lambda e: (e["date"] is None, e["date"] or "")),
        "qualifications": quals,
        "attendance": attendance,
        "achievements": achievements,
        "progression": _progression(journey, workflow, auth_db,
                                    staffish=staffish,
                                    destinations=destinations),
        "transfers": _transfers(rows, workflow, legacy),
        "documents": documents,
        "support": support,
        "system_access": identity_service.users_for_journey(jid, db_path=auth_db),
        "lineage": lineage,
    }
    restricted = [name for name, _t in SECTION_TITLES if name not in visible]
    for name in restricted:
        sections[name] = None

    return {
        "journey_id": jid,
        "requested_journey_id": journey_id,
        "found": True,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "viewer": {"role": viewer_role, "system": viewer_system, "tier": tier},
        "restricted_sections": restricted,
        **sections,
        # The legacy registry moves, in the shape build_overview returned.
        "legacy_transitions": legacy if "timeline" in visible else [],
    }


def build_learner_360_for_student(system: str, student_id: str, **kwargs
                                  ) -> dict:
    """Resolve the journey from a local id, then build the Learner 360."""
    row = identity_service.find_by_student(system, student_id,
                                           db_path=kwargs.get("auth_db"))
    if row is None:
        return {"found": False, "system": system, "student_id": student_id}
    return build_learner_360(row["journey_id"], **kwargs)


def format_learner_360_text(view: dict) -> str:
    """Render a Learner 360 as plain text (CLI / logs)."""
    if not view.get("found"):
        return f"No journey found ({view.get('journey_id', '?')})"
    o = view.get("overview") or {}
    lines = [
        f"{o.get('full_name', '?')}  (journey {view['journey_id']})",
        f"  DOB {o.get('date_of_birth') or '—'}   "
        f"UPN {o.get('upn') or '—'}   NHS {o.get('nhs_number') or '—'}",
        f"  Currently: {o.get('current_label') or '—'} "
        f"({o.get('status') or '—'})",
    ]
    ce = view.get("current_education")
    if ce:
        lines.append("  Current education:")
        for a in ce["active"] + ce["pending"]:
            bits = [a["label"], f"[{a.get('local_student_id') or '—'}]",
                    a.get("status") or ""]
            for k in ("programme", "year_group", "institution_id"):
                if a.get(k):
                    bits.append(str(a[k]))
            lines.append("    - " + "  ".join(b for b in bits if b))
    for rec in view.get("records") or []:
        r = rec.get("record") or {}
        bits = [f"{rec['label']} [{rec['student_id']}]"]
        if r.get("year_group"):
            bits.append(f"Y{r['year_group']}")
        if r.get("course"):
            bits.append(str(r["course"]))
        if r.get("status"):
            bits.append(str(r["status"]))
        att = rec.get("attendance")
        if att:
            bits.append(f"attendance n={att['total']} "
                        f"({att.get('present_pct', '—')}% present)")
        if rec.get("results"):
            bits.append(f"{len(rec['results'])} result(s)")
        lines.append("    * " + "  ".join(bits))
    quals = view.get("qualifications")
    if quals:
        lines.append("  Qualifications:")
        for q in quals:
            lines.append(
                f"    - {q.get('title')}  {q.get('grade') or ''}  "
                f"{q.get('awarded_on') or ''}  [{q.get('source_system')}]")
    timeline = view.get("timeline")
    if timeline:
        lines.append("  Timeline:")
        for e in timeline:
            lines.append(f"    {e.get('date') or '?':<20} {e['label']:<20} "
                         f"{e['kind']}: {e['detail']}")
    support = view.get("support")
    if support and (support["flags"] or support["counts"]):
        lines.append("  Support: " + ", ".join(
            [f["flag"] for f in support["flags"]]
            + [f"{k}={v}" for k, v in support["counts"].items()]))
    if view.get("restricted_sections"):
        lines.append("  (Not shown for this viewer: "
                     + ", ".join(view["restricted_sections"]) + ")")
    return "\n".join(lines)


__all__ = [
    "ATTENDANCE_SOURCES",
    "PHASE_EXTRACTORS",
    "SAFEGUARDING_ROLES",
    "SECTION_TITLES",
    "SELF_ROLES",
    "STAFF_ROLES",
    "build_learner_360",
    "build_learner_360_for_student",
    "format_learner_360_text",
    "viewer_tier",
]
