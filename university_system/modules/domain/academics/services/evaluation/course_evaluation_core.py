"""
Course Evaluation System Core Service

Evaluation templates, course evaluations, response collection,
results analytics, and instructor performance tracking.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.feature_gui_factory import create_gui_launcher


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
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating template: {e}")
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
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error adding question: {e}")
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
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating evaluation: {e}")
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
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error starting response: {e}")
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
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error recording answer: {e}")
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
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error completing response: {e}")
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
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error calculating results: {e}")
        finally:
            conn.close()


def display_course_evaluation_menu(auth):
    """Display the Course Evaluation System CLI menu"""
    print("\n" + "="*50)
    print("      COURSE EVALUATION SYSTEM")
    print("="*50)
    print("1. Create Evaluation Template")
    print("2. Launch Course Evaluation")
    print("3. Submit Responses")
    print("4. View Results")
    print("5. Instructor Performance Analytics")
    print("6. Export Evaluation Data")
    print("7. Evaluation History")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n📝 Feature available via Evaluation managers")
                print("Use: from university_system.modules.domain.academics.services.evaluation import EvaluationTemplateManager")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")


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
