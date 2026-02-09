"""
Course Evaluation System Core Service

Evaluation templates, course evaluations, response collection,
results analytics, and instructor performance tracking.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from university_system.infrastructure.database.db import get_connection
from university_system.infrastructure.exceptions import DatabaseError, ValidationError
from university_system.modules.shared.feature_gui_factory import create_gui_launcher
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
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


def display_course_evaluation_menu(auth):
    """Display the Course Evaluation System CLI menu"""
    print("\n" + "="*50)
    print(f"      {get_text('evaluation.title', default='COURSE EVALUATION SYSTEM')}")
    print("="*50)
    print(f"1. {get_text('evaluation.menu.create_template', default='Create Evaluation Template')}")
    print(f"2. {get_text('evaluation.menu.launch_evaluation', default='Launch Course Evaluation')}")
    print(f"3. {get_text('evaluation.menu.submit_responses', default='Submit Responses')}")
    print(f"4. {get_text('evaluation.menu.view_results', default='View Results')}")
    print(f"5. {get_text('evaluation.menu.instructor_analytics', default='Instructor Performance Analytics')}")
    print(f"6. {get_text('evaluation.menu.export_data', default='Export Evaluation Data')}")
    print(f"7. {get_text('evaluation.menu.history', default='Evaluation History')}")
    print(f"8. {get_text('evaluation.menu.language', default='Language')}")
    print(f"9. {get_text('evaluation.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{get_text('evaluation.prompt.choice', default='Enter your choice (1-9)')}: ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n{get_text('evaluation.feature_available', default='Feature available via Evaluation managers')}")
                print("Use: from university_system.modules.domain.academics.services.evaluation import EvaluationTemplateManager")
            elif choice == '8':
                display_language_menu_option()
            elif choice == '9':
                print(get_text('evaluation.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('evaluation.invalid_choice', default='Invalid choice.'))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(get_text('evaluation.error', default='Error: {error}').format(error=e))


# Import the full GUI
try:
    from university_system.modules.domain.academics.gui.course_evaluation_gui import (
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
    'display_course_evaluation_menu',
    'launch_course_evaluation_gui',
]
