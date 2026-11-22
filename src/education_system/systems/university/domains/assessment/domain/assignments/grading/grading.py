from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
from education_system.systems.university.domains.assessment.domain.assignments.core.constants import SUBDIR_EXPORTS
from datetime import datetime
import csv
import os


class GradingMixin:
    """Mixin providing grading, rubric management, and grade export."""

    def _qa(self):
        from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import (
            AssessmentQAService,
        )
        return AssessmentQAService(self.db_path)

    def _apply_qa(self, submission_id, percentage, feedback=None, marker=None):
        """Run a saved mark through the QA rules and say what happened to it."""
        try:
            result = self._qa().record_mark(submission_id, percentage, marker=marker,
                                            feedback=feedback)
        except Exception as e:
            print(f"Warning: assessment QA rules not applied: {e}")
            return {"grade": percentage, "released": True}
        if result.get("word_penalty_pct"):
            print(f"  Word limit exceeded: {result['word_penalty_pct']:g} points deducted.")
        if result.get("capped"):
            print("  Referral attempt: mark capped at the pass mark.")
        print(f"  Recorded mark: {result['grade']:.1f}%"
              + ("" if result["released"] else " (held until grades are released)"))
        return result

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
            try:
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
            finally:
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

            try:
                labels = self._qa().marker_labels([(r[0], f"{r[2]} {r[3]}") for r in submissions])
            except Exception:
                labels = {}

            print("\nUngraded Submissions:")
            print("=" * 100)
            print(f"{'ID':<5} {'Student':<25} {'Assignment':<30} {'Submitted':<20}")
            print("-" * 100)

            for sub in submissions:
                sid, student_id, fname, lname, title, date = sub
                student_name = labels.get(sid, f"{fname} {lname}")[:23]
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

            print(f"\nGrading submission for: {labels.get(submission_id, f'{submission[-2]} {submission[-1]}')}")
            print(f"Assignment: {submission[-5]}")
            print(f"File: {submission[6]}")
            print(f"Max marks: {submission[-4]}")

            # Check if assignment has a rubric
            # Read from the end: s.* is wider than this code once assumed.
            rubric_id = submission[-3]
            if rubric_id:
                marked = self._grade_with_rubric(cursor, submission_id, rubric_id)
            else:
                marked = self._grade_simple(cursor, submission_id, submission[-4] or 100)

            conn.commit()
            conn.close()

            if marked:
                self._apply_qa(submission_id, marked[0], marked[1], self.auth.current_user['id'])

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
        return final_percentage, overall_feedback

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
        return percentage, feedback

    def submit_grade(self, submission_id, grade, feedback=''):
        """Submit a grade for a submission"""
        try:
            if not self._check_permission('grade_submissions'):
                print("Permission denied")
                return False

            grader_id = self._get_student_id()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            conn = sqlite3.connect(self.db_path)
            try:
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

            finally:
                conn.close()

            qa = self._apply_qa(submission_id, float(grade), feedback)
            if qa["released"]:
                self._send_notification(student_id, "Grade Released", f"Your submission has been graded: {qa['grade']}", "grade_released")

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
        """Release one student's grade early.

        Anonymously marked, moderated or date-released assignments are
        released for the whole cohort from the Assessment QA menu instead.
        """
        try:
            from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import (
                AssessmentQAError,
            )
            try:
                self._qa().release_submission(submission_id)
            except AssessmentQAError as e:
                print(f"Not released: {e}")
                return False

            conn = sqlite3.connect(self.db_path)
            try:
                result = conn.execute('SELECT student_id, grade FROM assignment_submissions WHERE id = ?',
                                      (submission_id,)).fetchone()
            finally:
                conn.close()
            if result:
                student_id, grade = result
                self._send_notification(student_id, "Grade Released", f"Your grade has been released: {grade}", "grade_released")

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
                self._send_notification(student_id, "Grade Available", message, "grade_notification")
                return True

            return False

        except Exception as e:
            print(f"Error sending grade notification: {e}")
            return False

    def export_grades(self, assignment_id, export_path=None):
        """Export grades to CSV"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, SUBDIR_EXPORTS, f'grades_{assignment_id}.csv')

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT
                        student_id, grade, feedback, graded_at, graded_by
                    FROM assignment_submissions
                    WHERE assignment_id = ? AND status = 'graded'
                    ORDER BY student_id
                ''', (assignment_id,))

                grades = cursor.fetchall()
            finally:
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

    def grade_with_rubrics(self):
        """Mark a submission criterion by criterion against its assignment's rubric."""
        if not self._check_permission('manage_assignments'):
            return
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute('''
                SELECT s.id, s.student_id, st.first_name, st.last_name, a.title, a.module_code,
                       a.rubric_id, r.name AS rubric_name, s.submission_date, s.word_count
                FROM assignment_submissions s
                JOIN assignments a ON a.id = s.assignment_id
                JOIN rubrics r ON r.id = a.rubric_id
                LEFT JOIN students st ON st.student_id = s.student_id
                WHERE s.grade IS NULL AND COALESCE(s.is_final_submission, 1) = 1
                ORDER BY s.submission_date
            ''').fetchall()
        finally:
            conn.close()
        if not rows:
            print("No unmarked submissions on assignments that have a rubric.")
            print("Attach a rubric to an assignment from 'Manage Rubrics'.")
            return
        try:
            labels = self._qa().marker_labels(
                [(r['id'], f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or r['student_id'])
                 for r in rows])
        except Exception:
            labels = {}
        print(f"\n{'ID':<5} {'Student':<24} {'Assignment':<30} {'Rubric':<20} {'Submitted':<16}")
        print("-" * 98)
        for r in rows:
            name = labels.get(r['id']) or r['student_id']
            print(f"{r['id']:<5} {name[:23]:<24} {str(r['title'])[:29]:<30} "
                  f"{str(r['rubric_name'])[:19]:<20} {str(r['submission_date'] or '')[:16]:<16}")
        choice = input("\nSubmission ID to mark: ").strip()
        chosen = next((r for r in rows if choice.isdigit() and r['id'] == int(choice)), None)
        if chosen is None:
            print("Invalid submission ID.")
            return
        print(f"\nMarking: {labels.get(chosen['id']) or chosen['student_id']} — {chosen['title']}")
        if chosen['word_count'] is not None:
            print(f"Word count: {chosen['word_count']}")

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            marked = self._grade_with_rubric(cursor, chosen['id'], chosen['rubric_id'])
            conn.commit()
        except ZeroDivisionError:
            conn.rollback()
            print("This rubric has no criteria with marks; add criteria in 'Manage Rubrics'.")
            return
        finally:
            conn.close()
        if marked:
            self._apply_qa(chosen['id'], marked[0], marked[1], self.auth.current_user['id'])

    def manage_rubrics(self):
        """List rubrics; view, extend, rename, attach to an assignment or delete them."""
        if not self._check_permission('manage_assignments'):
            return
        while True:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                rubrics = conn.execute('''
                    SELECT r.id, r.name, r.description, r.total_points,
                           (SELECT COUNT(*) FROM rubric_criteria c WHERE c.rubric_id = r.id) AS criteria,
                           (SELECT COUNT(*) FROM assignments a WHERE a.rubric_id = r.id) AS used_by
                    FROM rubrics r ORDER BY r.id
                ''').fetchall()
            finally:
                conn.close()
            if not rubrics:
                print("\nNo rubrics yet. Create one with 'Create Rubric'.")
                return
            print(f"\n{'ID':<5} {'Name':<32} {'Criteria':>8} {'Points':>7} {'Used by':>8}")
            print("-" * 64)
            for r in rubrics:
                print(f"{r['id']:<5} {str(r['name'])[:31]:<32} {r['criteria']:>8} "
                      f"{(r['total_points'] or 0):>7g} {r['used_by']:>8}")
            choice = input("\nRubric ID to manage (Enter to go back): ").strip()
            if not choice.isdigit() or int(choice) not in {r['id'] for r in rubrics}:
                return
            self._manage_one_rubric(int(choice))

    def _manage_one_rubric(self, rubric_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rubric = conn.execute("SELECT * FROM rubrics WHERE id = ?", (rubric_id,)).fetchone()
            criteria = conn.execute(
                "SELECT id, criteria_name, criteria_description, max_points, weight "
                "FROM rubric_criteria WHERE rubric_id = ? ORDER BY COALESCE(order_index, 0), id",
                (rubric_id,)).fetchall()
        finally:
            conn.close()
        print(f"\nRubric {rubric_id}: {rubric['name']}")
        if rubric['description']:
            print(f"  {rubric['description']}")
        for c in criteria:
            print(f"  [{c['id']}] {c['criteria_name']} — max {c['max_points']:g}, weight {c['weight'] or 1:g}")
            if c['criteria_description']:
                print(f"       {c['criteria_description']}")
        if not criteria:
            print("  (no criteria)")
        print("\n1. Add criterion  2. Remove criterion  3. Rename / describe  "
              "4. Attach to an assignment  5. Delete rubric  0. Back")
        action = input("Choice: ").strip()
        if action == '1':
            name = input("Criterion name: ").strip()
            if not name:
                return
            desc = input("Description: ").strip()
            try:
                points = float(input("Maximum points: ").strip())
            except ValueError:
                print("Maximum points must be a number.")
                return
            if points <= 0:
                print("Maximum points must be positive.")
                return
            self.add_rubric_criterion(rubric_id, name, desc, points)
        elif action == '2':
            cid = input("Criterion ID to remove: ").strip()
            if cid.isdigit() and int(cid) in {c['id'] for c in criteria}:
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.execute("DELETE FROM rubric_criteria WHERE id = ?", (int(cid),))
                    self._sync_rubric_total(conn, rubric_id)
                    conn.commit()
                finally:
                    conn.close()
                self._log_action('delete', 'rubric_criteria', int(cid))
                print("Criterion removed.")
            else:
                print("Invalid criterion ID.")
        elif action == '3':
            name = input(f"Name [{rubric['name']}]: ").strip()
            desc = input(f"Description [{rubric['description'] or ''}]: ").strip()
            fields = {k: v for k, v in (('name', name), ('description', desc)) if v}
            if fields:
                self.edit_rubric(rubric_id, **fields)
        elif action == '4':
            aid = input("Assignment ID to use this rubric: ").strip()
            if not aid.isdigit():
                print("Invalid assignment ID.")
                return
            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.execute("UPDATE assignments SET rubric_id = ?, updated_at = ? WHERE id = ?",
                                   (rubric_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), int(aid)))
                conn.commit()
            finally:
                conn.close()
            print("Rubric attached." if cur.rowcount else "No assignment with that ID.")
        elif action == '5':
            if input(f"Delete rubric '{rubric['name']}'? Assignments using it will have no rubric. (y/n): "
                     ).strip().lower() == 'y':
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.execute("UPDATE assignments SET rubric_id = NULL WHERE rubric_id = ?", (rubric_id,))
                    conn.commit()
                finally:
                    conn.close()
                self.delete_rubric(rubric_id)

    @staticmethod
    def _sync_rubric_total(conn, rubric_id):
        conn.execute("UPDATE rubrics SET total_points = COALESCE("
                     "(SELECT SUM(max_points) FROM rubric_criteria WHERE rubric_id = ?), 0) WHERE id = ?",
                     (rubric_id, rubric_id))

    def edit_rubric(self, rubric_id, **kwargs):
        """Edit an existing rubric"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            update_fields = []
            values = []
            for key, value in kwargs.items():
                # 'rubric_name' was the old spelling; the column is 'name'.
                if key == 'rubric_name':
                    key = 'name'
                if key in ['name', 'description', 'total_points']:
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

            # order_index is the column every rubric_criteria definition has.
            cursor.execute('SELECT * FROM rubric_criteria WHERE rubric_id = ? ORDER BY COALESCE(order_index, 0), id', (rubric_id,))
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

            # Same columns create_rubric writes: criteria_name / criteria_description /
            # order_index exist on every definition of this table.
            cursor.execute('SELECT MAX(order_index) FROM rubric_criteria WHERE rubric_id = ?', (rubric_id,))
            result = cursor.fetchone()
            next_order = (result[0] if result[0] is not None else -1) + 1

            cursor.execute('''
                INSERT INTO rubric_criteria (rubric_id, criteria_name, criteria_description, max_points, weight, order_index)
                VALUES (?, ?, ?, ?, 1.0, ?)
            ''', (rubric_id, criterion_name, description, max_points, next_order))
            self._sync_rubric_total(conn, rubric_id)

            conn.commit()
            self._log_action('create', 'rubric_criteria', cursor.lastrowid)
            conn.close()

            print("Rubric criterion added successfully!")
            return True

        except Exception as e:
            print(f"Error adding rubric criterion: {e}")
            return False
