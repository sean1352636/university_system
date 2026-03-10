from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.sql_safety import validate_identifier
from datetime import datetime
import csv
import os


class GradingMixin:
    """Mixin providing grading, rubric management, and grade export."""

    def create_rubric(self):
        """Create a new grading rubric"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nCreate New Rubric")
            print("=" * 50)

            name = input("Rubric name: ").strip()
            if not name:
                print("Name cannot be empty.")
                return

            description = input("Description: ").strip()

            criteria = []
            total_points = 0

            print("\nAdd criteria (type 'done' when finished):")
            while True:
                criteria_name = input("Criteria name (or 'done'): ").strip()
                if criteria_name.lower() == 'done':
                    break

                criteria_desc = input("Criteria description: ").strip()

                while True:
                    try:
                        points = float(input("Maximum points: "))
                        if points <= 0:
                            print("Points must be positive.")
                            continue
                        break
                    except ValueError:
                        print("Please enter a valid number.")

                weight = 1.0
                weight_input = input("Weight (default 1.0): ").strip()
                if weight_input:
                    try:
                        weight = float(weight_input)
                    except ValueError:
                        weight = 1.0

                criteria.append({
                    'name': criteria_name,
                    'description': criteria_desc,
                    'points': points,
                    'weight': weight
                })

                total_points += points
                print(f"Added criteria. Current total: {total_points} points")

            if not criteria:
                print("No criteria added.")
                return

            # Save to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO rubrics (name, description, total_points, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (name, description, total_points, self.auth.current_user['id'], timestamp))

            rubric_id = cursor.lastrowid

            # Add criteria
            for i, criterion in enumerate(criteria):
                cursor.execute('''
                INSERT INTO rubric_criteria (rubric_id, criteria_name, criteria_description, max_points, weight, order_index)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (rubric_id, criterion['name'], criterion['description'],
                      criterion['points'], criterion['weight'], i))

            conn.commit()
            conn.close()

            print(f"\nRubric '{name}' created successfully!")
            print(f"Total points: {total_points}")

        except Exception as e:
            print(f"Error creating rubric: {e}")

    def grade_submission(self):
        """Grade a student submission"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            # Show ungraded submissions
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.id, s.student_id, st.first_name, st.last_name, a.title, s.submission_date
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.grade IS NULL AND s.status = 'submitted'
            ORDER BY s.submission_date
            ''')

            submissions = cursor.fetchall()

            if not submissions:
                print("No ungraded submissions found.")
                conn.close()
                return

            print("\nUngraded Submissions:")
            print("=" * 100)
            print(f"{'ID':<5} {'Student':<25} {'Assignment':<30} {'Submitted':<20}")
            print("-" * 100)

            for sub in submissions:
                sid, student_id, fname, lname, title, date = sub
                student_name = f"{fname} {lname}"[:23]
                assignment_title = title[:28]
                print(f"{sid:<5} {student_name:<25} {assignment_title:<30} {date:<20}")

            submission_id = input("\nEnter submission ID to grade: ").strip()
            if not submission_id.isdigit():
                print("Invalid submission ID.")
                conn.close()
                return

            submission_id = int(submission_id)

            # Get submission details
            cursor.execute('''
            SELECT s.*, a.title, a.max_marks, a.rubric_id, st.first_name, st.last_name
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.id = ?
            ''', (submission_id,))

            submission = cursor.fetchone()
            if not submission:
                print("Submission not found.")
                conn.close()
                return

            print(f"\nGrading submission for: {submission[14]} {submission[15]}")
            print(f"Assignment: {submission[11]}")
            print(f"File: {submission[6]}")
            print(f"Max marks: {submission[12]}")

            # Check if assignment has a rubric
            rubric_id = submission[13]
            if rubric_id:
                self._grade_with_rubric(cursor, submission_id, rubric_id)
            else:
                self._grade_simple(cursor, submission_id, submission[12])

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Error grading submission: {e}")

    def _grade_with_rubric(self, cursor, submission_id, rubric_id):
        """Grade using a rubric"""
        cursor.execute('''
        SELECT id, criteria_name, criteria_description, max_points
        FROM rubric_criteria
        WHERE rubric_id = ?
        ORDER BY order_index
        ''', (rubric_id,))

        criteria = cursor.fetchall()
        total_earned = 0
        total_possible = 0

        print("\nGrading with rubric:")
        for criterion in criteria:
            crit_id, name, desc, max_points = criterion
            print(f"\n{name} (Max: {max_points} points)")
            if desc:
                print(f"Description: {desc}")

            while True:
                try:
                    points = float(input(f"Points earned (0-{max_points}): "))
                    if 0 <= points <= max_points:
                        break
                    else:
                        print(f"Points must be between 0 and {max_points}")
                except ValueError:
                    print("Please enter a valid number.")

            feedback = input("Feedback for this criterion (optional): ").strip()

            cursor.execute('''
            INSERT INTO grades (submission_id, rubric_criteria_id, points_earned, max_points,
                              percentage, feedback, graded_by, graded_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (submission_id, crit_id, points, max_points,
                  (points/max_points)*100, feedback,
                  self.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            total_earned += points
            total_possible += max_points

        final_percentage = (total_earned / total_possible) * 100
        overall_feedback = input("\nOverall feedback: ").strip()

        cursor.execute('''
        UPDATE assignment_submissions
        SET grade = ?, graded_by = ?, graded_date = ?, feedback = ?
        WHERE id = ?
        ''', (final_percentage, self.auth.current_user['id'],
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), overall_feedback, submission_id))

        print(f"\nGrade saved: {final_percentage:.1f}% ({total_earned}/{total_possible} points)")

    def _grade_simple(self, cursor, submission_id, max_marks):
        """Simple grading without rubric"""
        while True:
            try:
                grade = float(input(f"Grade (0-{max_marks}): "))
                if 0 <= grade <= max_marks:
                    break
                else:
                    print(f"Grade must be between 0 and {max_marks}")
            except ValueError:
                print("Please enter a valid number.")

        feedback = input("Feedback: ").strip()

        percentage = (grade / max_marks) * 100

        cursor.execute('''
        UPDATE assignment_submissions
        SET grade = ?, graded_by = ?, graded_date = ?, feedback = ?
        WHERE id = ?
        ''', (percentage, self.auth.current_user['id'],
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), feedback, submission_id))

        print(f"\nGrade saved: {percentage:.1f}% ({grade}/{max_marks} points)")

    def submit_grade(self, submission_id, grade, feedback=''):
        """Submit a grade for a submission"""
        try:
            if not self._check_permission('grade_submissions'):
                print("Permission denied")
                return False

            grader_id = self._get_student_id()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE assignment_submissions
                SET grade = ?, feedback = ?, graded_by = ?, graded_at = ?, status = 'graded'
                WHERE id = ?
            ''', (grade, feedback, grader_id, timestamp, submission_id))

            conn.commit()
            self._log_action('update', 'assignment_submissions', submission_id, {'grade': grade})

            cursor.execute('SELECT student_id FROM assignment_submissions WHERE id = ?', (submission_id,))
            student_id = cursor.fetchone()[0]
            self._send_notification(student_id, "Grade Released", f"Your submission has been graded: {grade}", "grade_released", submission_id)

            conn.close()

            print("Grade submitted successfully!")
            return True

        except Exception as e:
            print(f"Error submitting grade: {e}")
            return False

    def get_ungraded_submissions(self, assignment_id=None):
        """Get all ungraded submissions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if assignment_id:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    WHERE assignment_id = ? AND (grade IS NULL OR status != 'graded')
                    ORDER BY submission_date
                ''', (assignment_id,))
            else:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    WHERE grade IS NULL OR status != 'graded'
                    ORDER BY submission_date
                ''')

            submissions = cursor.fetchall()
            conn.close()
            return submissions

        except Exception as e:
            print(f"Error retrieving ungraded submissions: {e}")
            return []

    def get_graded_submissions(self, assignment_id=None):
        """Get all graded submissions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if assignment_id:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    WHERE assignment_id = ? AND status = 'graded'
                    ORDER BY graded_at DESC
                ''', (assignment_id,))
            else:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    WHERE status = 'graded'
                    ORDER BY graded_at DESC
                ''')

            submissions = cursor.fetchall()
            conn.close()
            return submissions

        except Exception as e:
            print(f"Error retrieving graded submissions: {e}")
            return []

    def calculate_grade_percentage(self, grade, max_marks):
        """Calculate grade as percentage"""
        try:
            return (float(grade) / float(max_marks)) * 100
        except (ValueError, TypeError, ZeroDivisionError):
            return 0.0

    def release_grade(self, submission_id):
        """Release a grade to student"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE assignment_submissions
                SET status = 'grade_released'
                WHERE id = ?
            ''', (submission_id,))

            cursor.execute('SELECT student_id, grade FROM assignment_submissions WHERE id = ?', (submission_id,))
            result = cursor.fetchone()

            if result:
                student_id, grade = result
                self._send_notification(student_id, "Grade Released", f"Your grade has been released: {grade}", "grade_released", submission_id)

            conn.commit()
            conn.close()

            print("Grade released successfully!")
            return True

        except Exception as e:
            print(f"Error releasing grade: {e}")
            return False

    def send_grade_notification(self, submission_id):
        """Send grade notification to student"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT student_id, grade, feedback
                FROM assignment_submissions
                WHERE id = ?
            ''', (submission_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                student_id, grade, feedback = result
                message = f"Your grade: {grade}"
                if feedback:
                    message += f"\nFeedback: {feedback}"
                self._send_notification(student_id, "Grade Available", message, "grade_notification", submission_id)
                return True

            return False

        except Exception as e:
            print(f"Error sending grade notification: {e}")
            return False

    def export_grades(self, assignment_id, export_path=None):
        """Export grades to CSV"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, 'exports', f'grades_{assignment_id}.csv')

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    student_id, grade, feedback, graded_at, graded_by
                FROM assignment_submissions
                WHERE assignment_id = ? AND status = 'graded'
                ORDER BY student_id
            ''', (assignment_id,))

            grades = cursor.fetchall()
            conn.close()

            with open(export_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Student ID', 'Grade', 'Feedback', 'Graded At', 'Graded By'])
                writer.writerows(grades)

            print(f"Grades exported to: {export_path}")
            return export_path

        except Exception as e:
            print(f"Error exporting grades: {e}")
            return None

    def edit_rubric(self, rubric_id, **kwargs):
        """Edit an existing rubric"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            update_fields = []
            values = []
            for key, value in kwargs.items():
                if key in ['rubric_name', 'description', 'total_points']:
                    update_fields.append(f"{validate_identifier(key, 'column')} = ?")
                    values.append(value)

            if not update_fields:
                print("No valid fields to update")
                return False

            values.append(rubric_id)
            query = f"UPDATE rubrics SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)

            conn.commit()
            self._log_action('update', 'rubrics', rubric_id, kwargs)
            conn.close()

            print("Rubric updated successfully!")
            return True

        except Exception as e:
            print(f"Error editing rubric: {e}")
            return False

    def delete_rubric(self, rubric_id):
        """Delete a rubric"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM rubric_criteria WHERE rubric_id = ?', (rubric_id,))
            cursor.execute('DELETE FROM rubrics WHERE id = ?', (rubric_id,))

            conn.commit()
            self._log_action('delete', 'rubrics', rubric_id)
            conn.close()

            print("Rubric deleted successfully!")
            return True

        except Exception as e:
            print(f"Error deleting rubric: {e}")
            return False

    def get_rubrics(self, created_by=None):
        """Get all rubrics, optionally filtered by creator"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if created_by:
                cursor.execute('SELECT * FROM rubrics WHERE created_by = ? ORDER BY created_at DESC', (created_by,))
            else:
                cursor.execute('SELECT * FROM rubrics ORDER BY created_at DESC')

            rubrics = cursor.fetchall()
            conn.close()
            return rubrics

        except Exception as e:
            print(f"Error retrieving rubrics: {e}")
            return []

    def get_rubric_criteria(self, rubric_id):
        """Get criteria for a specific rubric"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM rubric_criteria WHERE rubric_id = ? ORDER BY criterion_order', (rubric_id,))
            criteria = cursor.fetchall()
            conn.close()
            return criteria

        except Exception as e:
            print(f"Error retrieving rubric criteria: {e}")
            return []

    def add_rubric_criterion(self, rubric_id, criterion_name, description='', max_points=10):
        """Add a criterion to a rubric"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT MAX(criterion_order) FROM rubric_criteria WHERE rubric_id = ?', (rubric_id,))
            result = cursor.fetchone()
            next_order = (result[0] or 0) + 1

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO rubric_criteria (rubric_id, criterion_name, description, max_points, criterion_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (rubric_id, criterion_name, description, max_points, next_order, timestamp))

            conn.commit()
            self._log_action('create', 'rubric_criteria', cursor.lastrowid)
            conn.close()

            print("Rubric criterion added successfully!")
            return True

        except Exception as e:
            print(f"Error adding rubric criterion: {e}")
            return False
