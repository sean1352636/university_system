"""LMS quiz service with auto-grading."""
import sqlite3
import json
from datetime import datetime


class QuizService:
    def __init__(self, db_path):
        self._db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_quiz(self, lesson_id, title, pass_mark=50, time_limit_mins=None):
        conn = self._conn()
        try:
            cursor = conn.execute("INSERT INTO lms_quizzes (lesson_id, title, pass_mark, time_limit_mins) VALUES (?, ?, ?, ?)",
                                  (lesson_id, title, pass_mark, time_limit_mins))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_question(self, quiz_id, question_text, question_type, correct_answer, marks=1, options=None, order_index=0):
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO lms_questions (quiz_id, question_text, question_type, options_json, correct_answer, marks, order_index) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (quiz_id, question_text, question_type, json.dumps(options) if options else None, correct_answer, marks, order_index))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def list_questions(self, quiz_id):
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM lms_questions WHERE quiz_id = ? ORDER BY order_index", (quiz_id,)).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("options_json"):
                    d["options"] = json.loads(d["options_json"])
                result.append(d)
            return result
        finally:
            conn.close()

    def submit_quiz(self, quiz_id, student_id, answers):
        """Submit and auto-grade. answers = {question_id_str: answer}"""
        conn = self._conn()
        try:
            questions = conn.execute("SELECT * FROM lms_questions WHERE quiz_id = ?", (quiz_id,)).fetchall()
            quiz = conn.execute("SELECT * FROM lms_quizzes WHERE id = ?", (quiz_id,)).fetchone()
            total_marks = sum(q["marks"] for q in questions)
            earned = sum(q["marks"] for q in questions
                         if str(answers.get(str(q["id"]), "")).strip().lower() == str(q["correct_answer"]).strip().lower())
            score = round((earned / total_marks * 100) if total_marks > 0 else 0)
            passed = score >= (quiz["pass_mark"] if quiz else 50)
            conn.execute("INSERT INTO lms_quiz_attempts (quiz_id, student_id, answers_json, score, passed) VALUES (?, ?, ?, ?, ?)",
                         (quiz_id, student_id, json.dumps(answers), score, int(passed)))
            conn.commit()
            return {"score": score, "passed": passed, "earned": earned, "total": total_marks}
        finally:
            conn.close()

    def get_quiz_results(self, quiz_id, student_id=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM lms_quiz_attempts WHERE quiz_id = ?"
            params = [quiz_id]
            if student_id:
                sql += " AND student_id = ?"
                params.append(student_id)
            return [dict(r) for r in conn.execute(sql + " ORDER BY attempted_at DESC", params).fetchall()]
        finally:
            conn.close()

    def get_quiz_stats(self, quiz_id):
        """Aggregate statistics for a quiz: attempts, avg_score, pass_rate."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*) AS attempts,
                          COUNT(DISTINCT student_id) AS unique_students,
                          AVG(score) AS avg_score,
                          SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) AS pass_count
                   FROM lms_quiz_attempts WHERE quiz_id = ?""",
                (quiz_id,)).fetchone()
            attempts = row["attempts"]
            pass_rate = round(row["pass_count"] / attempts * 100, 1) if attempts > 0 else 0.0
            avg_score = round(row["avg_score"], 1) if row["avg_score"] is not None else 0.0
            return {"attempts": attempts, "unique_students": row["unique_students"],
                    "avg_score": avg_score, "pass_rate": pass_rate}
        finally:
            conn.close()
