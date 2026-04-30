"""Exam Portal Service — core business logic for online examinations.

Handles exam lifecycle: creation, publishing, student attempts, answer
collection, auto-grading, manual grading, results and analytics.
"""

import json
import logging
import random
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import (
    get_connection,
    sqlite3,
)

logger = logging.getLogger(__name__)

# ── Schema bootstrap ────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS exam_portal_exams (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    description     TEXT,
    module_code     TEXT,
    created_by      TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'draft',
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    start_time      TEXT,
    end_time        TEXT,
    pass_mark       REAL    DEFAULT 50.0,
    total_marks     REAL    DEFAULT 100.0,
    shuffle_questions INTEGER DEFAULT 0,
    shuffle_answers   INTEGER DEFAULT 0,
    show_results    TEXT    DEFAULT 'after_submit',
    max_attempts    INTEGER DEFAULT 1,
    allow_review    INTEGER DEFAULT 1,
    auto_submit     INTEGER DEFAULT 1,
    instructions    TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    published_at    TEXT
);

CREATE TABLE IF NOT EXISTS exam_portal_questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id         INTEGER NOT NULL,
    question_type   TEXT    NOT NULL DEFAULT 'mcq',
    question_text   TEXT    NOT NULL,
    options_json    TEXT,
    correct_answer  TEXT,
    marks           REAL    NOT NULL DEFAULT 1.0,
    order_index     INTEGER DEFAULT 0,
    explanation     TEXT,
    difficulty      TEXT    DEFAULT 'medium',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (exam_id) REFERENCES exam_portal_exams(id)
);

CREATE TABLE IF NOT EXISTS exam_portal_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id         INTEGER NOT NULL,
    student_id      TEXT    NOT NULL,
    student_name    TEXT,
    access_token    TEXT    UNIQUE,
    status          TEXT    NOT NULL DEFAULT 'in_progress',
    started_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    submitted_at    TEXT,
    auto_submitted  INTEGER DEFAULT 0,
    time_remaining  INTEGER,
    ip_address      TEXT,
    integrity_flags INTEGER DEFAULT 0,
    score           REAL,
    percentage      REAL,
    passed          INTEGER,
    graded_at       TEXT,
    graded_by       TEXT,
    FOREIGN KEY (exam_id) REFERENCES exam_portal_exams(id)
);

CREATE TABLE IF NOT EXISTS exam_portal_answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      INTEGER NOT NULL,
    question_id     INTEGER NOT NULL,
    answer_text     TEXT,
    is_correct      INTEGER,
    marks_awarded   REAL,
    feedback        TEXT,
    flagged         INTEGER DEFAULT 0,
    time_spent_secs INTEGER DEFAULT 0,
    answered_at     TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (attempt_id) REFERENCES exam_portal_attempts(id),
    FOREIGN KEY (question_id) REFERENCES exam_portal_questions(id)
);

CREATE TABLE IF NOT EXISTS exam_portal_integrity_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      INTEGER NOT NULL,
    event_type      TEXT    NOT NULL,
    event_data      TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (attempt_id) REFERENCES exam_portal_attempts(id)
);

CREATE INDEX IF NOT EXISTS idx_ep_questions_exam ON exam_portal_questions(exam_id);
CREATE INDEX IF NOT EXISTS idx_ep_attempts_exam ON exam_portal_attempts(exam_id);
CREATE INDEX IF NOT EXISTS idx_ep_attempts_student ON exam_portal_attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_ep_answers_attempt ON exam_portal_answers(attempt_id);
"""


class ExamPortalService:
    """Core service for the exam portal."""

    def __init__(self):
        self._ensure_tables()

    def _ensure_tables(self):
        try:
            with get_connection() as conn:
                conn.executescript(_SCHEMA_SQL)
                conn.commit()
        except Exception as e:
            logger.error("Failed to init exam portal tables: %s", e)

    # ── Import from Exam Scheduler ──────────────────────────────────

    def sync_from_scheduler(self, created_by: str = "scheduler") -> Dict:
        """Import exams from the exam scheduler's ``exams`` table.

        Creates a portal exam for each scheduler exam that doesn't already
        have one (matched by module_code + date + start_time).  Returns a
        dict with ``imported`` and ``skipped`` counts.
        """
        imported = 0
        skipped = 0
        try:
            with get_connection() as conn:
                # Check if the scheduler's exams table exists
                tbl = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='exams'"
                ).fetchone()
                if not tbl:
                    return {"imported": 0, "skipped": 0, "error": "Exam scheduler table not found"}

                rows = conn.execute(
                    "SELECT id, module_code, module_name, date, start_time, end_time, "
                    "room, instructor_name, students_enrolled FROM exams ORDER BY date, start_time"
                ).fetchall()

                for row in rows:
                    sched_id = row[0]
                    module_code = row[1] or ""
                    module_name = row[2] or module_code
                    date = row[3] or ""
                    start_time = row[4] or ""
                    end_time = row[5] or ""
                    room = row[6] or ""
                    instructor = row[7] or ""
                    students = row[8] or 0

                    # Build a title from the scheduler data
                    title = f"{module_name} Exam" if module_name else f"{module_code} Exam"

                    # Calculate duration from start/end time
                    duration = 60  # default
                    try:
                        from datetime import datetime as _dt
                        fmt = "%H:%M"
                        st = _dt.strptime(start_time, fmt)
                        et = _dt.strptime(end_time, fmt)
                        diff = (et - st).seconds // 60
                        if diff > 0:
                            duration = diff
                    except Exception:
                        pass

                    # Build start/end datetime strings
                    start_dt = f"{date} {start_time}" if date and start_time else None
                    end_dt = f"{date} {end_time}" if date and end_time else None

                    # Check if already imported (match on module_code + date + start_time)
                    existing = conn.execute(
                        "SELECT id FROM exam_portal_exams WHERE module_code = ? "
                        "AND start_time = ?",
                        (module_code, start_dt),
                    ).fetchone()
                    if existing:
                        skipped += 1
                        continue

                    # Create the portal exam
                    conn.execute(
                        """INSERT INTO exam_portal_exams
                           (title, description, module_code, created_by, duration_minutes,
                            start_time, end_time, status, instructions)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?)""",
                        (title,
                         f"Scheduled exam for {module_name}. Room: {room}. Instructor: {instructor}.",
                         module_code, created_by, duration,
                         start_dt, end_dt,
                         f"Room: {room}\nInstructor: {instructor}\nStudents enrolled: {students}"),
                    )
                    imported += 1

                conn.commit()
        except Exception as e:
            logger.error("Error syncing from scheduler: %s", e)
            return {"imported": imported, "skipped": skipped, "error": str(e)}

        return {"imported": imported, "skipped": skipped}

    # ── Exam CRUD ───────────────────────────────────────────────────

    def create_exam(self, title: str, created_by: str, **kwargs) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO exam_portal_exams
                   (title, description, module_code, created_by, duration_minutes,
                    start_time, end_time, pass_mark, total_marks, shuffle_questions,
                    shuffle_answers, show_results, max_attempts, instructions, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')""",
                (title, kwargs.get("description"), kwargs.get("module_code"),
                 created_by, kwargs.get("duration_minutes", 60),
                 kwargs.get("start_time"), kwargs.get("end_time"),
                 kwargs.get("pass_mark", 50.0), kwargs.get("total_marks", 100.0),
                 kwargs.get("shuffle_questions", 0), kwargs.get("shuffle_answers", 0),
                 kwargs.get("show_results", "after_submit"),
                 kwargs.get("max_attempts", 1), kwargs.get("instructions")),
            )
            conn.commit()
            return cursor.lastrowid

    def update_exam(self, exam_id: int, **kwargs) -> bool:
        fields = []
        values = []
        allowed = [
            "title", "description", "module_code", "duration_minutes",
            "start_time", "end_time", "pass_mark", "total_marks",
            "shuffle_questions", "shuffle_answers", "show_results",
            "max_attempts", "instructions", "allow_review", "auto_submit",
        ]
        for key in allowed:
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])
        if not fields:
            return False
        fields.append("updated_at = datetime('now')")
        values.append(exam_id)
        with get_connection() as conn:
            conn.execute(
                f"UPDATE exam_portal_exams SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
        return True

    def publish_exam(self, exam_id: int) -> bool:
        exam = self.get_exam(exam_id)
        if not exam:
            return False
        try:
            from education_system.university_system.modules.services.integration_bus import (
                is_exam_within_term,
            )
            if not is_exam_within_term(exam.get("start_time"), exam.get("end_time")):
                return False
        except Exception:
            pass
        with get_connection() as conn:
            conn.execute(
                "UPDATE exam_portal_exams SET status = 'published', "
                "published_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                (exam_id,),
            )
            conn.commit()
        try:
            from education_system.university_system.modules.services.integration_bus import (
                publish_exam_event,
            )
            publish_exam_event(
                exam_id, action="published",
                module_code=exam.get("module_code"),
                exam_title=exam.get("title"),
                start_time=exam.get("start_time"),
                duration_minutes=exam.get("duration_minutes"),
                pass_mark=exam.get("pass_mark"),
            )
        except Exception:
            pass
        return True

    def unpublish_exam(self, exam_id: int) -> bool:
        with get_connection() as conn:
            conn.execute(
                "UPDATE exam_portal_exams SET status = 'draft', "
                "updated_at = datetime('now') WHERE id = ?",
                (exam_id,),
            )
            conn.commit()
        return True

    def delete_exam(self, exam_id: int) -> bool:
        with get_connection() as conn:
            conn.execute("DELETE FROM exam_portal_answers WHERE attempt_id IN "
                         "(SELECT id FROM exam_portal_attempts WHERE exam_id = ?)", (exam_id,))
            conn.execute("DELETE FROM exam_portal_integrity_events WHERE attempt_id IN "
                         "(SELECT id FROM exam_portal_attempts WHERE exam_id = ?)", (exam_id,))
            conn.execute("DELETE FROM exam_portal_attempts WHERE exam_id = ?", (exam_id,))
            conn.execute("DELETE FROM exam_portal_questions WHERE exam_id = ?", (exam_id,))
            conn.execute("DELETE FROM exam_portal_exams WHERE id = ?", (exam_id,))
            conn.commit()
        return True

    def get_exam(self, exam_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM exam_portal_exams WHERE id = ?", (exam_id,)).fetchone()
            if not row:
                return None
            return dict(row)

    def list_exams(self, status: str = None, module_code: str = None,
                   created_by: str = None) -> List[Dict]:
        query = "SELECT * FROM exam_portal_exams WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if module_code:
            query += " AND module_code = ?"
            params.append(module_code)
        if created_by:
            query += " AND created_by = ?"
            params.append(created_by)
        query += " ORDER BY created_at DESC"
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    def list_available_exams(self, student_id: str) -> List[Dict]:
        """List published exams available to student (within time window, attempts remaining)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT e.*, COUNT(a.id) as attempt_count
                   FROM exam_portal_exams e
                   LEFT JOIN exam_portal_attempts a ON a.exam_id = e.id AND a.student_id = ?
                   WHERE e.status = 'published'
                     AND (e.start_time IS NULL OR e.start_time <= ?)
                     AND (e.end_time IS NULL OR e.end_time >= ?)
                   GROUP BY e.id
                   HAVING attempt_count < e.max_attempts
                   ORDER BY e.start_time""",
                (student_id, now, now),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Questions ───────────────────────────────────────────────────

    def add_question(self, exam_id: int, question_type: str, question_text: str,
                     marks: float = 1.0, **kwargs) -> int:
        options = kwargs.get("options")
        options_json = json.dumps(options) if options else None
        with get_connection() as conn:
            # Get next order index
            row = conn.execute(
                "SELECT COALESCE(MAX(order_index), 0) + 1 FROM exam_portal_questions WHERE exam_id = ?",
                (exam_id,),
            ).fetchone()
            order_index = row[0] if row else 1

            cursor = conn.execute(
                """INSERT INTO exam_portal_questions
                   (exam_id, question_type, question_text, options_json,
                    correct_answer, marks, order_index, explanation, difficulty)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (exam_id, question_type, question_text, options_json,
                 kwargs.get("correct_answer"), marks, order_index,
                 kwargs.get("explanation"), kwargs.get("difficulty", "medium")),
            )
            conn.commit()
            return cursor.lastrowid

    def update_question(self, question_id: int, **kwargs) -> bool:
        fields, values = [], []
        for key in ["question_type", "question_text", "correct_answer",
                     "marks", "order_index", "explanation", "difficulty"]:
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])
        if "options" in kwargs:
            fields.append("options_json = ?")
            values.append(json.dumps(kwargs["options"]))
        if not fields:
            return False
        values.append(question_id)
        with get_connection() as conn:
            conn.execute(
                f"UPDATE exam_portal_questions SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            conn.commit()
        return True

    def delete_question(self, question_id: int) -> bool:
        with get_connection() as conn:
            conn.execute("DELETE FROM exam_portal_answers WHERE question_id = ?", (question_id,))
            conn.execute("DELETE FROM exam_portal_questions WHERE id = ?", (question_id,))
            conn.commit()
        return True

    def get_questions(self, exam_id: int, shuffle: bool = False) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM exam_portal_questions WHERE exam_id = ? ORDER BY order_index",
                (exam_id,),
            ).fetchall()
            questions = []
            for r in rows:
                q = dict(r)
                if q.get("options_json"):
                    q["options"] = json.loads(q["options_json"])
                else:
                    q["options"] = []
                questions.append(q)

            if shuffle:
                random.shuffle(questions)
                for q in questions:
                    if q["options"] and q.get("question_type") in ("mcq", "true_false"):
                        random.shuffle(q["options"])
            return questions

    def get_question_count(self, exam_id: int) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM exam_portal_questions WHERE exam_id = ?", (exam_id,)
            ).fetchone()
            return row[0]

    # ── Exam Attempts ───────────────────────────────────────────────

    def start_attempt(self, exam_id: int, student_id: str,
                      student_name: str = None, ip_address: str = None) -> Optional[Dict]:
        exam = self.get_exam(exam_id)
        if not exam or exam["status"] != "published":
            return None
        try:
            from education_system.university_system.modules.services.integration_bus import (
                can_student_start_exam,
            )
            allowed, reason = can_student_start_exam(student_id)
            if not allowed:
                return {"error": "blocked", "reason": reason}
        except Exception:
            pass

        # Check for existing in-progress attempt first, then limit
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT * FROM exam_portal_attempts WHERE exam_id = ? AND student_id = ? AND status = 'in_progress'",
                (exam_id, student_id),
            ).fetchone()
            if existing:
                return dict(existing)

            # Count completed attempts against limit
            count = conn.execute(
                "SELECT COUNT(*) FROM exam_portal_attempts WHERE exam_id = ? AND student_id = ? AND status != 'in_progress'",
                (exam_id, student_id),
            ).fetchone()[0]
            if count >= exam["max_attempts"]:
                return None

            token = secrets.token_urlsafe(32)
            cursor = conn.execute(
                """INSERT INTO exam_portal_attempts
                   (exam_id, student_id, student_name, access_token, ip_address,
                    time_remaining, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'in_progress')""",
                (exam_id, student_id, student_name, token, ip_address,
                 exam["duration_minutes"] * 60),
            )
            conn.commit()

            return {
                "id": cursor.lastrowid,
                "exam_id": exam_id,
                "access_token": token,
                "time_remaining": exam["duration_minutes"] * 60,
                "status": "in_progress",
            }

    def save_answer(self, attempt_id: int, question_id: int, answer_text: str,
                    flagged: bool = False, time_spent: int = 0) -> bool:
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM exam_portal_answers WHERE attempt_id = ? AND question_id = ?",
                (attempt_id, question_id),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE exam_portal_answers
                       SET answer_text = ?, flagged = ?, time_spent_secs = ?,
                           answered_at = datetime('now')
                       WHERE id = ?""",
                    (answer_text, int(flagged), time_spent, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO exam_portal_answers
                       (attempt_id, question_id, answer_text, flagged, time_spent_secs)
                       VALUES (?, ?, ?, ?, ?)""",
                    (attempt_id, question_id, answer_text, int(flagged), time_spent),
                )
            conn.commit()
        return True

    def get_answers(self, attempt_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM exam_portal_answers WHERE attempt_id = ? ORDER BY question_id",
                (attempt_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def submit_attempt(self, attempt_id: int, auto: bool = False) -> Dict:
        """Submit an attempt and auto-grade objective questions."""
        with get_connection() as conn:
            attempt = conn.execute(
                "SELECT * FROM exam_portal_attempts WHERE id = ?", (attempt_id,)
            ).fetchone()
            if not attempt:
                return {"error": "Attempt not found"}

            exam = conn.execute(
                "SELECT * FROM exam_portal_exams WHERE id = ?", (attempt["exam_id"],)
            ).fetchone()

            # Auto-grade objective questions
            questions = conn.execute(
                "SELECT * FROM exam_portal_questions WHERE exam_id = ?",
                (attempt["exam_id"],),
            ).fetchall()

            total_score = 0.0
            total_marks = 0.0
            needs_manual = False

            for q in questions:
                total_marks += q["marks"]
                answer = conn.execute(
                    "SELECT * FROM exam_portal_answers WHERE attempt_id = ? AND question_id = ?",
                    (attempt_id, q["id"]),
                ).fetchone()

                if not answer or not answer["answer_text"]:
                    conn.execute(
                        """INSERT OR IGNORE INTO exam_portal_answers
                           (attempt_id, question_id, answer_text, is_correct, marks_awarded)
                           VALUES (?, ?, '', 0, 0)""",
                        (attempt_id, q["id"]),
                    )
                    continue

                qtype = q["question_type"]
                if qtype in ("mcq", "true_false"):
                    correct = (answer["answer_text"].strip().lower()
                               == (q["correct_answer"] or "").strip().lower())
                    awarded = q["marks"] if correct else 0
                    total_score += awarded
                    conn.execute(
                        "UPDATE exam_portal_answers SET is_correct = ?, marks_awarded = ?, "
                        "feedback = ? WHERE id = ?",
                        (int(correct), awarded,
                         "Correct" if correct else f"Incorrect. Answer: {q['correct_answer']}",
                         answer["id"]),
                    )
                elif qtype == "fill_blank":
                    correct = (answer["answer_text"].strip().lower()
                               == (q["correct_answer"] or "").strip().lower())
                    awarded = q["marks"] if correct else 0
                    total_score += awarded
                    conn.execute(
                        "UPDATE exam_portal_answers SET is_correct = ?, marks_awarded = ?, "
                        "feedback = ? WHERE id = ?",
                        (int(correct), awarded,
                         "Correct" if correct else f"Expected: {q['correct_answer']}",
                         answer["id"]),
                    )
                else:
                    # essay, short_answer, file_upload — needs manual grading
                    needs_manual = True

            percentage = (total_score / total_marks * 100) if total_marks > 0 else 0
            passed = 1 if percentage >= (exam["pass_mark"] or 50) else 0
            graded_status = "graded" if not needs_manual else "submitted"

            conn.execute(
                """UPDATE exam_portal_attempts
                   SET status = ?, submitted_at = datetime('now'), auto_submitted = ?,
                       score = ?, percentage = ?, passed = ?,
                       graded_at = CASE WHEN ? = 'graded' THEN datetime('now') ELSE NULL END
                   WHERE id = ?""",
                (graded_status, int(auto), total_score, percentage, passed,
                 graded_status, attempt_id),
            )
            conn.commit()

            result = {
                "attempt_id": attempt_id,
                "score": total_score,
                "total_marks": total_marks,
                "percentage": round(percentage, 1),
                "passed": bool(passed),
                "status": graded_status,
                "needs_manual_grading": needs_manual,
            }
        if graded_status == "graded":
            try:
                from education_system.university_system.modules.services.integration_bus import (
                    publish_exam_event,
                )
                publish_exam_event(
                    attempt["exam_id"], action="graded",
                    module_code=exam["module_code"] if exam else None,
                    exam_title=exam["title"] if exam else None,
                    student_id=attempt["student_id"],
                    score=total_score, total_marks=total_marks,
                    percentage=round(percentage, 1), passed=bool(passed),
                )
            except Exception:
                pass
        return result

    def update_time_remaining(self, attempt_id: int, seconds: int):
        with get_connection() as conn:
            conn.execute(
                "UPDATE exam_portal_attempts SET time_remaining = ? WHERE id = ?",
                (seconds, attempt_id),
            )
            conn.commit()

    # ── Manual Grading ──────────────────────────────────────────────

    def grade_answer(self, answer_id: int, marks_awarded: float,
                     feedback: str = None) -> bool:
        with get_connection() as conn:
            conn.execute(
                """UPDATE exam_portal_answers
                   SET marks_awarded = ?, feedback = ?, is_correct = CASE WHEN ? > 0 THEN 1 ELSE 0 END
                   WHERE id = ?""",
                (marks_awarded, feedback, marks_awarded, answer_id),
            )
            conn.commit()
        return True

    def finalise_grading(self, attempt_id: int, graded_by: str) -> Dict:
        """Recalculate total score after manual grading and mark as graded."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(marks_awarded), 0) FROM exam_portal_answers WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            total_score = row[0]

            attempt = conn.execute(
                "SELECT exam_id FROM exam_portal_attempts WHERE id = ?", (attempt_id,)
            ).fetchone()
            exam = conn.execute(
                "SELECT total_marks, pass_mark FROM exam_portal_exams WHERE id = ?",
                (attempt["exam_id"],),
            ).fetchone()

            total_marks = exam["total_marks"] or 100
            percentage = (total_score / total_marks * 100) if total_marks > 0 else 0
            passed = 1 if percentage >= (exam["pass_mark"] or 50) else 0

            conn.execute(
                """UPDATE exam_portal_attempts
                   SET status = 'graded', score = ?, percentage = ?, passed = ?,
                       graded_at = datetime('now'), graded_by = ?
                   WHERE id = ?""",
                (total_score, percentage, passed, graded_by, attempt_id),
            )
            student_row = conn.execute(
                "SELECT a.student_id, e.title, e.module_code FROM exam_portal_attempts a "
                "JOIN exam_portal_exams e ON e.id = a.exam_id WHERE a.id = ?",
                (attempt_id,),
            ).fetchone()
            conn.commit()

        try:
            from education_system.university_system.modules.services.integration_bus import (
                publish_exam_event,
            )
            if student_row:
                publish_exam_event(
                    attempt["exam_id"], action="graded",
                    module_code=student_row["module_code"],
                    exam_title=student_row["title"],
                    student_id=student_row["student_id"],
                    score=total_score, total_marks=total_marks,
                    percentage=round(percentage, 1), passed=bool(passed),
                )
        except Exception:
            pass
        return {"score": total_score, "percentage": round(percentage, 1), "passed": bool(passed)}

    # ── Results ─────────────────────────────────────────────────────

    def get_attempt(self, attempt_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM exam_portal_attempts WHERE id = ?", (attempt_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_student_attempts(self, student_id: str) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT a.*, e.title as exam_title, e.total_marks
                   FROM exam_portal_attempts a
                   JOIN exam_portal_exams e ON a.exam_id = e.id
                   WHERE a.student_id = ?
                   ORDER BY a.started_at DESC""",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_exam_results(self, exam_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT a.*, e.title as exam_title, e.total_marks, e.pass_mark
                   FROM exam_portal_attempts a
                   JOIN exam_portal_exams e ON a.exam_id = e.id
                   WHERE a.exam_id = ? AND a.status IN ('submitted', 'graded')
                   ORDER BY a.percentage DESC""",
                (exam_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_ungraded_attempts(self, exam_id: int = None) -> List[Dict]:
        query = """SELECT a.*, e.title as exam_title
                   FROM exam_portal_attempts a
                   JOIN exam_portal_exams e ON a.exam_id = e.id
                   WHERE a.status = 'submitted'"""
        params = []
        if exam_id:
            query += " AND a.exam_id = ?"
            params.append(exam_id)
        query += " ORDER BY a.submitted_at"
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]

    # ── Integrity ───────────────────────────────────────────────────

    def log_integrity_event(self, attempt_id: int, event_type: str,
                            event_data: str = None):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO exam_portal_integrity_events (attempt_id, event_type, event_data) VALUES (?, ?, ?)",
                (attempt_id, event_type, event_data),
            )
            conn.execute(
                "UPDATE exam_portal_attempts SET integrity_flags = integrity_flags + 1 WHERE id = ?",
                (attempt_id,),
            )
            conn.commit()

    # ── Analytics ───────────────────────────────────────────────────

    def get_exam_analytics(self, exam_id: int) -> Dict:
        with get_connection() as conn:
            results = conn.execute(
                """SELECT COUNT(*) as total, AVG(percentage) as avg_pct,
                          MIN(percentage) as min_pct, MAX(percentage) as max_pct,
                          SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as pass_count
                   FROM exam_portal_attempts
                   WHERE exam_id = ? AND status = 'graded'""",
                (exam_id,),
            ).fetchone()

            # Question difficulty
            questions = conn.execute(
                """SELECT q.id, q.question_text, q.marks, q.question_type,
                          COUNT(a.id) as total_answers,
                          SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
                          AVG(a.marks_awarded) as avg_marks
                   FROM exam_portal_questions q
                   LEFT JOIN exam_portal_answers a ON q.id = a.question_id
                   WHERE q.exam_id = ?
                   GROUP BY q.id""",
                (exam_id,),
            ).fetchall()

            return {
                "total_attempts": results["total"] or 0,
                "average_score": round(results["avg_pct"] or 0, 1),
                "min_score": round(results["min_pct"] or 0, 1),
                "max_score": round(results["max_pct"] or 0, 1),
                "pass_count": results["pass_count"] or 0,
                "pass_rate": round((results["pass_count"] or 0) / max(results["total"] or 1, 1) * 100, 1),
                "questions": [
                    {
                        "id": q["id"],
                        "text": q["question_text"][:60],
                        "type": q["question_type"],
                        "marks": q["marks"],
                        "total_answers": q["total_answers"],
                        "correct_count": q["correct_count"] or 0,
                        "difficulty_pct": round(
                            (q["correct_count"] or 0) / max(q["total_answers"] or 1, 1) * 100, 1
                        ),
                        "avg_marks": round(q["avg_marks"] or 0, 2),
                    }
                    for q in questions
                ],
            }

    def export_results_csv(self, exam_id: int) -> str:
        """Return exam results as CSV string."""
        results = self.get_exam_results(exam_id)
        lines = ["Student ID,Student Name,Score,Percentage,Passed,Submitted At,Status"]
        for r in results:
            lines.append(
                f"{r['student_id']},{r.get('student_name', '')},{r.get('score', '')}"
                f",{r.get('percentage', '')},{r.get('passed', '')}"
                f",{r.get('submitted_at', '')},{r['status']}"
            )
        return "\n".join(lines)
