"""Learner qualifications — one record per award, keyed on ``journey_id``.

Qualifications used to exist only inside the system that awarded them (a
GCSE in secondary's ``exam_results``, an FE aim's ``final_grade``, an
apprenticeship's completed standard) and, for a learner who moved on, in
the handover payload the next phase received. Nothing answered "what has
this person achieved?" across the platform, and ``qualification.awarded``
was declared on the bus but never published.

``learner_qualification`` (auth.db) is that answer. Each row records its
**lineage** — ``source_system`` plus ``source_ref`` (e.g.
``secondary:exam_results:41`` or ``handover:<transition>:gcse_results:maths``)
— and ``(source_system, source_ref)`` is unique, so every projection here is
an idempotent upsert.

Rows arrive three ways (``origin``):

``recorded``
    :func:`record_qualification` — a live award by a system or an operator.
    Publishes ``qualification.awarded``.
``system``
    :func:`sync_journey` / :func:`sync_all` — read from a system database
    via ``SYSTEM_DB_PATHS`` (never by importing the system). Silent: this
    is historic data catching up, not news.
``handover``
    Achieved results carried in an approved handover payload. Silent too,
    and for a stronger reason: handover data never goes on the bus.

:func:`collect_for_journey` is the read-only view the Learner 360 and the
transcript use — persisted rows plus anything derivable but not yet synced.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from education_system.paths import SYSTEM_DB_PATHS, SYSTEM_ORDER
from education_system.platform.cross_system import identity_service
from education_system.platform.identity.auth.db import connect

logger = logging.getLogger(__name__)

_SOURCE_MODULE = "platform.cross_system.qualifications"

ORIGINS = ("recorded", "system", "handover")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learner_qualification (
    qualification_id   TEXT    PRIMARY KEY,
    journey_id         TEXT    NOT NULL REFERENCES student_journey(journey_id),
    source_system      TEXT    NOT NULL,
    title              TEXT    NOT NULL,
    level              TEXT,
    grade              TEXT,
    awarded_on         TEXT,
    source_ref         TEXT,
    qualification_type TEXT,
    awarding_body      TEXT,
    origin             TEXT    NOT NULL DEFAULT 'recorded',
    recorded_by        TEXT,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_learner_qual_source
    ON learner_qualification(source_system, source_ref)
    WHERE source_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_learner_qual_journey
    ON learner_qualification(journey_id, awarded_on);
"""

# Handover keys that carry *achieved* results. Predicted grades, entries
# and credits-in-progress are deliberately absent: a qualification record
# says what somebody has, not what they are expected to get.
HANDOVER_QUALIFICATION_KEYS: dict[str, tuple[str, str | None]] = {
    # key -> (title prefix, level)
    "achieved_qualifications": ("", None),
    "gcse_results": ("GCSE", "2"),
    "ks2_results": ("KS2", "KS2"),
    "epa_result": ("End-point assessment", None),
    "standard_completed": ("Apprenticeship standard", None),
}

# Grades that record a sitting, not an award.
_NON_AWARD_GRADES = frozenset({
    "", "u", "fail", "f", "unclassified", "x", "absent", "withdrawn",
    "pending", "not yet", "ungraded",
})

# Only these transition states carry an approved handover.
_HANDOVER_STATES = ("handover_approved", "admitted", "completed")

_initialised: set[str] = set()


def ensure_qualification_schema(db_path: str | None = None) -> None:
    key = db_path or "<default>"
    if key in _initialised:
        return
    identity_service._ensure(db_path)
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    _initialised.add(key)


def reset_schema_cache_for_test() -> None:
    _initialised.clear()


def _is_award(grade: Any) -> bool:
    return str(grade or "").strip().lower() not in _NON_AWARD_GRADES


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def record_qualification(
    journey_id: str,
    *,
    source_system: str,
    title: str,
    level: str | int | None = None,
    grade: str | None = None,
    awarded_on: str | None = None,
    source_ref: str | None = None,
    qualification_type: str | None = None,
    awarding_body: str | None = None,
    recorded_by: str | None = None,
    origin: str = "recorded",
    publish: bool = True,
    db_path: str | None = None,
) -> dict:
    """Record (or update) one qualification and return the row.

    Idempotent on ``(source_system, source_ref)``: recording the same award
    again updates it rather than duplicating it, and publishes
    ``qualification.awarded`` only when the row is new or its grade changed
    (a re-mark is news; a re-sync is not). Pass ``publish=False`` for bulk
    or handover-derived writes. A merged journey id is followed to its
    survivor; an unknown one raises ``ValueError``.
    """
    if not (title or "").strip():
        raise ValueError("title is required")
    if not source_system:
        raise ValueError("source_system is required")
    if origin not in ORIGINS:
        raise ValueError(f"origin must be one of {', '.join(ORIGINS)}")
    ensure_qualification_schema(db_path)
    jid = identity_service.resolve_journey_id(journey_id, db_path=db_path)
    if jid is None:
        raise ValueError(f"No journey {journey_id}")
    level_text = None if level is None else str(level)

    conn = connect(db_path)
    try:
        existing = None
        if source_ref:
            existing = conn.execute(
                "SELECT * FROM learner_qualification WHERE source_system = ? "
                "AND source_ref = ?", (source_system, source_ref)).fetchone()
        if existing is None:
            qid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO learner_qualification (qualification_id, "
                "journey_id, source_system, title, level, grade, awarded_on, "
                "source_ref, qualification_type, awarding_body, origin, "
                "recorded_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (qid, jid, source_system, title.strip(), level_text, grade,
                 awarded_on, source_ref, qualification_type, awarding_body,
                 origin, recorded_by))
            announce = True
        else:
            qid = existing["qualification_id"]
            announce = (existing["grade"] or None) != (grade or None)
            conn.execute(
                "UPDATE learner_qualification SET journey_id = ?, title = ?, "
                "level = COALESCE(?, level), grade = ?, "
                "awarded_on = COALESCE(?, awarded_on), "
                "qualification_type = COALESCE(?, qualification_type), "
                "awarding_body = COALESCE(?, awarding_body), "
                "updated_at = datetime('now') WHERE qualification_id = ?",
                (jid, title.strip(), level_text, grade, awarded_on,
                 qualification_type, awarding_body, qid))
        conn.commit()
        row = dict(conn.execute(
            "SELECT * FROM learner_qualification WHERE qualification_id = ?",
            (qid,)).fetchone())
    finally:
        conn.close()

    if publish and announce and origin != "handover":
        from education_system.platform.integrations.external import (
            cross_system_bus,
        )
        identity_service._publish(
            cross_system_bus.EVENT_QUALIFICATION_AWARDED, journey_id=jid,
            idempotency_key=f"qualification.awarded:{qid}:{grade or '-'}",
            source_system=source_system
            if source_system in identity_service.SYSTEM_SLOTS else "platform",
            source_module=_SOURCE_MODULE, db_path=db_path,
            qualification_id=qid, title=row["title"], level=row["level"],
            grade=row["grade"], awarded_on=row["awarded_on"],
            qualification_type=row["qualification_type"],
            awarding_body=row["awarding_body"], source_ref=source_ref)
    return row


def list_for_journey(journey_id: str, *,
                     db_path: str | None = None) -> list[dict]:
    """Persisted qualifications for one learner, oldest award first."""
    ensure_qualification_schema(db_path)
    jid = identity_service.resolve_journey_id(journey_id,
                                              db_path=db_path) or journey_id
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM learner_qualification WHERE journey_id = ? "
            "ORDER BY awarded_on IS NULL, awarded_on, created_at",
            (jid,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Handover projection
# ---------------------------------------------------------------------------

def _payload_of(handover_json: str | None) -> dict:
    try:
        data = json.loads(handover_json or "{}")
    except (TypeError, ValueError):
        return {}
    if isinstance(data, dict) and isinstance(data.get("payload"), dict):
        return data["payload"]
    return data if isinstance(data, dict) else {}


def _title_from(item: dict) -> str | None:
    for k in ("title", "qualification", "name", "subject", "standard"):
        if item.get(k):
            return str(item[k])
    return None


def _items_from_value(key: str, value: Any) -> list[tuple[str, dict]]:
    """(ref suffix, item) pairs from one handover value, any common shape."""
    prefix, level = HANDOVER_QUALIFICATION_KEYS[key]

    def with_prefix(title: str) -> str:
        return f"{prefix} {title}".strip() if prefix else title

    out: list[tuple[str, dict]] = []
    if isinstance(value, dict):
        if _title_from(value) and ("grade" in value or "result" in value
                                   or "title" in value):
            value = [value]
        else:
            for subject, result in value.items():
                if isinstance(result, dict):
                    grade = result.get("grade") or result.get("result")
                    out.append((str(subject), {
                        "title": with_prefix(_title_from(result) or str(subject)),
                        "grade": None if grade is None else str(grade),
                        "level": result.get("level") or level,
                        "awarded_on": result.get("awarded_on")
                        or result.get("date")}))
                else:
                    out.append((str(subject), {
                        "title": with_prefix(str(subject)),
                        "grade": None if result is None else str(result),
                        "level": level, "awarded_on": None}))
            return out
    if isinstance(value, list):
        for i, item in enumerate(value):
            if isinstance(item, dict):
                title = _title_from(item)
                if not title:
                    continue
                grade = item.get("grade") or item.get("result")
                out.append((str(i), {
                    "title": with_prefix(title),
                    "grade": None if grade is None else str(grade),
                    "level": item.get("level") or level,
                    "awarded_on": item.get("awarded_on") or item.get("date")}))
            elif item:
                out.append((str(i), {"title": with_prefix(str(item)),
                                     "grade": None, "level": level,
                                     "awarded_on": None}))
        return out
    if value not in (None, "", False):
        out.append(("value", {"title": prefix or key.replace("_", " "),
                              "grade": str(value), "level": level,
                              "awarded_on": None}))
    return out


def _handover_items(journey_id: str, *,
                    db_path: str | None) -> list[dict]:
    """Qualification dicts derivable from a journey's approved handovers."""
    conn = connect(db_path)
    try:
        try:
            rows = conn.execute(
                "SELECT transition_id, source_system, handover_json, "
                "handover_approved_at FROM learner_transition "
                "WHERE journey_id = ? AND handover_json IS NOT NULL "
                f"AND status IN ({', '.join('?' * len(_HANDOVER_STATES))})",
                (journey_id, *_HANDOVER_STATES)).fetchall()
        except sqlite3.Error:
            return []
    finally:
        conn.close()
    items = []
    for r in rows:
        payload = _payload_of(r["handover_json"])
        for key in HANDOVER_QUALIFICATION_KEYS:
            if key not in payload:
                continue
            for suffix, item in _items_from_value(key, payload[key]):
                if item["grade"] is not None and not _is_award(item["grade"]):
                    continue
                items.append({
                    **item,
                    "awarded_on": item.get("awarded_on")
                    or (r["handover_approved_at"] or "")[:10] or None,
                    "source_system": r["source_system"] or "external",
                    "source_ref": f"handover:{r['transition_id']}:{key}:{suffix}",
                    "origin": "handover",
                })
    return items


# ---------------------------------------------------------------------------
# System projection — read via SYSTEM_DB_PATHS, never by importing a system
# ---------------------------------------------------------------------------

def _open(path) -> sqlite3.Connection | None:
    if not path or not Path(path).exists():
        return None
    # Read-only so a projection can never create or write a system DB.
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro",
                           uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _has(conn, table: str) -> set[str]:
    try:
        return {r[1] for r in conn.execute(
            f"PRAGMA table_info({table})").fetchall()}  # nosec B608 - fixed names
    except sqlite3.Error:
        return set()


def _in_clause(ids: list[str] | None, column: str) -> tuple[str, list]:
    if ids is None:
        return "", []
    return f" AND {column} IN ({', '.join('?' * len(ids))})", list(ids)


def _primary(conn, ids) -> list[tuple[str, dict]]:
    cols = _has(conn, "sats_results")
    if not {"pupil_id", "subject"} <= cols:
        return []
    grade_col = next((c for c in ("outcome", "scaled_score", "result", "grade")
                      if c in cols), None)
    year_col = "academic_year" if "academic_year" in cols else None
    where, args = _in_clause(ids, "pupil_id")
    rows = conn.execute(
        f"SELECT rowid AS rid, pupil_id, subject"  # nosec B608 - probed columns
        f"{', ' + grade_col + ' AS grade' if grade_col else ''}"
        f"{', ' + year_col + ' AS year' if year_col else ''} "
        f"FROM sats_results WHERE 1=1{where}", args).fetchall()
    return [(str(r["pupil_id"]), {
        "title": f"KS2 SATs {r['subject']}", "level": "KS2",
        "grade": str(r["grade"]) if grade_col and r["grade"] is not None
        else None,
        "awarded_on": r["year"] if year_col else None,
        "qualification_type": "KS2 SATs",
        "source_ref": f"primary:sats_results:{r['rid']}"}) for r in rows]


def _secondary(conn, ids) -> list[tuple[str, dict]]:
    if not {"pupil_id", "final_grade", "result_id"} <= _has(conn, "exam_results"):
        return []
    subj = _has(conn, "subjects")
    entries = _has(conn, "exam_entries")
    join_s = ("LEFT JOIN subjects s ON s.subject_id = r.subject_id"
              if {"subject_id", "name"} <= subj else "")
    join_e = ("LEFT JOIN exam_entries e ON e.entry_id = r.entry_id"
              if "entry_id" in entries else "")
    name = "s.name" if join_s else "NULL"
    qual = "s.qualification" if join_s and "qualification" in subj else "NULL"
    board = "e.exam_board" if join_e and "exam_board" in entries else "NULL"
    where, args = _in_clause(ids, "r.pupil_id")
    rows = conn.execute(
        f"SELECT r.result_id, r.pupil_id, r.subject_id, r.final_grade, "  # nosec B608 - probed
        f"r.result_date, {name} AS subject_name, {qual} AS qualification, "
        f"{board} AS board FROM exam_results r {join_s} {join_e} "
        f"WHERE r.final_grade IS NOT NULL{where}", args).fetchall()
    out = []
    for r in rows:
        if not _is_award(r["final_grade"]):
            continue
        q = r["qualification"] or "GCSE"
        out.append((str(r["pupil_id"]), {
            "title": f"{q} {r['subject_name'] or 'subject ' + str(r['subject_id'])}",
            "level": "2" if q.upper().startswith("GCSE") else None,
            "grade": str(r["final_grade"]), "awarded_on": r["result_date"],
            "qualification_type": q, "awarding_body": r["board"],
            "source_ref": f"secondary:exam_results:{r['result_id']}"}))
    return out


def _sixth_form(conn, ids) -> list[tuple[str, dict]]:
    if not ({"entry_id", "grade", "result_id"} <= _has(conn, "exam_results")
            and {"entry_id", "student_id", "subject"} <= _has(conn, "exam_entries")):
        return []
    where, args = _in_clause(ids, "e.student_id")
    rows = conn.execute(
        "SELECT r.result_id, r.grade, r.released_at, e.student_id, e.subject, "  # nosec B608
        "e.paper_title, e.exam_board, e.year FROM exam_results r "
        f"JOIN exam_entries e ON e.entry_id = r.entry_id WHERE 1=1{where}",
        args).fetchall()
    out = []
    for r in rows:
        if not _is_award(r["grade"]):
            continue
        title = r["subject"] + (f" — {r['paper_title']}" if r["paper_title"] else "")
        out.append((str(r["student_id"]), {
            "title": title, "level": "3", "grade": str(r["grade"]),
            "awarded_on": (r["released_at"] or "")[:10] or (
                str(r["year"]) if r["year"] else None),
            "qualification_type": "A Level", "awarding_body": r["exam_board"],
            "source_ref": f"sixth_form:exam_results:{r['result_id']}"}))
    return out


def _fe_college(conn, ids) -> list[tuple[str, dict]]:
    cols = _has(conn, "enrolments")
    if not {"enrolment_id", "student_id", "status", "final_grade"} <= cols:
        return []
    courses = _has(conn, "courses")
    join = "LEFT JOIN courses c ON c.course_id = e.course_id" if courses else ""

    def c(col: str) -> str:
        return f"c.{col}" if col in courses else "NULL"

    where, args = _in_clause(ids, "e.student_id")
    rows = conn.execute(
        f"SELECT e.enrolment_id, e.student_id, e.course_id, e.final_grade, "  # nosec B608
        f"e.end_date, {c('title')} AS title, {c('level')} AS level, "
        f"{c('qualification_type')} AS qtype, "
        f"{c('awarding_body')} AS body FROM enrolments e {join} "
        f"WHERE e.status = 'completed'{where}", args).fetchall()
    return [(str(r["student_id"]), {
        "title": r["title"] or str(r["course_id"]), "level": r["level"],
        "grade": str(r["final_grade"]), "awarded_on": r["end_date"],
        "qualification_type": r["qtype"], "awarding_body": r["body"],
        "source_ref": f"fe_college:enrolments:{r['enrolment_id']}"})
        for r in rows if _is_award(r["final_grade"])]


def _apprenticeships(conn, ids) -> list[tuple[str, dict]]:
    cols = _has(conn, "apprentices")
    if not {"apprentice_id", "status", "programme_id"} <= cols:
        return []
    progs = _has(conn, "programmes")
    join = ("LEFT JOIN programmes p ON p.programme_id = a.programme_id"
            if {"title", "level"} <= progs else "")
    title = "p.title" if join else "NULL"
    level = "p.level" if join else "NULL"
    end = "a.actual_end_date" if "actual_end_date" in cols else "NULL"
    where, args = _in_clause(ids, "a.apprentice_id")
    rows = conn.execute(
        f"SELECT a.apprentice_id, a.programme_id, {end} AS ended, "  # nosec B608
        f"{title} AS title, {level} AS level FROM apprentices a {join} "
        f"WHERE a.status = 'Completed'{where}", args).fetchall()
    has_epa = {"apprentice_id", "grade", "assessed_date"} <= _has(conn, "epa_results")
    out = []
    for r in rows:
        grade = None
        if has_epa:
            # The published EPA outcome is the one grade that crosses; the
            # latest assessed method stands for the award. Portfolio and
            # formative judgements are never read.
            g = conn.execute(
                "SELECT grade FROM epa_results WHERE apprentice_id = ? "
                "ORDER BY assessed_date DESC, result_id DESC LIMIT 1",
                (r["apprentice_id"],)).fetchone()
            grade = g["grade"] if g else None
        out.append((str(r["apprentice_id"]), {
            "title": r["title"] or f"Apprenticeship programme {r['programme_id']}",
            "level": None if r["level"] is None else str(r["level"]),
            "grade": grade, "awarded_on": r["ended"],
            "qualification_type": "Apprenticeship standard",
            "source_ref": (f"apprenticeships:apprentices:{r['apprentice_id']}:"
                           f"{r['programme_id']}")}))
    return out


def _university(conn, ids) -> list[tuple[str, dict]]:
    cols = _has(conn, "certificates")
    if not {"id", "student_id", "certificate_type", "course_name"} <= cols:
        return []
    status = " AND COALESCE(status, 'active') != 'revoked'" if "status" in cols else ""
    where, args = _in_clause(ids, "student_id")
    rows = conn.execute(
        "SELECT id, student_id, certificate_type, course_name, "  # nosec B608
        f"{'award_date' if 'award_date' in cols else 'NULL'} AS awarded, "
        f"{'grade' if 'grade' in cols else 'NULL'} AS grade "
        f"FROM certificates WHERE 1=1{status}{where}", args).fetchall()
    return [(str(r["student_id"]), {
        "title": f"{r['certificate_type']}: {r['course_name']}",
        "level": None, "grade": r["grade"], "awarded_on": r["awarded"],
        "qualification_type": r["certificate_type"],
        "source_ref": f"university:certificates:{r['id']}"}) for r in rows]


#: system -> reader(conn, local_ids | None) -> [(local_id, item)]. ``None``
#: means every row (the bulk sync); a list restricts to those learners.
SYSTEM_READERS: dict[str, Callable[[sqlite3.Connection, list[str] | None],
                                   list[tuple[str, dict]]]] = {
    "primary": _primary,
    "secondary": _secondary,
    "sixth_form": _sixth_form,
    "fe_college": _fe_college,
    "apprenticeships": _apprenticeships,
    "university": _university,
}


def _read_system(system: str, path, ids: list[str] | None
                 ) -> list[tuple[str, dict]]:
    reader = SYSTEM_READERS.get(system)
    conn = _open(path) if reader else None
    if conn is None:
        return []
    try:
        out: list[tuple[str, dict]] = []
        if ids is None:
            out = reader(conn, None)
        else:
            for start in range(0, len(ids), 400):
                out.extend(reader(conn, ids[start:start + 400]))
        return out
    except sqlite3.Error:
        logger.debug("Qualification read failed for %s", system,
                     exc_info=True)
        return []
    finally:
        conn.close()


def _system_items(journey_id: str, *, db_paths: dict | None,
                  db_path: str | None) -> list[dict]:
    from education_system.platform.cross_system import person
    paths = db_paths if db_paths is not None else SYSTEM_DB_PATHS
    by_system: dict[str, list[str]] = {}
    for system, local_id in person.all_local_records(journey_id,
                                                     db_path=db_path):
        by_system.setdefault(system, []).append(local_id)
    items = []
    for system in SYSTEM_ORDER:
        ids = by_system.get(system)
        if not ids:
            continue
        for _local, item in _read_system(system, paths.get(system), ids):
            items.append({**item, "source_system": system, "origin": "system"})
    return items


def _dedupe(items: Iterable[dict]) -> list[dict]:
    """Keep one row per award, preferring recorded > system > handover.

    A GCSE appears in secondary's exam_results *and* in the handover to
    sixth form; it is still one qualification.
    """
    priority = {"recorded": 0, "system": 1, "handover": 2}
    ordered = sorted(items, key=lambda i: priority.get(i.get("origin"), 3))
    seen_refs: set[tuple[str, str]] = set()
    seen_awards: set[tuple[str, str]] = set()
    out = []
    for item in ordered:
        ref = (item.get("source_system") or "", item.get("source_ref") or "")
        award = (identity_service.normalise_name(item.get("title")),
                 str(item.get("grade") or "").strip().lower())
        if (ref[1] and ref in seen_refs) or award in seen_awards:
            continue
        if ref[1]:
            seen_refs.add(ref)
        seen_awards.add(award)
        out.append(item)
    return sorted(out, key=lambda i: (i.get("awarded_on") is None,
                                      str(i.get("awarded_on") or ""),
                                      i.get("title") or ""))


def collect_for_journey(journey_id: str, *, db_paths: dict | None = None,
                        db_path: str | None = None,
                        include_derived: bool = True) -> list[dict]:
    """Every qualification known for a learner, read-only.

    Persisted rows plus, unless ``include_derived=False``, what the system
    databases and approved handovers would add on the next sync. Each item
    carries ``source_system``, ``source_ref`` and ``origin`` (lineage).
    """
    rows = [{**r, "origin": r.get("origin") or "recorded"}
            for r in list_for_journey(journey_id, db_path=db_path)]
    if not include_derived:
        return rows
    jid = identity_service.resolve_journey_id(journey_id,
                                              db_path=db_path) or journey_id
    derived = _system_items(jid, db_paths=db_paths, db_path=db_path)
    derived += _handover_items(jid, db_path=db_path)
    return _dedupe([*rows, *derived])


def _persist(journey_id: str, items: Iterable[dict], *,
             db_path: str | None) -> int:
    ensure_qualification_schema(db_path)
    conn = connect(db_path)
    try:
        known = {(r["source_system"], r["source_ref"]) for r in conn.execute(
            "SELECT source_system, source_ref FROM learner_qualification "
            "WHERE source_ref IS NOT NULL").fetchall()}
    finally:
        conn.close()
    created = 0
    for item in items:
        key = (item["source_system"], item["source_ref"])
        is_new = key not in known
        try:
            record_qualification(
                journey_id, source_system=item["source_system"],
                title=item["title"], level=item.get("level"),
                grade=item.get("grade"), awarded_on=item.get("awarded_on"),
                source_ref=item["source_ref"],
                qualification_type=item.get("qualification_type"),
                awarding_body=item.get("awarding_body"),
                origin=item["origin"], publish=False, db_path=db_path)
        except Exception:
            logger.exception("Could not persist qualification %s", key)
            continue
        known.add(key)
        created += int(is_new)
    return created


def sync_journey(journey_id: str, *, db_paths: dict | None = None,
                 db_path: str | None = None) -> int:
    """Persist everything derivable for one learner. Returns rows created."""
    jid = identity_service.resolve_journey_id(journey_id, db_path=db_path)
    if jid is None:
        return 0
    items = _system_items(jid, db_paths=db_paths, db_path=db_path)
    items += _handover_items(jid, db_path=db_path)
    return _persist(jid, items, db_path=db_path)


def sync_all(*, db_paths: dict | None = None,
             db_path: str | None = None) -> dict[str, int]:
    """Project every system's qualifications and every approved handover.

    Reads each system database once (not once per learner — a fresh
    connection to the university DB alone costs ~100ms) and maps local ids
    to journeys in batches. Idempotent. Returns counts per source.
    """
    from education_system.platform.cross_system import enrolments
    ensure_qualification_schema(db_path)
    paths = db_paths if db_paths is not None else SYSTEM_DB_PATHS
    summary = {"created": 0, "unmatched": 0, "handover": 0}
    for system in SYSTEM_ORDER:
        rows = _read_system(system, paths.get(system), None)
        if not rows:
            summary[system] = 0
            continue
        ids = sorted({local for local, _item in rows})
        journeys = identity_service.find_by_students(system, ids,
                                                     db_path=db_path)
        per_journey: dict[str, list[dict]] = {}
        for local, item in rows:
            journey = journeys.get(local)
            jid = journey["journey_id"] if journey else None
            if jid is None:
                # A spell whose id is only in the enrolment history.
                hits = enrolments.find_by_local_id(system, local,
                                                   db_path=db_path)
                jid = hits[0]["journey_id"] if hits else None
            if jid is None:
                summary["unmatched"] += 1
                continue
            per_journey.setdefault(jid, []).append(
                {**item, "source_system": system, "origin": "system"})
        created = sum(_persist(jid, items, db_path=db_path)
                      for jid, items in per_journey.items())
        summary[system] = created
        summary["created"] += created

    conn = connect(db_path)
    try:
        try:
            jids = [r[0] for r in conn.execute(
                "SELECT DISTINCT journey_id FROM learner_transition "
                "WHERE handover_json IS NOT NULL").fetchall()]
        except sqlite3.Error:
            jids = []
    finally:
        conn.close()
    for jid in jids:
        live = identity_service.resolve_journey_id(jid, db_path=db_path)
        if live:
            n = _persist(live, _handover_items(live, db_path=db_path),
                         db_path=db_path)
            summary["handover"] += n
            summary["created"] += n
    return summary


__all__ = [
    "HANDOVER_QUALIFICATION_KEYS",
    "SYSTEM_READERS",
    "ensure_qualification_schema",
    "reset_schema_cache_for_test",
    "record_qualification",
    "list_for_journey",
    "collect_for_journey",
    "sync_journey",
    "sync_all",
]
