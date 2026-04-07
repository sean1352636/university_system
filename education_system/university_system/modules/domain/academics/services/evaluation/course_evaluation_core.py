"""
Course Evaluation System Core Service

Evaluation templates, course evaluations, response collection,
results analytics, instructor performance tracking, and
anonymised end-of-module student feedback (v8.2.0).
"""

from __future__ import annotations

import hashlib
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.exceptions import DatabaseError, ValidationError
from education_system.university_system.modules.shared.feature_gui_factory import create_gui_launcher
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

class EvaluationTemplateManager:
    """Manages evaluation templates"""

    @staticmethod
    def create_template(template_name: str, template_type: str,
                       description: str = "", created_by: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO evaluation_templates (
                    template_name, template_type, description, created_by
                ) VALUES (?, ?, ?, ?)
            ''', (template_name, template_type, description, created_by))
            template_id = cursor.lastrowid
            conn.commit()
            return template_id
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error creating template: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def add_question(template_id: int, question_text: str,
                    question_type: str, question_category: str,
                    scale_min: int = 1, scale_max: int = 5,
                    display_order: int = 0) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO evaluation_questions (
                    template_id, question_text, question_type,
                    question_category, scale_min, scale_max, display_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (template_id, question_text, question_type, question_category,
                  scale_min, scale_max, display_order))
            question_id = cursor.lastrowid
            conn.commit()
            return question_id
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error adding question: {e}") from e
        finally:
            conn.close()

class CourseEvaluationManager:
    """Manages course evaluations"""

    @staticmethod
    def create_evaluation(module_code: str, academic_year: str, semester: str,
                         instructor_id: str, template_id: int,
                         start_date: str, end_date: str) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO course_evaluations (
                    module_code, academic_year, semester, instructor_id,
                    template_id, start_date, end_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (module_code, academic_year, semester, instructor_id,
                  template_id, start_date, end_date))
            evaluation_id = cursor.lastrowid
            conn.commit()
            return evaluation_id
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error creating evaluation: {e}") from e
        finally:
            conn.close()

class ResponseManager:
    """Manages evaluation responses"""

    @staticmethod
    def start_response(evaluation_id: int, student_id: str = None) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO evaluation_responses (evaluation_id, student_id)
                VALUES (?, ?)
            ''', (evaluation_id, student_id))
            response_id = cursor.lastrowid
            conn.commit()
            return response_id
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error starting response: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def record_answer(response_id: int, question_id: int,
                     answer_value: str, numeric_value: float = None) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO evaluation_answers (
                    response_id, question_id, answer_value, numeric_value
                ) VALUES (?, ?, ?, ?)
            ''', (response_id, question_id, answer_value, numeric_value))
            answer_id = cursor.lastrowid
            conn.commit()
            return answer_id
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error recording answer: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def complete_response(response_id: int, time_taken_minutes: int) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE evaluation_responses
                SET is_complete = 1, time_taken_minutes = ?
                WHERE response_id = ?
            ''', (time_taken_minutes, response_id))

            # Update evaluation response count
            cursor.execute('''
                UPDATE course_evaluations
                SET response_count = response_count + 1
                WHERE evaluation_id = (
                    SELECT evaluation_id FROM evaluation_responses WHERE response_id = ?
                )
            ''', (response_id,))

            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error completing response: {e}") from e
        finally:
            conn.close()

class ResultsAnalyticsManager:
    """Manages evaluation results and analytics"""

    @staticmethod
    def calculate_results(evaluation_id: int) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT
                    q.question_id,
                    q.question_text,
                    AVG(a.numeric_value) as average_score,
                    COUNT(a.answer_id) as response_count
                FROM evaluation_questions q
                LEFT JOIN evaluation_answers a ON q.question_id = a.question_id
                LEFT JOIN evaluation_responses r ON a.response_id = r.response_id
                WHERE r.evaluation_id = ? AND r.is_complete = 1
                GROUP BY q.question_id
            ''', (evaluation_id,))

            results = []
            for row in cursor.fetchall():
                # Store results
                cursor.execute('''
                    INSERT OR REPLACE INTO evaluation_results (
                        evaluation_id, question_id, average_score, response_count
                    ) VALUES (?, ?, ?, ?)
                ''', (evaluation_id, row['question_id'],
                      row['average_score'], row['response_count']))
                results.append(dict(row))

            conn.commit()
            return results
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error calculating results: {e}") from e
        finally:
            conn.close()

class AnonymisedEvaluationService:
    """Anonymised end-of-module student feedback service (v8.2.0).

    Student IDs are hashed with SHA-256 before storage. Results are
    returned as aggregates only — no individual responses are exposed.
    """

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS evaluation_forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT NOT NULL,
                module_name TEXT NOT NULL, academic_year TEXT NOT NULL, semester TEXT,
                status TEXT DEFAULT 'draft', created_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, closes_at TEXT,
                is_anonymous INTEGER DEFAULT 1)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS eval_form_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, form_id INTEGER NOT NULL,
                question_text TEXT NOT NULL, question_type TEXT DEFAULT 'rating',
                options TEXT, display_order INTEGER DEFAULT 0,
                is_required INTEGER DEFAULT 1,
                FOREIGN KEY (form_id) REFERENCES evaluation_forms(id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS eval_form_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT, form_id INTEGER NOT NULL,
                student_hash TEXT NOT NULL, submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (form_id) REFERENCES evaluation_forms(id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS eval_form_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT, response_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL, rating_value INTEGER, text_value TEXT,
                FOREIGN KEY (response_id) REFERENCES eval_form_responses(id),
                FOREIGN KEY (question_id) REFERENCES eval_form_questions(id))""")
            conn.commit()

    @staticmethod
    def _hash_student(student_id: str, form_id: int) -> str:
        return hashlib.sha256(f"{student_id}:{form_id}:salt_eval".encode()).hexdigest()[:32]

    def create_form(self, module_code, module_name, academic_year, semester=None, created_by=None):
        with transaction() as conn:
            cur = conn.execute("INSERT INTO evaluation_forms (module_code,module_name,academic_year,semester,created_by) VALUES (?,?,?,?,?)",
                               (module_code, module_name, academic_year, semester, created_by))
            conn.commit()
            return cur.lastrowid

    def get_form(self, form_id):
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM evaluation_forms WHERE id=?", (form_id,)).fetchone()
            return dict(row) if row else None

    def list_forms(self, status=None):
        with get_connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM evaluation_forms WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM evaluation_forms ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def activate_form(self, form_id):
        with transaction() as conn:
            conn.execute("UPDATE evaluation_forms SET status='active' WHERE id=?", (form_id,)); conn.commit()

    def close_form(self, form_id):
        with transaction() as conn:
            conn.execute("UPDATE evaluation_forms SET status='closed',closes_at=? WHERE id=?", (datetime.now().isoformat(), form_id)); conn.commit()

    def add_question(self, form_id, question_text, question_type='rating', options=None, display_order=0, is_required=1):
        with transaction() as conn:
            cur = conn.execute("INSERT INTO eval_form_questions (form_id,question_text,question_type,options,display_order,is_required) VALUES (?,?,?,?,?,?)",
                               (form_id, question_text, question_type, options, display_order, is_required))
            conn.commit()
            return cur.lastrowid

    def get_questions(self, form_id):
        with get_connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM eval_form_questions WHERE form_id=? ORDER BY display_order", (form_id,)).fetchall()]

    def submit_response(self, form_id, student_id, answers):
        """Submit response. Student ID is hashed for anonymity."""
        h = self._hash_student(student_id, form_id)
        with transaction() as conn:
            if conn.execute("SELECT id FROM eval_form_responses WHERE form_id=? AND student_hash=?", (form_id, h)).fetchone():
                raise ValueError("You have already submitted a response for this evaluation.")
            cur = conn.execute("INSERT INTO eval_form_responses (form_id,student_hash) VALUES (?,?)", (form_id, h))
            rid = cur.lastrowid
            for a in answers:
                conn.execute("INSERT INTO eval_form_answers (response_id,question_id,rating_value,text_value) VALUES (?,?,?,?)",
                             (rid, a['question_id'], a.get('rating_value'), a.get('text_value')))
            conn.commit()
            return rid

    def get_anonymised_results(self, form_id):
        """Aggregated results only — no individual responses."""
        with get_connection() as conn:
            questions = self.get_questions(form_id)
            results = {"form_id": form_id, "questions": []}
            for q in questions:
                qr = {"question_id": q['id'], "question_text": q['question_text'], "question_type": q['question_type']}
                if q['question_type'] == 'rating':
                    row = conn.execute("SELECT AVG(rating_value),COUNT(*),MIN(rating_value),MAX(rating_value) FROM eval_form_answers WHERE question_id=? AND rating_value IS NOT NULL", (q['id'],)).fetchone()
                    qr['avg_rating'] = round(row[0], 2) if row[0] else 0
                    qr['response_count'] = row[1]
                    dist = {}
                    for r in conn.execute("SELECT rating_value,COUNT(*) FROM eval_form_answers WHERE question_id=? AND rating_value IS NOT NULL GROUP BY rating_value", (q['id'],)).fetchall():
                        dist[r[0]] = r[1]
                    qr['distribution'] = dist
                elif q['question_type'] == 'text':
                    texts = conn.execute("SELECT text_value FROM eval_form_answers WHERE question_id=? AND text_value IS NOT NULL AND text_value!=''", (q['id'],)).fetchall()
                    qr['response_count'] = len(texts)
                    qr['responses'] = [t[0] for t in texts]
                results['questions'].append(qr)
            results['total_responses'] = conn.execute("SELECT COUNT(*) FROM eval_form_responses WHERE form_id=?", (form_id,)).fetchone()[0]
            return results

    def get_response_rate(self, form_id):
        with get_connection() as conn:
            return {"form_id": form_id, "responses": conn.execute("SELECT COUNT(*) FROM eval_form_responses WHERE form_id=?", (form_id,)).fetchone()[0]}


def display_course_evaluation_menu(auth):
    """Course Evaluation System CLI — fully functional with anonymised feedback."""
    service = AnonymisedEvaluationService()

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("COURSE EVALUATION SYSTEM".center(70))
        print("=" * 70)
        print("\n  1. List Evaluation Forms")
        print("  2. Create Evaluation Form")
        print("  3. Add Question to Form")
        print("  4. Activate Form")
        print("  5. Close Form")
        print("  6. Submit Response (Anonymised)")
        print("  7. View Anonymised Results")
        print("  8. Response Rates")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == '0':
            break
        elif choice == '1':
            forms = service.list_forms()
            print(f"\n{'ID':<5} {'Module':<12} {'Name':<25} {'Year':<10} {'Status':<10}")
            print("-" * 65)
            for f in forms:
                print(f"{f['id']:<5} {f['module_code']:<12} {f['module_name']:<25} {f['academic_year']:<10} {f['status']:<10}")
        elif choice == '2':
            code = input("Module code: ").strip()
            name = input("Module name: ").strip()
            year = input("Academic year: ").strip()
            sem = input("Semester: ").strip()
            fid = service.create_form(code, name, year, sem)
            print(f"\nForm created with ID: {fid}")
        elif choice == '3':
            fid = int(input("Form ID: ").strip())
            text = input("Question text: ").strip()
            qtype = input("Type (rating/text/multiple_choice) [rating]: ").strip() or 'rating'
            order = int(input("Display order [0]: ").strip() or '0')
            service.add_question(fid, text, qtype, display_order=order)
            print("Question added.")
        elif choice == '4':
            fid = int(input("Form ID to activate: ").strip())
            service.activate_form(fid)
            print("Form activated.")
        elif choice == '5':
            fid = int(input("Form ID to close: ").strip())
            service.close_form(fid)
            print("Form closed.")
        elif choice == '6':
            fid = int(input("Form ID: ").strip())
            student_id = auth.current_user.get('username', 'unknown') if auth and auth.current_user else input("Student ID: ").strip()
            questions = service.get_questions(fid)
            answers = []
            for q in questions:
                print(f"\n  {q['question_text']} ({q['question_type']})")
                if q['question_type'] == 'rating':
                    val = int(input("  Rating (1-5): ").strip())
                    answers.append({"question_id": q['id'], "rating_value": val})
                else:
                    val = input("  Answer: ").strip()
                    answers.append({"question_id": q['id'], "text_value": val})
            try:
                service.submit_response(fid, student_id, answers)
                print("\nResponse submitted (anonymised).")
            except ValueError as e:
                print(f"\n{e}")
        elif choice == '7':
            fid = int(input("Form ID: ").strip())
            results = service.get_anonymised_results(fid)
            print(f"\nTotal responses: {results['total_responses']}")
            for q in results['questions']:
                print(f"\n  Q: {q['question_text']}")
                if q['question_type'] == 'rating':
                    print(f"    Avg: {q.get('avg_rating', 0)} | Responses: {q.get('response_count', 0)}")
                elif q['question_type'] == 'text':
                    print(f"    {q.get('response_count', 0)} text responses")
        elif choice == '8':
            forms = service.list_forms()
            for f in forms:
                rate = service.get_response_rate(f['id'])
                print(f"  {f['module_code']} ({f['status']}): {rate['responses']} responses")
        input("\nPress Enter to continue...")

# Import the full GUI
try:
    from education_system.university_system.modules.domain.academics.gui.course_management_gui.course_evaluation_gui import (
        launch_course_evaluation_gui
    )
except ImportError:
    # Fallback to factory launcher if GUI not available
    launch_course_evaluation_gui = create_gui_launcher(
        title="Course Evaluation System",
        description="""Comprehensive course and instructor evaluation system.

Features:
• Evaluation templates
• Course evaluations
• Response collection
• Results analytics
• Instructor performance
• Evaluation history""",
        cli_instruction="Use CLI: Course Evaluation System"
    )

__all__ = [
    'EvaluationTemplateManager', 'CourseEvaluationManager',
    'ResponseManager', 'ResultsAnalyticsManager',
    'AnonymisedEvaluationService',
    'display_course_evaluation_menu',
    'launch_course_evaluation_gui',
]
