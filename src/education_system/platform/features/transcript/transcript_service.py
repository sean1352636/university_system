"""Digital Transcript service layer.

Builds a cross-system transcript for one learner from every system
database. The learner is resolved through the canonical identity registry
first: given a journey id, a (system, local id), or a legal name that
matches exactly one journey, every record that journey has held is read
**by its local id** and the platform's qualification record is attached.

Only a learner the registry does not know falls back to the old heuristic
of matching the name across systems — and then only against records that
are not themselves linked to a journey, because a linked record belongs to
somebody, and it is not this learner.

Methods:
  generate_transcript(student_name=None, *, journey_id=None, system=None,
                      student_id=None) -> structured dict
  format_transcript(transcript_data) -> formatted text string
  save_transcript(text, output_path)
  get_transcript_summary(student_name) -> one-paragraph summary string
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from education_system.paths import (
    SYSTEM_DB_PATHS as _DB_PATHS,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
    learner_table,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _connect(system, db_paths=None):
    path = (db_paths if db_paths is not None else _DB_PATHS).get(system)
    if not path or not Path(path).exists():
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row[0] > 0


def _get_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r[1] for r in rows}


def _name_search_expr(columns):
    if "full_name" in columns:
        return "full_name"
    if "name" in columns:
        return "name"
    if "first_name" in columns and "last_name" in columns:
        return "(first_name || ' ' || last_name)"
    if "given_name" in columns and "family_name" in columns:
        return "(given_name || ' ' || family_name)"
    if "forename" in columns and "surname" in columns:
        return "(forename || ' ' || surname)"
    if "first_name" in columns and "surname" in columns:
        return "(first_name || ' ' || surname)"
    if "forename" in columns and "last_name" in columns:
        return "(forename || ' ' || last_name)"
    return None


def _extract_name(row, columns=None):
    rk = row.keys() if hasattr(row, "keys") else []
    if "full_name" in rk and row["full_name"]:
        return row["full_name"]
    if "name" in rk and row["name"]:
        return row["name"]
    parts = []
    for fn in ("first_name", "given_name", "forename"):
        if fn in rk and row[fn]:
            parts.append(row[fn])
            break
    for ln in ("last_name", "family_name", "surname"):
        if ln in rk and row[ln]:
            parts.append(row[ln])
            break
    return " ".join(parts) if parts else ""


def _locate(conn, system, *, student_id=None, name=None, unlinked_only=False):
    """The learner row for ``student_id`` (exact) or ``name`` (LIKE).

    The learner table comes from the one registry (``pupils`` /
    ``students`` / ``apprentices``); the old code hard-wired ``students``
    for secondary, whose learners live in ``pupils``.
    """
    table, id_col = learner_table(system)
    if not _table_exists(conn, table):
        table = next((t for t in ("pupils", "students", "apprentices")
                      if _table_exists(conn, t)), None)
        if table is None:
            return None
    cols = _get_columns(conn, table)
    if student_id is not None:
        key = id_col if id_col in cols else ("id" if "id" in cols else None)
        if key is None:
            return None
        return conn.execute(
            f"SELECT * FROM {table} WHERE {key} = ?",  # nosec B608 - registry names
            (student_id,)).fetchone()
    name_expr = _name_search_expr(cols)
    if not (name and name_expr):
        return None
    extra = (" AND (journey_id IS NULL OR journey_id = '')"
             if unlinked_only and "journey_id" in cols else "")
    return conn.execute(
        f"SELECT * FROM {table} WHERE {name_expr} LIKE ?{extra} LIMIT 1",  # nosec B608
        (f"%{name}%",)).fetchone()


def _blank(system, row, cols=None):
    rk = row.keys()
    table_id = learner_table(system)[1]
    sid = row[table_id] if table_id in rk else (row["id"] if "id" in rk else "")
    data = {
        "system": system,
        "student_id": sid,
        "name": _extract_name(row, cols),
        "year_group": row["year_group"] if "year_group" in rk else "",
        "status": row["status"] if "status" in rk else "unknown",
        "enrolled_date": "",
        "personal_info": {},
        "grades": [],
        "attendance": {},
        "qualifications": [],
        "transfers": [],
    }
    for col in ("admission_date", "enrollment_date", "enrolled_date",
                "start_date"):
        if col in rk and row[col]:
            data["enrolled_date"] = row[col]
            break
    for col in ("date_of_birth", "dob", "gender", "email", "address",
                "programme", "department"):
        if col in rk and row[col]:
            data["personal_info"][col] = row[col]
    data["personal_info"]["name"] = data["name"]
    return data


def _attendance_counts(conn, table, id_col, key, status_col="status",
                       join=""):
    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM {table} {join} WHERE {id_col} = ?",  # nosec B608
        (key,)).fetchone()["c"]
    present = conn.execute(
        f"SELECT COUNT(*) AS c FROM {table} {join} WHERE {id_col} = ? "  # nosec B608
        f"AND LOWER({status_col}) IN ('present','late','/','\\','l')",
        (key,)).fetchone()["c"]
    return {
        "total_sessions": total,
        "present": present,
        "percentage": round(present / total * 100, 1) if total > 0 else 0,
    }


def _transfer_rows(conn, sid, candidates=("student_id", "source_student_id")):
    if not _table_exists(conn, "academic_transfer_history"):
        return []
    th_cols = _get_columns(conn, "academic_transfer_history")
    id_match = next((c for c in candidates if c in th_cols), None)
    if not id_match:
        return []
    rows = conn.execute(
        f"SELECT * FROM academic_transfer_history WHERE {id_match} = ?",  # nosec B608
        (sid,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class TranscriptService:
    """Generates comprehensive cross-system transcripts."""

    def __init__(self, db_paths=None, auth_db=None):
        # Both default to the canonical registry; tests pass temp paths.
        self._db_paths = db_paths
        self._auth_db = auth_db

    def search_students(self, name_query):
        """Search every system for learners matching *name_query*.

        Returns a list of dicts: system, student_id, name, year_group,
        status, journey_id (when the local row is linked).
        """
        results = []
        if not name_query or not name_query.strip():
            return results
        like = f"%{name_query.strip()}%"

        for sys_key in SYSTEM_ORDER:
            conn = _connect(sys_key, self._db_paths)
            if not conn:
                continue
            try:
                table, id_col = learner_table(sys_key)
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                name_expr = _name_search_expr(cols)
                if not name_expr:
                    continue
                if id_col not in cols:
                    id_col = "id" if "id" in cols else id_col
                year_col = "year_group" if "year_group" in cols else (
                    "year" if "year" in cols else None)

                rows = conn.execute(
                    f"SELECT *, {name_expr} AS full_name FROM {table} "  # nosec B608
                    f"WHERE {name_expr} LIKE ? LIMIT 50",
                    (like,),
                ).fetchall()
                for r in rows:
                    rk = r.keys()
                    results.append({
                        "system": sys_key,
                        "student_id": r[id_col] if id_col in rk else "",
                        "name": r["full_name"],
                        "year_group": r[year_col] if year_col and year_col in rk else "",
                        "status": r["status"] if "status" in rk else "unknown",
                        "journey_id": r["journey_id"] if "journey_id" in rk else None,
                    })
            except Exception:
                logger.debug("Transcript search failed for %s", sys_key,
                             exc_info=True)
            finally:
                conn.close()
        return results

    # -----------------------------------------------------------------------
    # Transcript generation
    # -----------------------------------------------------------------------

    def _resolve_journey(self, *, journey_id=None, system=None,
                         student_id=None, student_name=None):
        """The canonical journey row, or None (unknown or ambiguous)."""
        try:
            from education_system.platform.cross_system import identity_service
            if journey_id:
                jid = identity_service.resolve_journey_id(
                    journey_id, db_path=self._auth_db)
                return identity_service.get(jid, db_path=self._auth_db) if jid else None
            if system and student_id is not None:
                return identity_service.find_by_student(
                    system, str(student_id), db_path=self._auth_db)
            if student_name:
                return self._journey_by_name(student_name)
        except Exception:
            logger.debug("Transcript journey resolution failed", exc_info=True)
        return None

    def _journey_by_name(self, student_name):
        from education_system.platform.cross_system import identity_service
        from education_system.platform.identity.auth.db import connect
        target = identity_service.normalise_name(student_name)
        if not target:
            return None
        conn = connect(self._auth_db)
        try:
            rows = conn.execute(
                "SELECT * FROM student_journey WHERE LOWER(legal_last_name) "
                "LIKE ? AND COALESCE(status, '') != 'merged'",
                (f"%{target.split()[-1]}%",)).fetchall()
        except sqlite3.Error:
            return None
        finally:
            conn.close()
        hits = [dict(r) for r in rows if identity_service.normalise_name(
            f"{r['legal_first_name']} {r['legal_last_name']}") == target]
        # Two learners with this name: refuse to guess.
        return hits[0] if len(hits) == 1 else None

    def generate_transcript(self, student_name=None, *, journey_id=None,
                            system=None, student_id=None):
        """Build a structured transcript dict.

        Identify the learner by ``journey_id``, by ``system`` +
        ``student_id``, or by ``student_name`` (positional, as before).

        The dict contains: student_name, journey_id, matched_by
        ("journey_id" | "name"), generated_at, personal_info, systems (one
        per local record, with grades, attendance, qualifications),
        transfers, and qualifications (the platform's cross-system record,
        each with its source_system/source_ref lineage).
        """
        journey = self._resolve_journey(journey_id=journey_id, system=system,
                                        student_id=student_id,
                                        student_name=student_name)
        transcript = {
            "student_name": student_name or "",
            "journey_id": journey["journey_id"] if journey else None,
            "matched_by": "journey_id" if journey else "name",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "personal_info": {},
            "systems": [],
            "transfers": [],
            "qualifications": [],
        }

        if journey is not None:
            from education_system.platform.cross_system import (
                person,
                qualifications,
            )
            transcript["student_name"] = (
                f"{journey.get('legal_first_name') or ''} "
                f"{journey.get('legal_last_name') or ''}").strip()
            transcript["personal_info"]["date_of_birth"] = journey.get("date_of_birth")
            for sys_key, local_id in person.all_local_records(
                    journey["journey_id"], db_path=self._auth_db):
                self._add(transcript, self._collect_system_data(
                    sys_key, student_id=local_id))
            try:
                transcript["qualifications"] = qualifications.collect_for_journey(
                    journey["journey_id"], db_paths=self._db_paths,
                    db_path=self._auth_db)
            except Exception:
                logger.debug("Qualification read failed", exc_info=True)
            transcript["personal_info"]["name"] = transcript["student_name"]
            return transcript

        if student_name:
            for sys_key in SYSTEM_ORDER:
                self._add(transcript, self._collect_system_data(
                    sys_key, name=student_name, unlinked_only=True))
        return transcript

    @staticmethod
    def _add(transcript, sys_data):
        if not sys_data:
            return
        transcript["systems"].append(sys_data)
        # Merge personal info (later systems override)
        if sys_data.get("personal_info"):
            transcript["personal_info"].update(sys_data["personal_info"])
        if sys_data.get("transfers"):
            transcript["transfers"].extend(sys_data["transfers"])

    def format_transcript(self, transcript_data):
        """Convert a transcript dict to a well-formatted text report."""
        lines = []
        lines.append("=" * 70)
        lines.append("DIGITAL TRANSCRIPT")
        lines.append("=" * 70)
        lines.append(f"Student: {transcript_data.get('student_name', 'N/A')}")
        if transcript_data.get("journey_id"):
            lines.append(f"Learner reference: {transcript_data['journey_id']}")
        lines.append(f"Generated: {transcript_data.get('generated_at', '')}")
        lines.append("")

        # Personal Information
        pi = transcript_data.get("personal_info", {})
        if pi:
            lines.append("-" * 40)
            lines.append("PERSONAL INFORMATION")
            lines.append("-" * 40)
            for key in ("name", "date_of_birth", "dob", "gender", "email", "address"):
                val = pi.get(key)
                if val:
                    lines.append(f"  {key.replace('_', ' ').title()}: {val}")
            lines.append("")

        # Educational History per system
        for sys_data in transcript_data.get("systems", []):
            sys_label = SYSTEM_LABELS.get(sys_data["system"], sys_data["system"].title())
            lines.append("-" * 40)
            lines.append(f"EDUCATIONAL HISTORY: {sys_label.upper()}")
            lines.append("-" * 40)

            if sys_data.get("enrolled_date"):
                lines.append(f"  Enrolled: {sys_data['enrolled_date']}")
            if sys_data.get("year_group"):
                lines.append(f"  Year/Group: {sys_data['year_group']}")
            if sys_data.get("status"):
                lines.append(f"  Status: {sys_data['status']}")
            lines.append("")

            # Grades
            grades = sys_data.get("grades", [])
            if grades:
                lines.append("  Courses / Subjects / Grades:")
                for g in grades:
                    parts = []
                    for k in ("subject_code", "course_code", "subject", "assessment_type",
                              "grade", "letter_grade", "score", "level", "outcome",
                              "academic_year", "term", "semester"):
                        v = g.get(k)
                        if v is not None and str(v).strip():
                            parts.append(f"{k}={v}")
                    lines.append(f"    {', '.join(parts)}")
                lines.append("")

            # Attendance
            att = sys_data.get("attendance", {})
            if att:
                lines.append("  Attendance:")
                total = att.get("total_sessions", 0)
                present = att.get("present", 0)
                pct = att.get("percentage", 0)
                lines.append(f"    Total sessions: {total}")
                lines.append(f"    Present: {present}")
                lines.append(f"    Attendance rate: {pct}%")
                lines.append("")

            # Qualifications
            quals = sys_data.get("qualifications", [])
            if quals:
                lines.append("  Qualifications & Awards:")
                for q in quals:
                    parts = [f"{k}={v}" for k, v in q.items() if v is not None and str(v).strip()]
                    lines.append(f"    {', '.join(parts)}")
                lines.append("")

        # Platform qualification record (cross-system, with lineage)
        platform_quals = transcript_data.get("qualifications", [])
        if platform_quals:
            lines.append("-" * 40)
            lines.append("QUALIFICATIONS")
            lines.append("-" * 40)
            for q in platform_quals:
                label = SYSTEM_LABELS.get(q.get("source_system") or "",
                                          q.get("source_system") or "")
                bits = [q.get("title") or "?"]
                if q.get("level"):
                    bits.append(f"level {q['level']}")
                if q.get("grade"):
                    bits.append(f"grade {q['grade']}")
                if q.get("awarded_on"):
                    bits.append(str(q["awarded_on"]))
                lines.append(f"  {', '.join(bits)}  [{label}]")
            lines.append("")

        # Transfer History
        transfers = transcript_data.get("transfers", [])
        if transfers:
            lines.append("-" * 40)
            lines.append("TRANSFER HISTORY")
            lines.append("-" * 40)
            for t in transfers:
                parts = [f"{k}={v}" for k, v in t.items() if v is not None and str(v).strip()]
                lines.append(f"  {', '.join(parts)}")
            lines.append("")

        lines.append("=" * 70)
        lines.append("END OF TRANSCRIPT")
        lines.append("=" * 70)
        return "\n".join(lines)

    def save_transcript(self, text, output_path):
        """Save formatted transcript text to a file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def get_transcript_summary(self, student_name):
        """Return a brief one-paragraph summary of the student's transcript."""
        transcript = self.generate_transcript(student_name)
        systems = transcript.get("systems", [])
        if not systems:
            return f"No records found for {student_name} across any education system."

        parts = []
        parts.append(f"{student_name} has records in {len(systems)} education system(s)")

        system_names = []
        total_grades = 0
        for s in systems:
            system_names.append(SYSTEM_LABELS.get(s["system"], s["system"]))
            total_grades += len(s.get("grades", []))

        parts.append(f"({', '.join(system_names)})")

        if total_grades > 0:
            parts.append(f"with {total_grades} grade/assessment record(s) in total")

        # Best attendance
        best_att = 0
        for s in systems:
            pct = s.get("attendance", {}).get("percentage", 0)
            if pct > best_att:
                best_att = pct
        if best_att > 0:
            parts.append(f"and a best attendance rate of {best_att}%")

        quals = transcript.get("qualifications", [])
        if quals:
            parts.append(f"holding {len(quals)} recorded qualification(s)")

        transfers = transcript.get("transfers", [])
        if transfers:
            parts.append(f"with {len(transfers)} recorded transfer(s)")

        return " ".join(parts) + "."

    # -----------------------------------------------------------------------
    # Per-system data collection
    # -----------------------------------------------------------------------

    def _collect_system_data(self, system, *, student_id=None, name=None,
                             unlinked_only=False):
        """Collect all transcript data for one local record in one system."""
        conn = _connect(system, self._db_paths)
        if not conn:
            return None
        try:
            row = _locate(conn, system, student_id=student_id, name=name,
                          unlinked_only=unlinked_only)
            if row is None:
                return None
            collector = {
                "primary": self._collect_primary,
                "secondary": self._collect_secondary,
                "sixth_form": self._collect_college,
                "university": self._collect_university,
            }.get(system, self._collect_generic)
            return collector(conn, system, row)
        except Exception:
            logger.debug("Transcript collect failed for %s", system,
                         exc_info=True)
            return None
        finally:
            conn.close()

    # -- Nursery / FE College / Apprenticeships -------------------------------

    def _collect_generic(self, conn, system, row):
        """Record + attendance for the systems without a bespoke collector."""
        from education_system.platform.cross_system import learner_360
        data = _blank(system, row)
        att = learner_360._attendance_for(system, conn, data["student_id"])
        if att:
            data["attendance"] = {
                "total_sessions": att["total"],
                "present": round(att["total"] * att["present_pct"] / 100),
                "percentage": att["present_pct"],
            }
        return data

    # -- Primary -------------------------------------------------------------

    def _collect_primary(self, conn, system, row):
        data = _blank(system, row)
        pid = data["student_id"]

        # Assessments
        if _table_exists(conn, "assessments"):
            try:
                rows = conn.execute(
                    "SELECT * FROM assessments WHERE pupil_id = ? ORDER BY academic_year, term",
                    (pid,),
                ).fetchall()
                data["grades"].extend([dict(r) for r in rows])
            except Exception:
                pass

        # SATs
        if _table_exists(conn, "sats_results"):
            try:
                rows = conn.execute(
                    "SELECT * FROM sats_results WHERE pupil_id = ? ORDER BY academic_year",
                    (pid,),
                ).fetchall()
                for r in rows:
                    d = dict(r)
                    data["grades"].append(d)
                    # SATs with outcome are qualifications
                    if d.get("outcome"):
                        data["qualifications"].append({
                            "type": "SATs",
                            "subject": d.get("subject", ""),
                            "outcome": d["outcome"],
                            "academic_year": d.get("academic_year", ""),
                        })
            except Exception:
                pass

        # Phonics
        if _table_exists(conn, "phonics_results"):
            try:
                rows = conn.execute(
                    "SELECT * FROM phonics_results WHERE pupil_id = ? ORDER BY academic_year",
                    (pid,),
                ).fetchall()
                data["grades"].extend([dict(r) for r in rows])
            except Exception:
                pass

        # Attendance — primary registers carry a DfE mark code, not a status.
        if _table_exists(conn, "attendance_records"):
            try:
                cols = _get_columns(conn, "attendance_records")
                data["attendance"] = _attendance_counts(
                    conn, "attendance_records", "pupil_id", pid,
                    status_col="mark" if "mark" in cols else "status")
            except Exception:
                pass

        try:
            data["transfers"] = _transfer_rows(
                conn, pid, ("pupil_id", "student_id", "source_student_id"))
        except Exception:
            pass
        return data

    # -- Secondary -----------------------------------------------------------

    def _collect_secondary(self, conn, system, row):
        data = _blank(system, row)
        rk = row.keys()
        sid = data["student_id"]
        pk = row["id"] if "id" in rk else sid

        # Grades
        if _table_exists(conn, "grades"):
            try:
                rows = conn.execute(
                    "SELECT * FROM grades WHERE student_id = ? ORDER BY academic_year, term",
                    (pk,),
                ).fetchall()
                data["grades"].extend([dict(r) for r in rows])
            except Exception:
                pass

        # Exam results
        if _table_exists(conn, "exam_results"):
            try:
                cols = _get_columns(conn, "exam_results")
                key_col = "pupil_id" if "pupil_id" in cols else "student_id"
                rows = conn.execute(
                    f"SELECT * FROM exam_results WHERE {key_col} = ? ORDER BY rowid",  # nosec B608
                    (sid if key_col == "pupil_id" else pk,),
                ).fetchall()
                for r in rows:
                    d = dict(r)
                    data["grades"].append(d)
                    grade = d.get("grade") or d.get("final_grade")
                    if grade:
                        data["qualifications"].append({
                            "type": "Exam",
                            "grade": grade,
                            "marks": d.get("marks_obtained", d.get("marks_awarded", "")),
                        })
            except Exception:
                pass

        # Attendance
        if _table_exists(conn, "attendance_records"):
            try:
                cols = _get_columns(conn, "attendance_records")
                key_col = "pupil_id" if "pupil_id" in cols else "student_id"
                data["attendance"] = _attendance_counts(
                    conn, "attendance_records", key_col,
                    sid if key_col == "pupil_id" else pk,
                    status_col="mark" if "mark" in cols else "status")
            except Exception:
                pass

        try:
            data["transfers"] = _transfer_rows(
                conn, sid, ("pupil_id", "student_id", "source_student_id"))
        except Exception:
            pass
        return data

    # -- College -------------------------------------------------------------

    def _collect_college(self, conn, system, row):
        data = _blank(system, row)
        rk = row.keys()
        sid = data["student_id"]
        pk = row["id"] if "id" in rk else sid

        # Grades
        if _table_exists(conn, "grades"):
            try:
                rows = conn.execute(
                    "SELECT * FROM grades WHERE student_id = ? ORDER BY semester, term",
                    (pk,),
                ).fetchall()
                data["grades"].extend([dict(r) for r in rows])
            except Exception:
                pass

        # Attendance (two-table join)
        if _table_exists(conn, "attendance_records"):
            try:
                join = ""
                if _table_exists(conn, "attendance_sessions"):
                    join = "JOIN attendance_sessions s ON ar.session_id = s.id"
                data["attendance"] = _attendance_counts(
                    conn, "attendance_records ar", "ar.student_id", pk,
                    status_col="ar.status", join=join)
            except Exception:
                pass

        try:
            data["transfers"] = _transfer_rows(conn, sid)
        except Exception:
            pass
        return data

    # -- University ----------------------------------------------------------

    def _collect_university(self, conn, system, row):
        data = _blank(system, row)
        rk = row.keys()
        sid = data["student_id"]
        pk = row["id"] if "id" in rk else sid

        # Grades
        if _table_exists(conn, "grades"):
            try:
                rows = conn.execute(
                    "SELECT * FROM grades WHERE student_id = ? ORDER BY rowid",
                    (pk,),
                ).fetchall()
                data["grades"].extend([dict(r) for r in rows])
            except Exception:
                pass

        # Attendance — university uses "attendance", others use "attendance_records"
        att_table = next((t for t in ("attendance", "attendance_records")
                          if _table_exists(conn, t)), None)
        if att_table:
            try:
                data["attendance"] = _attendance_counts(
                    conn, att_table, "student_id", pk)
            except Exception:
                pass

        try:
            data["transfers"] = _transfer_rows(conn, sid)
        except Exception:
            pass
        return data
