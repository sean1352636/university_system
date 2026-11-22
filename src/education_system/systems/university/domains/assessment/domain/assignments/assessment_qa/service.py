"""Assignment quality assurance: the marking-to-module-result workflow.

One service for the rules that sit between "a marker typed a mark" and "the
mark counts towards the student's module result":

* anonymous marking (candidate numbers until release)
* word limits and the over-length penalty
* moderation: sample, second mark, agree
* cohort grade release, on a date, gated on marking and moderation
* feedback turnaround (default 20 working days after the deadline)
* non-submission records (NS, counts as 0)
* formative vs summative (formative never reaches the module result)
* referral (capped at the pass mark) and deferral (uncapped) reassessment
* deadline-clash checks across a cohort
* the module roll-up into ``module_grades``, which degree audit and academic
  progress read

Grades on ``assignment_submissions.grade`` are percentages, as every existing
grading path already writes them.
"""
import logging
import math
import random
import secrets
from datetime import datetime, timedelta

from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
from education_system.systems.university.application.assessment.outcomes import (
    appeal_uncapped_resit,
    uncapped_resit_claim,
)
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import schema
from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa.word_count import count_words

logger = logging.getLogger(__name__)

PASS_MARK = 40.0
FEEDBACK_TURNAROUND_WORKING_DAYS = 20
MIN_MODERATION_SAMPLE = 5
CLASH_WINDOW_DAYS = 7
CLASH_THRESHOLD = 3

KINDS = ("summative", "formative")
REASSESSMENT_TYPES = ("referral", "deferral")

# Settings an instructor may change from the QA screens, with a coercer each.
_SETTINGS = {
    "assessment_kind": lambda v: v if v in KINDS else "summative",
    "module_weight_pct": lambda v: None if v in (None, "") else float(v),
    "anonymous_marking": lambda v: 1 if v else 0,
    "word_limit": lambda v: None if v in (None, "", 0, "0") else int(v),
    "word_limit_tolerance_pct": lambda v: float(v or 0),
    "word_limit_penalty_pct": lambda v: float(v or 0),
    "feedback_due_date": lambda v: v or None,
    "grade_release_date": lambda v: v or None,
    "moderation_required": lambda v: 1 if v else 0,
    "moderation_sample_pct": lambda v: float(v or 0),
}

# A resubmission inserts a new row and clears is_final_submission on the old
# ones; only the final row is marked, moderated and released.
_FINAL = "COALESCE(is_final_submission, 1) = 1"
_FINAL_S = "COALESCE(s.is_final_submission, 1) = 1"

_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                 "%Y-%m-%dT%H:%M", "%Y-%m-%d")


def parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text[:len(datetime.now().strftime(fmt))], fmt)
        except ValueError:
            continue
    return None


def add_working_days(start, days):
    """``start`` plus ``days`` Monday–Friday days (bank holidays not modelled)."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class AssessmentQAError(Exception):
    """A QA rule refused the action; the message is safe to show a user."""


class AssessmentQAService:

    def __init__(self, db_path=None):
        self._db_path = str(db_path) if db_path else None
        self._schema_ready = False

    # ── plumbing ────────────────────────────────────────────────────────

    @property
    def db_path(self):
        return self._db_path or str(UNIVERSITY_DEFAULT_DB_PATH)

    def _connect(self):
        conn = get_connection(self.db_path)
        if not self._schema_ready:
            self._ensure_schema(conn)
        return conn

    def _ensure_schema(self, conn):
        def columns(table):
            return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        schema.apply(conn.execute, columns)
        # Module-result standing and board locks, shared with Grade Tracking.
        from education_system.systems.university.infrastructure.database.schemas import grade_results_schema
        grade_results_schema.apply(conn.execute, columns)
        conn.commit()
        self._schema_ready = True

    def ensure_schema(self):
        conn = get_connection(self.db_path)
        try:
            self._ensure_schema(conn)
        finally:
            conn.close()

    @staticmethod
    def _assignment(conn, assignment_id):
        row = conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
        if row is None:
            raise AssessmentQAError(f"Assignment {assignment_id} not found.")
        return dict(row)

    @staticmethod
    def _is_released(assignment):
        return bool(assignment.get("grades_released_at"))

    # ── settings ────────────────────────────────────────────────────────

    def get_settings(self, assignment_id):
        conn = self._connect()
        try:
            a = self._assignment(conn, assignment_id)
        finally:
            conn.close()
        a["effective_feedback_due"] = self._feedback_due(a)
        return a

    def update_settings(self, assignment_id, **fields):
        unknown = set(fields) - set(_SETTINGS)
        if unknown:
            raise AssessmentQAError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
        values = {}
        for key, raw in fields.items():
            try:
                values[key] = _SETTINGS[key](raw)
            except (TypeError, ValueError):
                raise AssessmentQAError(f"Invalid value for {key}: {raw!r}")
        for key in ("feedback_due_date", "grade_release_date"):
            if values.get(key) and parse_date(values[key]) is None:
                raise AssessmentQAError(f"{key} must be a date like 2026-11-30.")
        weight = values.get("module_weight_pct")
        if weight is not None and not 0 <= weight <= 100:
            raise AssessmentQAError("Module weighting must be between 0 and 100.")
        if not values:
            return self.get_settings(assignment_id)
        conn = self._connect()
        try:
            self._assignment(conn, assignment_id)
            # Keys come from the _SETTINGS whitelist above, never from input.
            assignments = ", ".join(f'"{k}" = ?' for k in values)
            conn.execute(
                f"UPDATE assignments SET {assignments}, updated_at = ? WHERE id = ?",  # nosec B608
                (*values.values(), _now(), assignment_id))
            conn.commit()
        finally:
            conn.close()
        return self.get_settings(assignment_id)

    def module_weight_total(self, module_code):
        """Sum of explicit weightings of the module's first-sit summative work."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(module_weight_pct), 0) FROM assignments "
                "WHERE module_code = ? AND COALESCE(is_active, 1) = 1 "
                "AND COALESCE(assessment_kind, 'summative') = 'summative' "
                "AND reassessment_of IS NULL", (module_code,)).fetchone()
            return float(row[0] or 0)
        finally:
            conn.close()

    # ── anonymous marking ───────────────────────────────────────────────

    def is_anonymised(self, assignment_id, conn=None):
        own = conn is None
        conn = conn or self._connect()
        try:
            a = self._assignment(conn, assignment_id)
            return bool(a.get("anonymous_marking")) and not self._is_released(a)
        finally:
            if own:
                conn.close()

    def candidate_number(self, assignment_id, student_id, conn=None):
        own = conn is None
        conn = conn or self._connect()
        try:
            row = conn.execute(
                "SELECT candidate_number FROM assignment_candidate_numbers "
                "WHERE assignment_id = ? AND student_id = ?",
                (assignment_id, str(student_id))).fetchone()
            if row:
                return row[0]
            for _ in range(20):
                code = f"C{secrets.randbelow(900000) + 100000}"
                try:
                    conn.execute(
                        "INSERT INTO assignment_candidate_numbers "
                        "(assignment_id, student_id, candidate_number, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (assignment_id, str(student_id), code, _now()))
                    conn.commit()
                    return code
                except Exception:
                    conn.rollback()
                    row = conn.execute(
                        "SELECT candidate_number FROM assignment_candidate_numbers "
                        "WHERE assignment_id = ? AND student_id = ?",
                        (assignment_id, str(student_id))).fetchone()
                    if row:
                        return row[0]
            raise AssessmentQAError("Could not allocate a candidate number.")
        finally:
            if own:
                conn.close()

    def marker_label(self, assignment_id, student_id, student_name):
        """What a marker should see for this student: name, or candidate number."""
        conn = self._connect()
        try:
            if self.is_anonymised(assignment_id, conn):
                return f"Candidate {self.candidate_number(assignment_id, student_id, conn)}"
            return student_name
        finally:
            conn.close()

    def marker_labels(self, submissions):
        """Batch form for list views: ``{submission_id: label}`` from
        ``[(submission_id, student_name), ...]`` on one connection."""
        labels = {}
        if not submissions:
            return labels
        conn = self._connect()
        try:
            anonymised = {}
            for sid, name in submissions:
                row = conn.execute(
                    "SELECT assignment_id, student_id FROM assignment_submissions WHERE id = ?",
                    (sid,)).fetchone()
                if not row:
                    labels[sid] = name
                    continue
                aid, student = row
                if aid not in anonymised:
                    anonymised[aid] = self.is_anonymised(aid, conn)
                labels[sid] = (f"Candidate {self.candidate_number(aid, student, conn)}"
                               if anonymised[aid] else name)
            return labels
        finally:
            conn.close()

    def marker_label_for_submission(self, submission_id, student_name):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT assignment_id, student_id FROM assignment_submissions WHERE id = ?",
                (submission_id,)).fetchone()
        finally:
            conn.close()
        if not row:
            return student_name
        return self.marker_label(row[0], row[1], student_name)

    # ── word limits ─────────────────────────────────────────────────────

    def record_word_count(self, submission_id, word_count=None, file_path=None):
        """Store a submission's word count, counting the file if not given."""
        if word_count is None:
            word_count = count_words(file_path)
        if word_count is None:
            return None
        conn = self._connect()
        try:
            conn.execute("UPDATE assignment_submissions SET word_count = ? WHERE id = ?",
                         (int(word_count), submission_id))
            conn.commit()
        finally:
            conn.close()
        return int(word_count)

    @staticmethod
    def word_penalty(assignment, word_count):
        """Percentage points deducted for going over the word limit."""
        limit = assignment.get("word_limit")
        if not limit or word_count is None:
            return 0.0
        tolerance = float(assignment.get("word_limit_tolerance_pct") or 0)
        if word_count <= limit * (1 + tolerance / 100):
            return 0.0
        return float(assignment.get("word_limit_penalty_pct") or 0)

    def on_submitted(self, submission_id, file_path=None):
        """Bookkeeping after a student submits: count words, clear any NS record."""
        count = self.record_word_count(submission_id, file_path=file_path)
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE assignment_non_submissions SET voided = 1 WHERE (assignment_id, student_id) = "
                "(SELECT assignment_id, student_id FROM assignment_submissions WHERE id = ?)",
                (submission_id,))
            conn.commit()
        finally:
            conn.close()
        return count

    # ── marking ─────────────────────────────────────────────────────────

    def record_mark(self, submission_id, raw_pct, marker=None, feedback=None):
        """Record a marker's mark and apply the QA rules to it.

        ``raw_pct`` is the marker's percentage before any penalty. The stored
        grade has the word-limit penalty taken off and, on a referral, is
        capped at the pass mark. An academic misconduct penalty recorded on
        the submission (``misconduct_penalty``, set by
        ``application/integrity/review``) is applied last, so a re-mark
        cannot undo it. Returns what was stored and whether the mark is now
        visible to the student.
        """
        raw = max(0.0, min(100.0, float(raw_pct)))
        conn = self._connect()
        try:
            sub = conn.execute("SELECT * FROM assignment_submissions WHERE id = ?",
                               (submission_id,)).fetchone()
            if sub is None:
                raise AssessmentQAError(f"Submission {submission_id} not found.")
            sub = dict(sub)
            a = self._assignment(conn, sub["assignment_id"])

            penalty = self.word_penalty(a, sub.get("word_count"))
            grade = max(0.0, raw - penalty)
            cap = self._mark_cap(conn, a["id"], sub["student_id"])
            capped = cap is not None and grade > cap
            if capped:
                grade = cap
            misconduct = sub.get("misconduct_penalty")
            if misconduct == "zero":
                grade = 0.0
            elif misconduct in ("cap", "resubmit"):
                grade = min(grade, PASS_MARK)

            released = self._is_released(a) or self._auto_release_allowed(a)
            now = _now()
            fields = {
                "grade": round(grade, 2),
                "raw_grade": round(raw, 2),
                "word_penalty_pct": penalty or None,
                "capped": 1 if capped else 0,
                "status": "grade_released" if released else "graded",
                "graded_date": now,
            }
            if marker is not None:
                fields["graded_by"] = marker
            if feedback is not None:
                fields["feedback"] = feedback
            if released:
                fields["grade_released_at"] = now
            assignments = ", ".join(f'"{k}" = ?' for k in fields)
            conn.execute(
                f"UPDATE assignment_submissions SET {assignments} WHERE id = ?",  # nosec B608
                (*fields.values(), submission_id))
            # A sampled script re-marked before moderation keeps its first mark current.
            conn.execute(
                "UPDATE assignment_moderation SET first_mark = ?, updated_at = ? "
                "WHERE submission_id = ? AND status = 'sampled' AND second_mark IS NULL",
                (round(raw, 2), now, submission_id))
            # A student who has now been marked is not a non-submission.
            conn.execute(
                "UPDATE assignment_non_submissions SET voided = 1 "
                "WHERE assignment_id = ? AND student_id = ?",
                (a["id"], sub["student_id"]))
            conn.commit()
            # Every saved mark updates the provisional module result; the
            # exam board confirms it. Students see the mark only once released.
            self._rollup_for(conn, a, [sub["student_id"]])
            if released:
                self._sync_gradebook(a, [{"student_id": sub["student_id"], "grade": round(grade, 2)}])
            return {"grade": round(grade, 2), "raw_grade": round(raw, 2),
                    "word_penalty_pct": penalty, "capped": capped, "released": released,
                    "misconduct_penalty": misconduct}
        finally:
            conn.close()

    @staticmethod
    def _auto_release_allowed(a):
        """Per-mark release survives only where nothing else needs to happen first."""
        if not a.get("auto_release_grades"):
            return False
        if a.get("anonymous_marking") or a.get("moderation_required"):
            return False
        release_on = parse_date(a.get("grade_release_date"))
        return release_on is None or release_on <= datetime.now()

    @staticmethod
    def _mark_cap(conn, assignment_id, student_id):
        row = conn.execute(
            "SELECT attempt_type, mark_cap_pct FROM assignment_reassessments "
            "WHERE reassessment_assignment_id = ? AND student_id = ?",
            (assignment_id, str(student_id))).fetchone()
        if row and row[0] == "referral":
            return float(row[1] if row[1] is not None else PASS_MARK)
        return None

    # ── moderation ──────────────────────────────────────────────────────

    def draw_moderation_sample(self, assignment_id, sample_pct=None, drawn_by=None):
        """Pick scripts for second marking.

        Every fail is included, plus a random spread of the rest up to the
        sample size (at least five scripts, or all of them if fewer).
        """
        conn = self._connect()
        try:
            a = self._assignment(conn, assignment_id)
            if self._is_released(a):
                raise AssessmentQAError("Grades are already released.")
            pct = float(sample_pct if sample_pct is not None else a.get("moderation_sample_pct") or 10)
            marked = [dict(r) for r in conn.execute(
                "SELECT id, COALESCE(raw_grade, grade) AS mark, graded_by "
                f"FROM assignment_submissions WHERE assignment_id = ? AND grade IS NOT NULL AND {_FINAL}",
                (assignment_id,))]
            if not marked:
                raise AssessmentQAError("Nothing has been marked yet.")
            target = max(MIN_MODERATION_SAMPLE, math.ceil(len(marked) * pct / 100))
            fails = [m for m in marked if m["mark"] < PASS_MARK]
            rest = [m for m in marked if m["mark"] >= PASS_MARK]
            random.shuffle(rest)
            chosen = fails + rest[:max(0, target - len(fails))]
            now = _now()
            for m in chosen:
                conn.execute(
                    "INSERT OR IGNORE INTO assignment_moderation "
                    "(assignment_id, submission_id, first_mark, first_marker, status, "
                    " created_at, updated_at) VALUES (?, ?, ?, ?, 'sampled', ?, ?)",
                    (assignment_id, m["id"], m["mark"],
                     str(m["graded_by"]) if m["graded_by"] is not None else None, now, now))
            conn.execute("UPDATE assignments SET moderation_status = 'in_progress' WHERE id = ?",
                         (assignment_id,))
            conn.commit()
        finally:
            conn.close()
        return self.moderation_rows(assignment_id)

    def moderation_rows(self, assignment_id):
        conn = self._connect()
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT m.*, s.student_id FROM assignment_moderation m "
                "JOIN assignment_submissions s ON s.id = m.submission_id "
                "WHERE m.assignment_id = ? ORDER BY m.first_mark", (assignment_id,))]
            anonymised = self.is_anonymised(assignment_id, conn)
            for r in rows:
                r["label"] = (f"Candidate {self.candidate_number(assignment_id, r['student_id'], conn)}"
                              if anonymised else r["student_id"])
                if r["first_mark"] is not None and r["second_mark"] is not None:
                    r["difference"] = round(abs(r["first_mark"] - r["second_mark"]), 2)
                else:
                    r["difference"] = None
            return rows
        finally:
            conn.close()

    def record_second_mark(self, moderation_id, mark, marker=None, notes=None):
        mark = float(mark)
        if not 0 <= mark <= 100:
            raise AssessmentQAError("Second mark must be a percentage between 0 and 100.")
        conn = self._connect()
        try:
            row = conn.execute("SELECT status FROM assignment_moderation WHERE id = ?",
                               (moderation_id,)).fetchone()
            if row is None:
                raise AssessmentQAError("Moderation record not found.")
            if row[0] == "agreed":
                raise AssessmentQAError("This script already has an agreed mark.")
            conn.execute(
                "UPDATE assignment_moderation SET second_mark = ?, second_marker = ?, "
                "notes = COALESCE(?, notes), status = 'second_marked', updated_at = ? WHERE id = ?",
                (mark, marker, notes, _now(), moderation_id))
            conn.commit()
        finally:
            conn.close()

    def agree_mark(self, moderation_id, agreed_mark, agreed_by=None, notes=None):
        """Settle a sampled script. A changed mark is written back as the raw mark."""
        agreed = float(agreed_mark)
        if not 0 <= agreed <= 100:
            raise AssessmentQAError("Agreed mark must be a percentage between 0 and 100.")
        conn = self._connect()
        try:
            row = conn.execute("SELECT submission_id, first_mark, second_mark FROM "
                               "assignment_moderation WHERE id = ?", (moderation_id,)).fetchone()
            if row is None:
                raise AssessmentQAError("Moderation record not found.")
            if row[2] is None:
                raise AssessmentQAError("Record a second mark before agreeing one.")
            conn.execute(
                "UPDATE assignment_moderation SET agreed_mark = ?, agreed_by = ?, "
                "notes = COALESCE(?, notes), status = 'agreed', updated_at = ? WHERE id = ?",
                (agreed, agreed_by, notes, _now(), moderation_id))
            conn.commit()
            submission_id, first = row[0], row[1]
        finally:
            conn.close()
        if first is None or abs(agreed - first) > 1e-9:
            self.record_mark(submission_id, agreed)

    def complete_moderation(self, assignment_id, completed_by=None):
        conn = self._connect()
        try:
            self._assignment(conn, assignment_id)
            counts = conn.execute(
                "SELECT COUNT(*), SUM(status = 'agreed') FROM assignment_moderation "
                "WHERE assignment_id = ?", (assignment_id,)).fetchone()
            total, agreed = counts[0] or 0, counts[1] or 0
            if total == 0:
                raise AssessmentQAError("Draw a moderation sample first.")
            if agreed < total:
                raise AssessmentQAError(f"{total - agreed} sampled script(s) have no agreed mark yet.")
            conn.execute("UPDATE assignments SET moderation_status = 'complete' WHERE id = ?",
                         (assignment_id,))
            conn.commit()
        finally:
            conn.close()

    # ── release ─────────────────────────────────────────────────────────

    def release_blockers(self, assignment_id, ignore_release_date=False):
        """Why grades cannot be released yet; empty means they can."""
        conn = self._connect()
        try:
            a = self._assignment(conn, assignment_id)
            blockers = []
            if self._is_released(a):
                return ["Grades are already released."]
            unmarked = conn.execute(
                "SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = ? "
                f"AND grade IS NULL AND {_FINAL}", (assignment_id,)).fetchone()[0]
            if unmarked:
                blockers.append(f"{unmarked} submission(s) are not marked.")
            marked = conn.execute(
                "SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = ? "
                f"AND grade IS NOT NULL AND {_FINAL}", (assignment_id,)).fetchone()[0]
            if not marked:
                blockers.append("Nothing has been marked.")
            if a.get("moderation_required") and a.get("moderation_status") != "complete":
                blockers.append("Moderation is not complete.")
            release_on = parse_date(a.get("grade_release_date"))
            if not ignore_release_date and release_on and release_on > datetime.now():
                blockers.append(f"Release date is {a['grade_release_date']}.")
            return blockers
        finally:
            conn.close()

    def release_grades(self, assignment_id, released_by=None, ignore_release_date=False,
                       notify=True):
        """Release every mark on an assignment at once and roll up module results."""
        blockers = self.release_blockers(assignment_id, ignore_release_date)
        if blockers:
            raise AssessmentQAError(" ".join(blockers))
        conn = self._connect()
        try:
            a = self._assignment(conn, assignment_id)
            now = _now()
            conn.execute(
                "UPDATE assignments SET grades_released_at = ?, grades_released_by = ? WHERE id = ?",
                (now, released_by, assignment_id))
            conn.execute(
                "UPDATE assignment_submissions SET status = 'grade_released', "
                "grade_released_at = COALESCE(grade_released_at, ?) "
                "WHERE assignment_id = ? AND grade IS NOT NULL", (now, assignment_id))
            conn.commit()
            a["grades_released_at"] = now
            released = [dict(r) for r in conn.execute(
                "SELECT s.id, s.student_id, s.grade, s.feedback, st.first_name, st.last_name, "
                "       st.email_address "
                "FROM assignment_submissions s "
                "LEFT JOIN students st ON st.student_id = s.student_id "
                f"WHERE s.assignment_id = ? AND s.grade IS NOT NULL AND {_FINAL_S}", (assignment_id,))]
            ns = [r[0] for r in conn.execute(
                "SELECT student_id FROM assignment_non_submissions "
                "WHERE assignment_id = ? AND voided = 0", (assignment_id,))]
            self._rollup_for(conn, a, [r["student_id"] for r in released] + ns)
            self._sync_gradebook(a, released)
        finally:
            conn.close()
        if notify:
            self._email_release(a, released)
        return {"released": len(released), "non_submissions": len(ns)}

    def release_due(self, released_by="scheduled release"):
        """Release every assignment whose release date has passed and is ready.

        Called when the assignment GUI or CLI opens; there is no background
        scheduler. Returns ``{assignment_id: result-or-blockers}``.
        """
        conn = self._connect()
        try:
            due = [r[0] for r in conn.execute(
                "SELECT id FROM assignments WHERE grades_released_at IS NULL "
                "AND grade_release_date IS NOT NULL AND grade_release_date <> '' "
                "AND COALESCE(is_active, 1) = 1")]
        finally:
            conn.close()
        outcome = {}
        for aid in due:
            a = self.get_settings(aid)
            release_on = parse_date(a.get("grade_release_date"))
            if not release_on or release_on > datetime.now():
                continue
            blockers = self.release_blockers(aid)
            if blockers:
                outcome[aid] = {"blocked": blockers}
                continue
            try:
                outcome[aid] = self.release_grades(aid, released_by)
            except Exception as exc:
                logger.warning("Scheduled release of assignment %s failed: %s", aid, exc)
                outcome[aid] = {"blocked": [str(exc)]}
        return outcome

    def _sync_gradebook(self, a, released):
        """Mirror released, summative marks into student_grades for transcripts."""
        if (a.get("assessment_kind") or "summative") != "summative":
            return
        try:
            from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa.gradebook import (
                sync_grade_to_gradebook,
            )
        except Exception:
            return
        for r in released:
            sync_grade_to_gradebook(
                db_path=self.db_path, student_id=r["student_id"], module_code=a["module_code"],
                assessment_name=a["title"], grade_value=r["grade"], max_marks=100,
                instructor=a.get("grades_released_by"), is_final=True)

    @staticmethod
    def _email_release(a, released):
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email
            from education_system.systems.university.infrastructure.email.template_utils import render_template
        except Exception:
            return
        for r in released:
            if not r.get("email_address"):
                continue
            try:
                subject, body = render_template("assignment_grade_released", {
                    "first_name": r.get("first_name") or "",
                    "module_code": a["module_code"],
                    "module_name": a["module_code"],
                    "assignment_title": a["title"],
                    "grade_percentage": f"{r['grade']:.1f}",
                    "grade_points": f"{r['grade'] * (a.get('max_marks') or 100) / 100:.1f}",
                    "max_marks": str(a.get("max_marks") or 100),
                    "feedback": r.get("feedback") or "No additional feedback provided.",
                })
                send_email(r["email_address"], subject, body)
            except Exception:
                logger.debug("Grade release email to %s failed", r.get("student_id"), exc_info=True)

    def release_submission(self, submission_id, released_by=None):
        """Release one student's mark early (the per-submission legacy path).

        Refused when the assignment is marked anonymously, needs moderation
        or has a future release date: those are released for the whole
        cohort at once with ``release_grades``.
        """
        conn = self._connect()
        try:
            sub = conn.execute("SELECT assignment_id, student_id, grade FROM assignment_submissions "
                               "WHERE id = ?", (submission_id,)).fetchone()
            if sub is None:
                raise AssessmentQAError(f"Submission {submission_id} not found.")
            if sub[2] is None:
                raise AssessmentQAError("This submission has not been marked.")
            a = self._assignment(conn, sub[0])
            if not self._is_released(a):
                if a.get("anonymous_marking"):
                    raise AssessmentQAError("Anonymously marked work is released for the whole cohort.")
                if a.get("moderation_required"):
                    raise AssessmentQAError("This assignment needs moderation; release the cohort instead.")
                release_on = parse_date(a.get("grade_release_date"))
                if release_on and release_on > datetime.now():
                    raise AssessmentQAError(f"Grades for this assignment release on {a['grade_release_date']}.")
            now = _now()
            conn.execute("UPDATE assignment_submissions SET status = 'grade_released', "
                         "grade_released_at = COALESCE(grade_released_at, ?) WHERE id = ?",
                         (now, submission_id))
            conn.commit()
            self._rollup_for(conn, a, [sub[1]])
            self._sync_gradebook(a, [{"student_id": sub[1], "grade": sub[2]}])
            return True
        finally:
            conn.close()

    def refresh_module_result(self, submission_id):
        """Recompute the module result after a mark was changed or cleared elsewhere."""
        conn = self._connect()
        try:
            row = conn.execute("SELECT assignment_id, student_id FROM assignment_submissions "
                               "WHERE id = ?", (submission_id,)).fetchone()
            if row:
                self._rollup_for(conn, self._assignment(conn, row[0]), [row[1]])
        finally:
            conn.close()

    # ── feedback turnaround ─────────────────────────────────────────────

    @staticmethod
    def _feedback_due(a):
        if a.get("feedback_due_date"):
            return a["feedback_due_date"]
        due = parse_date(a.get("due_date"))
        if not due:
            return None
        return add_working_days(due, FEEDBACK_TURNAROUND_WORKING_DAYS).strftime("%Y-%m-%d")

    def feedback_turnaround_report(self, include_released=False):
        conn = self._connect()
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT a.id, a.module_code, a.title, a.due_date, a.feedback_due_date, "
                "       a.grades_released_at, "
                f"       (SELECT COUNT(*) FROM assignment_submissions s WHERE s.assignment_id = a.id AND {_FINAL_S}) AS submissions, "
                "       (SELECT COUNT(*) FROM assignment_submissions s WHERE s.assignment_id = a.id "
                f"                                   AND s.grade IS NOT NULL AND {_FINAL_S}) AS marked "
                "FROM assignments a WHERE COALESCE(a.is_active, 1) = 1 ORDER BY a.due_date")]
        finally:
            conn.close()
        today = datetime.now()
        report = []
        for r in rows:
            if r["grades_released_at"] and not include_released:
                continue
            r["feedback_due"] = self._feedback_due(r)
            due = parse_date(r["feedback_due"])
            r["overdue"] = bool(due and due < today and not r["grades_released_at"])
            r["days_left"] = (due - today).days if due else None
            report.append(r)
        return report

    # ── non-submission ──────────────────────────────────────────────────

    def _cohort(self, conn, module_code):
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT student_id FROM student_modules WHERE module_code = ? "
            "AND student_id IS NOT NULL "
            "AND LOWER(COALESCE(status, 'enrolled')) NOT IN "
            "    ('withdrawn', 'dropped', 'cancelled', 'interrupted', 'transferred')",
            (module_code,))]

    def _effective_deadline(self, conn, a, student_id):
        deadline = parse_date(a.get("due_date"))
        for (new_due,) in conn.execute(
                "SELECT new_due_date FROM extension_requests WHERE assignment_id = ? "
                "AND student_id = ? AND LOWER(status) = 'approved'", (a["id"], str(student_id))):
            extended = parse_date(new_due)
            if extended and (deadline is None or extended > deadline):
                deadline = extended
        return deadline

    def find_non_submissions(self, assignment_id):
        """Enrolled students with no submission whose deadline has passed."""
        conn = self._connect()
        try:
            a = self._assignment(conn, assignment_id)
            cohort = self._cohort(conn, a["module_code"])
            reassessed = {r[0] for r in conn.execute(
                "SELECT student_id FROM assignment_reassessments WHERE reassessment_assignment_id = ?",
                (assignment_id,))}
            if a.get("reassessment_of"):
                cohort = [s for s in cohort if s in reassessed]
            submitted = {r[0] for r in conn.execute(
                "SELECT student_id FROM assignment_submissions WHERE assignment_id = ? "
                "AND COALESCE(status, '') <> 'withdrawn'",
                (assignment_id,))}
            now = datetime.now()
            missing = []
            for sid in cohort:
                if sid in submitted:
                    continue
                deadline = self._effective_deadline(conn, a, sid)
                if deadline and deadline < now:
                    missing.append({"student_id": sid,
                                    "deadline": deadline.strftime("%Y-%m-%d %H:%M")})
            return missing
        finally:
            conn.close()

    def record_non_submissions(self, assignment_id, recorded_by=None):
        missing = self.find_non_submissions(assignment_id)
        conn = self._connect()
        try:
            a = self._assignment(conn, assignment_id)
            now = _now()
            for m in missing:
                conn.execute(
                    "INSERT INTO assignment_non_submissions "
                    "(assignment_id, student_id, code, recorded_at, recorded_by) "
                    "VALUES (?, ?, 'NS', ?, ?) "
                    "ON CONFLICT (assignment_id, student_id) DO UPDATE SET voided = 0",
                    (assignment_id, m["student_id"], now, recorded_by))
            conn.commit()
            if self._is_released(a):
                self._rollup_for(conn, a, [m["student_id"] for m in missing])
        finally:
            conn.close()
        return len(missing)

    def non_submissions(self, assignment_id):
        conn = self._connect()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT n.*, st.first_name, st.last_name FROM assignment_non_submissions n "
                "LEFT JOIN students st ON st.student_id = n.student_id "
                "WHERE n.assignment_id = ? AND n.voided = 0 ORDER BY n.student_id",
                (assignment_id,))]
        finally:
            conn.close()

    def void_non_submission(self, assignment_id, student_id):
        conn = self._connect()
        try:
            a = self._assignment(conn, assignment_id)
            conn.execute("UPDATE assignment_non_submissions SET voided = 1 "
                         "WHERE assignment_id = ? AND student_id = ?",
                         (assignment_id, str(student_id)))
            conn.commit()
            if self._is_released(a):
                self._rollup_for(conn, a, [str(student_id)])
        finally:
            conn.close()

    # ── reassessment ────────────────────────────────────────────────────

    def reassessment_candidates(self, assignment_id, pass_mark=PASS_MARK):
        """Students who failed or did not submit, with the sitting they are due.

        An uncapped deferral is suggested where a mitigating-circumstances
        panel granted one for this module; otherwise a capped referral.
        """
        conn = self._connect()
        try:
            a = self._assignment(conn, assignment_id)
            if not self._is_released(a):
                raise AssessmentQAError("Release grades before arranging reassessment.")
            rows = [dict(r) for r in conn.execute(
                "SELECT student_id, grade AS mark, 'fail' AS reason FROM assignment_submissions "
                f"WHERE assignment_id = ? AND grade IS NOT NULL AND grade < ? AND {_FINAL} "
                "UNION "
                "SELECT student_id, 0 AS mark, 'non-submission' AS reason "
                "FROM assignment_non_submissions WHERE assignment_id = ? AND voided = 0",
                (assignment_id, pass_mark, assignment_id))]
            already = {r[0] for r in conn.execute(
                "SELECT r.student_id FROM assignment_reassessments r "
                "WHERE r.original_assignment_id = ?", (assignment_id,))}
        finally:
            conn.close()
        out = []
        for r in rows:
            if r["student_id"] in already:
                continue
            claim = self._uncapped_claim(r["student_id"], a["module_code"])
            # An upheld academic appeal can also grant the uncapped sitting.
            appeal = appeal_uncapped_resit(r["student_id"], a["module_code"])
            r["suggested_type"] = "deferral" if claim or appeal else "referral"
            r["mc_claim_id"] = claim
            r["appeal_id"] = appeal
            out.append(r)
        return out

    @staticmethod
    def _uncapped_claim(student_id, module_code):
        return uncapped_resit_claim(student_id, module_code)

    def create_reassessment(self, assignment_id, students, due_date, created_by=None):
        """Create one reassessment sitting for the given students.

        ``students`` is a list of ``{"student_id", "attempt_type", "mc_claim_id"?}``.
        The sitting is a new assignment linked back to the original; its mark
        replaces the original in the module result, capped for referrals.
        """
        if not students:
            raise AssessmentQAError("Choose at least one student.")
        if parse_date(due_date) is None:
            raise AssessmentQAError("Give the reassessment a due date like 2027-01-15 23:59.")
        for s in students:
            if s.get("attempt_type") not in REASSESSMENT_TYPES:
                raise AssessmentQAError(f"Attempt type must be one of {REASSESSMENT_TYPES}.")
        conn = self._connect()
        try:
            a = self._assignment(conn, assignment_id)
            if a.get("reassessment_of"):
                raise AssessmentQAError("Create reassessments from the original assignment.")
            now = _now()
            kind = "referral" if all(s["attempt_type"] == "referral" for s in students) else (
                "deferral" if all(s["attempt_type"] == "deferral" for s in students) else "mixed")
            copy = {k: a.get(k) for k in (
                "module_code", "description", "instructions", "max_marks", "file_types_allowed",
                "max_file_size_mb", "assignment_type", "allow_late_submission",
                "late_penalty_per_day", "rubric_id", "anonymous_marking", "word_limit",
                "word_limit_tolerance_pct", "word_limit_penalty_pct", "moderation_required",
                "moderation_sample_pct") if k in a}
            copy.update({
                "title": f"{a['title']} — Reassessment",
                "due_date": due_date,
                "created_by": created_by if isinstance(created_by, int) else a.get("created_by"),
                "created_at": now, "updated_at": now, "is_active": 1,
                "assessment_kind": "summative", "module_weight_pct": None,
                "reassessment_of": assignment_id, "reassessment_type": kind,
                "auto_release_grades": 0,
            })
            cols = ", ".join(f'"{k}"' for k in copy)
            marks = ", ".join("?" for _ in copy)
            cur = conn.execute(f"INSERT INTO assignments ({cols}) VALUES ({marks})",  # nosec B608
                               tuple(copy.values()))
            new_id = cur.lastrowid
            for s in students:
                conn.execute(
                    "INSERT INTO assignment_reassessments (original_assignment_id, "
                    "reassessment_assignment_id, student_id, attempt_type, mark_cap_pct, "
                    "mc_claim_id, created_at, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (assignment_id, new_id, str(s["student_id"]), s["attempt_type"],
                     PASS_MARK if s["attempt_type"] == "referral" else None,
                     s.get("mc_claim_id"), now, str(created_by) if created_by is not None else None))
            conn.commit()
            return new_id
        finally:
            conn.close()

    def reassessments(self, assignment_id=None):
        conn = self._connect()
        try:
            sql = ("SELECT r.*, o.title AS original_title, n.title AS reassessment_title, "
                   "       n.due_date, s.grade AS mark "
                   "FROM assignment_reassessments r "
                   "JOIN assignments o ON o.id = r.original_assignment_id "
                   "JOIN assignments n ON n.id = r.reassessment_assignment_id "
                   "LEFT JOIN assignment_submissions s ON s.assignment_id = n.id "
                   "     AND s.student_id = r.student_id ")
            params = ()
            if assignment_id:
                sql += "WHERE r.original_assignment_id = ? "
                params = (assignment_id,)
            return [dict(r) for r in conn.execute(sql + "ORDER BY r.created_at DESC", params)]
        finally:
            conn.close()

    def visible_to_student(self, assignment_id, student_id):
        """A reassessment sitting is only visible to the students it was set for."""
        conn = self._connect()
        try:
            a = self._assignment(conn, assignment_id)
            if not a.get("reassessment_of"):
                return True
            return conn.execute(
                "SELECT 1 FROM assignment_reassessments WHERE reassessment_assignment_id = ? "
                "AND student_id = ?", (assignment_id, str(student_id))).fetchone() is not None
        finally:
            conn.close()

    def hidden_reassessment_ids(self, student_id):
        """Reassessment sittings this student was not set — filter these from student lists."""
        conn = self._connect()
        try:
            return {r[0] for r in conn.execute(
                "SELECT a.id FROM assignments a WHERE a.reassessment_of IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM assignment_reassessments r "
                "                WHERE r.reassessment_assignment_id = a.id AND r.student_id = ?)",
                (str(student_id),))}
        finally:
            conn.close()

    # ── deadline clashes ────────────────────────────────────────────────

    def deadline_clashes(self, module_code, due_date, exclude_assignment_id=None,
                         window_days=CLASH_WINDOW_DAYS, threshold=CLASH_THRESHOLD):
        """Students who would have ``threshold`` or more summative deadlines
        within ``window_days`` of ``due_date`` (counting this one)."""
        due = parse_date(due_date)
        if not due:
            return []
        lo = (due - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
        hi = (due + timedelta(days=window_days)).strftime("%Y-%m-%d 23:59:59")
        conn = self._connect()
        try:
            cohort = self._cohort(conn, module_code)
            clashes = []
            for sid in cohort:
                others = [dict(r) for r in conn.execute(
                    "SELECT a.id, a.module_code, a.title, a.due_date FROM assignments a "
                    "JOIN student_modules sm ON sm.module_code = a.module_code "
                    "WHERE sm.student_id = ? AND COALESCE(a.is_active, 1) = 1 "
                    "AND COALESCE(a.assessment_kind, 'summative') = 'summative' "
                    "AND a.reassessment_of IS NULL "
                    "AND a.due_date BETWEEN ? AND ? AND a.id <> COALESCE(?, -1)",
                    (sid, lo, hi, exclude_assignment_id))]
                if len(others) + 1 >= threshold:
                    clashes.append({"student_id": sid, "deadlines": others})
            return clashes
        finally:
            conn.close()

    def clash_report(self, window_days=CLASH_WINDOW_DAYS, threshold=CLASH_THRESHOLD):
        """Upcoming assignments whose cohort would be over the threshold."""
        conn = self._connect()
        try:
            upcoming = [dict(r) for r in conn.execute(
                "SELECT id, module_code, title, due_date FROM assignments "
                "WHERE COALESCE(is_active, 1) = 1 AND reassessment_of IS NULL "
                "AND COALESCE(assessment_kind, 'summative') = 'summative' "
                "AND due_date >= ? ORDER BY due_date", (datetime.now().strftime("%Y-%m-%d"),))]
        finally:
            conn.close()
        report = []
        for a in upcoming:
            hits = self.deadline_clashes(a["module_code"], a["due_date"], a["id"],
                                         window_days, threshold)
            if hits:
                report.append({**a, "students_affected": len(hits),
                               "worst": max(len(h["deadlines"]) + 1 for h in hits)})
        return report

    # ── module roll-up ──────────────────────────────────────────────────

    def rollup_module_grade(self, student_id, module_code):
        conn = self._connect()
        try:
            return self._rollup(conn, str(student_id), module_code)
        finally:
            conn.close()

    def _rollup_for(self, conn, a, student_ids):
        module = a["module_code"]
        if a.get("reassessment_of"):
            module = self._assignment(conn, a["reassessment_of"])["module_code"]
        if (a.get("assessment_kind") or "summative") != "summative":
            return
        for sid in dict.fromkeys(str(s) for s in student_ids if s):
            try:
                self._rollup(conn, sid, module)
            except Exception:
                logger.warning("Module roll-up failed for %s/%s", sid, module, exc_info=True)

    def _rollup(self, conn, student_id, module_code):
        """Recalculate the module result with the single combined calculation
        (assignments and exams together) in ``application/assessment/module_results``."""
        from education_system.systems.university.application.assessment import module_results
        result = module_results.recompute(conn, student_id, module_code)
        conn.commit()
        if result:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    publish, EVENT_GRADE_CHANGED,
                )
                publish(EVENT_GRADE_CHANGED, student_id=student_id, module_code=module_code,
                        percentage=result["final_score"], source="module_result")
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        return result


def apply_mark_rules(submission_id, percentage, marker=None, feedback=None, db_path=None):
    """Run a just-saved mark through the QA rules, for GUI and CLI callers.

    Call it after the caller's own transaction has committed. If the service
    cannot run, the mark is treated as released as entered (the behaviour
    before these rules existed) so marking never silently stops working.
    """
    try:
        return AssessmentQAService(db_path).record_mark(
            submission_id, percentage, marker=marker, feedback=feedback)
    except Exception:
        logger.warning("Assessment QA rules not applied to submission %s", submission_id,
                       exc_info=True)
        return {"grade": percentage, "raw_grade": percentage, "word_penalty_pct": 0,
                "capped": False, "released": True}


def mark_note(result):
    """One line telling the marker what the rules did to their mark."""
    notes = []
    if result.get("word_penalty_pct"):
        notes.append(f"{result['word_penalty_pct']:g} points deducted for exceeding the word limit")
    if result.get("capped"):
        notes.append("capped at the referral pass mark")
    if result.get("misconduct_penalty") == "zero":
        notes.append("set to zero by an academic misconduct decision")
    elif result.get("misconduct_penalty"):
        notes.append("capped at the pass mark by an academic misconduct decision")
    if not result.get("released"):
        notes.append("held until grades are released for this assignment")
    return ("; ".join(notes).capitalize() + ".") if notes else ""
