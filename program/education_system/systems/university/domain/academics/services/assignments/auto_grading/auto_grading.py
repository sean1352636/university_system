from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
import subprocess
import tempfile
import os
import random
import json


class AutoGradingMixin:
    """Mixin providing auto-grading for MCQ, fill-blank, and coding submissions."""

    def auto_grade_submissions(self):
        """Main auto-grading menu: select assignment, auto-grade all eligible submissions."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT a.id, a.title, a.module_code,
                   COUNT(sa.id) as pending_count
            FROM assignments a
            JOIN student_answers sa ON sa.assignment_id = a.id
            WHERE sa.graded = 0
            GROUP BY a.id, a.title, a.module_code
            ORDER BY a.title
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("No assignments with pending auto-gradable submissions found.")
                conn.close()
                return

            print("\nAuto-Grading Menu")
            print("=" * 70)
            print(f"{'#':<5} {'Assignment':<30} {'Module':<15} {'Pending':<10}")
            print("-" * 70)

            for i, (aid, title, module, pending) in enumerate(assignments, 1):
                print(f"{i:<5} {title[:28]:<30} {module:<15} {pending:<10}")

            choice = input("\nSelect assignment number (or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                conn.close()
                return

            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(assignments):
                print("Invalid selection.")
                conn.close()
                return

            selected = assignments[int(choice) - 1]
            assignment_id = selected[0]
            assignment_title = selected[1]

            print(f"\nAuto-grading submissions for: {assignment_title}")
            print("-" * 50)

            # Get pending answers grouped by type
            cursor.execute('''
            SELECT sa.id, sa.question_id, sa.student_answer, q.question_type
            FROM student_answers sa
            JOIN questions q ON sa.question_id = q.id
            WHERE sa.assignment_id = ? AND sa.graded = 0
            ORDER BY q.question_type
            ''', (assignment_id,))

            answers = cursor.fetchall()
            graded_count = 0
            error_count = 0

            for answer_id, question_id, student_answer, q_type in answers:
                try:
                    if q_type == 'mcq':
                        self.auto_grade_mcq(answer_id)
                    elif q_type == 'fill_blank':
                        self.auto_grade_fill_blank(answer_id)
                    elif q_type == 'coding':
                        self.auto_grade_coding(answer_id)
                    else:
                        print(f"  Skipping answer {answer_id}: unknown type '{q_type}'")
                        continue
                    graded_count += 1
                except Exception as e:
                    print(f"  Error grading answer {answer_id}: {e}")
                    error_count += 1

            conn.close()

            print("\nAuto-grading complete!")
            print(f"  Graded: {graded_count}")
            print(f"  Errors: {error_count}")

        except Exception as e:
            print(f"Error in auto-grading: {e}")

    def manage_question_banks(self):
        """List/create/edit/delete question banks."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            while True:
                print("\nQuestion Bank Management")
                print("=" * 50)
                print("1. List question banks")
                print("2. Create question bank")
                print("3. Edit question bank")
                print("4. Delete question bank")
                print("5. Add question to bank")
                print("6. View bank statistics")
                print("7. Back")

                choice = input("\nSelect option: ").strip()

                if choice == '1':
                    self._list_question_banks()
                elif choice == '2':
                    self.create_question_bank()
                elif choice == '3':
                    self._edit_question_bank()
                elif choice == '4':
                    self._delete_question_bank()
                elif choice == '5':
                    self.add_question_to_bank()
                elif choice == '6':
                    self.view_question_bank_stats()
                elif choice == '7':
                    break
                else:
                    print("Invalid option.")

        except Exception as e:
            print(f"Error managing question banks: {e}")

    def _list_question_banks(self):
        """List all question banks."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT qb.id, qb.name, qb.module_code, qb.description,
                   COUNT(q.id) as question_count, qb.created_at
            FROM question_banks qb
            LEFT JOIN questions q ON q.bank_id = qb.id
            GROUP BY qb.id, qb.name, qb.module_code, qb.description, qb.created_at
            ORDER BY qb.name
            ''')

            banks = cursor.fetchall()
            conn.close()

            if not banks:
                print("No question banks found.")
                return

            print(f"\n{'ID':<5} {'Name':<25} {'Module':<12} {'Questions':<10} {'Created':<20}")
            print("-" * 75)
            for bank_id, name, module, desc, count, created in banks:
                print(f"{bank_id:<5} {name[:23]:<25} {module:<12} {count:<10} {created:<20}")
                if desc:
                    print(f"      Description: {desc[:55]}")

        except Exception as e:
            print(f"Error listing question banks: {e}")

    def create_question_bank(self):
        """Create a new question bank (name, module, description)."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nCreate New Question Bank")
            print("=" * 50)

            name = input("Bank name: ").strip()
            if not name:
                print("Name cannot be empty.")
                return

            module_code = input("Module code: ").strip()
            if not module_code:
                print("Module code cannot be empty.")
                return

            description = input("Description (optional): ").strip()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO question_banks (name, module_code, description, created_by, created_at)
                VALUES (?, ?, ?, ?, ?)
                ''', (name, module_code, description,
                      self.auth.current_user['id'], timestamp))
                conn.commit()
                bank_id = cursor.lastrowid
            finally:
                conn.close()

            print(f"\nQuestion bank '{name}' created successfully! (ID: {bank_id})")

        except Exception as e:
            print(f"Error creating question bank: {e}")

    def _edit_question_bank(self):
        """Edit an existing question bank."""
        try:
            bank_id = input("Enter question bank ID to edit: ").strip()
            if not bank_id.isdigit():
                print("Invalid bank ID.")
                return

            bank_id = int(bank_id)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT name, module_code, description FROM question_banks WHERE id = ?',
                           (bank_id,))
            bank = cursor.fetchone()

            if not bank:
                print("Question bank not found.")
                conn.close()
                return

            current_name, current_module, current_desc = bank
            print(f"\nEditing bank: {current_name}")
            print(f"Current module: {current_module}")
            print(f"Current description: {current_desc or '(none)'}")

            new_name = input(f"New name (Enter to keep '{current_name}'): ").strip()
            new_module = input(f"New module (Enter to keep '{current_module}'): ").strip()
            new_desc = input("New description (Enter to keep current): ").strip()

            cursor.execute('''
            UPDATE question_banks
            SET name = ?, module_code = ?, description = ?
            WHERE id = ?
            ''', (new_name or current_name,
                  new_module or current_module,
                  new_desc if new_desc else current_desc,
                  bank_id))

            conn.commit()
            conn.close()

            print("Question bank updated successfully!")

        except Exception as e:
            print(f"Error editing question bank: {e}")

    def _delete_question_bank(self):
        """Delete a question bank and its questions."""
        try:
            bank_id = input("Enter question bank ID to delete: ").strip()
            if not bank_id.isdigit():
                print("Invalid bank ID.")
                return

            bank_id = int(bank_id)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT name FROM question_banks WHERE id = ?', (bank_id,))
            bank = cursor.fetchone()

            if not bank:
                print("Question bank not found.")
                conn.close()
                return

            confirm = input(f"Delete bank '{bank[0]}' and all its questions? (yes/no): ").strip()
            if confirm.lower() != 'yes':
                print("Deletion cancelled.")
                conn.close()
                return

            cursor.execute('DELETE FROM questions WHERE bank_id = ?', (bank_id,))
            cursor.execute('DELETE FROM question_banks WHERE id = ?', (bank_id,))

            conn.commit()
            conn.close()

            print(f"Question bank '{bank[0]}' deleted successfully.")

        except Exception as e:
            print(f"Error deleting question bank: {e}")

    def add_question_to_bank(self):
        """Add MCQ/fill-blank/coding question to a bank."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            bank_id = input("Enter question bank ID: ").strip()
            if not bank_id.isdigit():
                print("Invalid bank ID.")
                return

            bank_id = int(bank_id)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT name FROM question_banks WHERE id = ?', (bank_id,))
            bank = cursor.fetchone()

            if not bank:
                print("Question bank not found.")
                conn.close()
                return

            print(f"\nAdding question to: {bank[0]}")
            print("Question types: mcq, fill_blank, coding")

            q_type = input("Question type: ").strip().lower()
            if q_type not in ('mcq', 'fill_blank', 'coding'):
                print("Invalid question type. Must be mcq, fill_blank, or coding.")
                conn.close()
                return

            q_text = input("Question text: ").strip()
            if not q_text:
                print("Question text cannot be empty.")
                conn.close()
                return

            # Points
            while True:
                try:
                    points = float(input("Points: "))
                    if points <= 0:
                        print("Points must be positive.")
                        continue
                    break
                except ValueError:
                    print("Please enter a valid number.")

            # Difficulty
            difficulty = input("Difficulty (easy/medium/hard): ").strip().lower()
            if difficulty not in ('easy', 'medium', 'hard'):
                print("Invalid difficulty. Defaulting to 'medium'.")
                difficulty = 'medium'

            options = None
            correct_answer = None
            test_cases = None

            if q_type == 'mcq':
                print("\nEnter options (type 'done' when finished):")
                option_list = []
                letter = ord('A')
                while True:
                    opt = input(f"  Option {chr(letter)}: ").strip()
                    if opt.lower() == 'done':
                        break
                    option_list.append({'label': chr(letter), 'text': opt})
                    letter += 1

                if len(option_list) < 2:
                    print("MCQ requires at least 2 options.")
                    conn.close()
                    return

                options = json.dumps(option_list)

                valid_labels = [o['label'] for o in option_list]
                while True:
                    correct_answer = input(
                        f"Correct answer ({'/'.join(valid_labels)}): ").strip().upper()
                    if correct_answer in valid_labels:
                        break
                    print(f"Must be one of: {', '.join(valid_labels)}")

            elif q_type == 'fill_blank':
                correct_answer = input("Correct answer: ").strip()
                if not correct_answer:
                    print("Correct answer cannot be empty.")
                    conn.close()
                    return

                tolerance = input("Fuzzy match tolerance 0.0-1.0 (default 0.8): ").strip()
                try:
                    tolerance = float(tolerance) if tolerance else 0.8
                    if not (0.0 <= tolerance <= 1.0):
                        tolerance = 0.8
                except ValueError:
                    tolerance = 0.8

                # Store tolerance alongside answer
                options = json.dumps({'tolerance': tolerance})

            elif q_type == 'coding':
                correct_answer = input("Expected solution (reference code, optional): ").strip()

                print("\nEnter test cases (type 'done' when finished):")
                tc_list = []
                while True:
                    tc_input = input("  Test input (or 'done'): ").strip()
                    if tc_input.lower() == 'done':
                        break
                    tc_output = input("  Expected output: ").strip()
                    tc_list.append({'input': tc_input, 'expected_output': tc_output})

                if not tc_list:
                    print("Coding questions require at least one test case.")
                    conn.close()
                    return

                test_cases = json.dumps(tc_list)
                options = test_cases  # Store test cases in options column

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO questions (bank_id, question_type, question_text, options,
                                   correct_answer, points, difficulty, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (bank_id, q_type, q_text, options, correct_answer,
                  points, difficulty, timestamp))

            conn.commit()
            question_id = cursor.lastrowid
            conn.close()

            print(f"\nQuestion added successfully! (ID: {question_id})")

        except Exception as e:
            print(f"Error adding question: {e}")

    def auto_grade_mcq(self, submission_id):
        """Compare student answer to correct answer for MCQ."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sa.student_answer, q.correct_answer, q.points
            FROM student_answers sa
            JOIN questions q ON sa.question_id = q.id
            WHERE sa.id = ?
            ''', (submission_id,))

            row = cursor.fetchone()
            if not row:
                print(f"  Answer {submission_id} not found.")
                conn.close()
                return

            student_answer, correct_answer, points = row

            student_answer = (student_answer or '').strip().upper()
            correct_answer = (correct_answer or '').strip().upper()

            earned = points if student_answer == correct_answer else 0.0
            is_correct = 1 if student_answer == correct_answer else 0

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            UPDATE student_answers
            SET points_earned = ?, is_correct = ?, graded = 1, graded_at = ?,
                feedback = ?
            WHERE id = ?
            ''', (earned, is_correct, timestamp,
                  'Correct!' if is_correct else f'Incorrect. Correct answer: {correct_answer}',
                  submission_id))

            conn.commit()
            conn.close()

            status = "correct" if is_correct else "incorrect"
            print(f"  MCQ #{submission_id}: {status} ({earned}/{points} pts)")

        except Exception as e:
            print(f"  Error grading MCQ {submission_id}: {e}")

    def auto_grade_fill_blank(self, submission_id):
        """Fuzzy match student answer with configurable tolerance."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sa.student_answer, q.correct_answer, q.points, q.options
            FROM student_answers sa
            JOIN questions q ON sa.question_id = q.id
            WHERE sa.id = ?
            ''', (submission_id,))

            row = cursor.fetchone()
            if not row:
                print(f"  Answer {submission_id} not found.")
                conn.close()
                return

            student_answer, correct_answer, points, options_json = row

            # Parse tolerance from options
            tolerance = 0.8
            if options_json:
                try:
                    opts = json.loads(options_json)
                    tolerance = opts.get('tolerance', 0.8)
                except (json.JSONDecodeError, TypeError):
                    pass

            student_answer = (student_answer or '').strip().lower()
            correct_answer = (correct_answer or '').strip().lower()

            similarity = self._calculate_similarity(student_answer, correct_answer)
            is_correct = 1 if similarity >= tolerance else 0
            earned = points if is_correct else 0.0

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if is_correct:
                feedback = f'Correct! (similarity: {similarity:.2f})'
            else:
                feedback = (f'Incorrect. Your answer: "{student_answer}", '
                            f'expected: "{correct_answer}" '
                            f'(similarity: {similarity:.2f}, required: {tolerance:.2f})')

            cursor.execute('''
            UPDATE student_answers
            SET points_earned = ?, is_correct = ?, graded = 1, graded_at = ?,
                feedback = ?
            WHERE id = ?
            ''', (earned, is_correct, timestamp, feedback, submission_id))

            conn.commit()
            conn.close()

            status = "correct" if is_correct else "incorrect"
            print(f"  Fill-blank #{submission_id}: {status} "
                  f"(similarity: {similarity:.2f}, {earned}/{points} pts)")

        except Exception as e:
            print(f"  Error grading fill-blank {submission_id}: {e}")

    def _calculate_similarity(self, s1, s2):
        """Calculate similarity ratio between two strings using SequenceMatcher."""
        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        from difflib import SequenceMatcher
        return SequenceMatcher(None, s1, s2).ratio()

    def auto_grade_coding(self, submission_id):
        """Run student code against test cases in subprocess with timeout."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sa.student_answer, q.correct_answer, q.points, q.options
            FROM student_answers sa
            JOIN questions q ON sa.question_id = q.id
            WHERE sa.id = ?
            ''', (submission_id,))

            row = cursor.fetchone()
            if not row:
                print(f"  Answer {submission_id} not found.")
                conn.close()
                return

            student_code, reference_code, points, test_cases_json = row

            if not student_code or not student_code.strip():
                self._save_coding_grade(cursor, conn, submission_id, 0.0, 0,
                                        "No code submitted.")
                print(f"  Coding #{submission_id}: no code submitted (0/{points} pts)")
                return

            # Parse test cases
            try:
                test_cases = json.loads(test_cases_json) if test_cases_json else []
            except (json.JSONDecodeError, TypeError):
                test_cases = []

            if not test_cases:
                self._save_coding_grade(cursor, conn, submission_id, 0.0, 0,
                                        "No test cases defined for this question.")
                print(f"  Coding #{submission_id}: no test cases defined")
                return

            passed = 0
            total = len(test_cases)
            feedback_lines = []

            for i, tc in enumerate(test_cases, 1):
                tc_input = tc.get('input', '')
                expected_output = tc.get('expected_output', '').strip()

                try:
                    # Write student code to temp file and run in subprocess
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.py',
                                                     delete=False) as tmp:
                        tmp.write(student_code)
                        tmp_path = tmp.name

                    try:
                        result = subprocess.run(  # nosec B603
                            ['python3', tmp_path],
                            input=tc_input,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )

                        actual_output = result.stdout.strip()

                        if result.returncode != 0:
                            feedback_lines.append(
                                f"Test {i}: RUNTIME ERROR - {result.stderr.strip()[:200]}")
                        elif actual_output == expected_output:
                            passed += 1
                            feedback_lines.append(f"Test {i}: PASSED")
                        else:
                            feedback_lines.append(
                                f"Test {i}: FAILED - Expected: '{expected_output}', "
                                f"Got: '{actual_output}'")
                    finally:
                        os.unlink(tmp_path)

                except subprocess.TimeoutExpired:
                    feedback_lines.append(f"Test {i}: TIMEOUT (>10s)")
                    # Clean up temp file on timeout
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception as e:
                    feedback_lines.append(f"Test {i}: ERROR - {str(e)[:200]}")

            # Calculate proportional score
            earned = (passed / total) * points if total > 0 else 0.0
            is_correct = 1 if passed == total else 0

            feedback = (f"Passed {passed}/{total} test cases.\n" +
                        "\n".join(feedback_lines))

            self._save_coding_grade(cursor, conn, submission_id, earned,
                                    is_correct, feedback)

            print(f"  Coding #{submission_id}: {passed}/{total} tests passed "
                  f"({earned:.1f}/{points} pts)")

        except Exception as e:
            print(f"  Error grading coding {submission_id}: {e}")

    def _save_coding_grade(self, cursor, conn, submission_id, earned, is_correct, feedback):
        """Save coding grade to database."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        UPDATE student_answers
        SET points_earned = ?, is_correct = ?, graded = 1, graded_at = ?,
            feedback = ?
        WHERE id = ?
        ''', (earned, is_correct, timestamp, feedback, submission_id))
        conn.commit()

    def run_batch_auto_grading(self):
        """Auto-grade all pending submissions for a selected assignment."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT a.id, a.title, a.module_code,
                   COUNT(sa.id) as pending
            FROM assignments a
            JOIN student_answers sa ON sa.assignment_id = a.id
            WHERE sa.graded = 0
            GROUP BY a.id, a.title, a.module_code
            ORDER BY pending DESC
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("No assignments with pending submissions.")
                conn.close()
                return

            print("\nBatch Auto-Grading")
            print("=" * 70)
            print(f"{'#':<5} {'Assignment':<30} {'Module':<15} {'Pending':<10}")
            print("-" * 70)

            for i, (aid, title, module, pending) in enumerate(assignments, 1):
                print(f"{i:<5} {title[:28]:<30} {module:<15} {pending:<10}")

            print(f"\n{'A':<5} {'Grade ALL assignments'}")

            choice = input("\nSelect assignment number or 'A' for all (or 'q' to quit): ").strip()

            if choice.lower() == 'q':
                conn.close()
                return

            if choice.upper() == 'A':
                targets = assignments
            elif choice.isdigit() and 1 <= int(choice) <= len(assignments):
                targets = [assignments[int(choice) - 1]]
            else:
                print("Invalid selection.")
                conn.close()
                return

            conn.close()

            total_graded = 0
            total_errors = 0

            for aid, title, module, pending in targets:
                print(f"\nGrading: {title} ({pending} pending)")
                print("-" * 40)

                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute('''
                SELECT sa.id, q.question_type
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                WHERE sa.assignment_id = ? AND sa.graded = 0
                ''', (aid,))

                answers = cursor.fetchall()
                conn.close()

                for answer_id, q_type in answers:
                    try:
                        if q_type == 'mcq':
                            self.auto_grade_mcq(answer_id)
                        elif q_type == 'fill_blank':
                            self.auto_grade_fill_blank(answer_id)
                        elif q_type == 'coding':
                            self.auto_grade_coding(answer_id)
                        else:
                            print(f"  Skipping answer {answer_id}: unknown type '{q_type}'")
                            continue
                        total_graded += 1
                    except Exception as e:
                        print(f"  Error grading answer {answer_id}: {e}")
                        total_errors += 1

            print("\nBatch grading complete!")
            print(f"  Total graded: {total_graded}")
            print(f"  Total errors: {total_errors}")

        except Exception as e:
            print(f"Error in batch auto-grading: {e}")

    def view_question_bank_stats(self):
        """Per-question difficulty stats: % wrong, avg time spent."""
        if not self._check_permission('manage_assignments'):
            return

        try:
            bank_id = input("Enter question bank ID: ").strip()
            if not bank_id.isdigit():
                print("Invalid bank ID.")
                return

            bank_id = int(bank_id)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT name FROM question_banks WHERE id = ?', (bank_id,))
            bank = cursor.fetchone()

            if not bank:
                print("Question bank not found.")
                conn.close()
                return

            print(f"\nQuestion Bank Stats: {bank[0]}")
            print("=" * 90)

            cursor.execute('''
            SELECT
                q.id,
                q.question_text,
                q.question_type,
                q.difficulty,
                q.points,
                COUNT(sa.id) as attempts,
                SUM(CASE WHEN sa.is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
                AVG(sa.time_spent) as avg_time
            FROM questions q
            LEFT JOIN student_answers sa ON sa.question_id = q.id AND sa.graded = 1
            WHERE q.bank_id = ?
            GROUP BY q.id, q.question_text, q.question_type, q.difficulty, q.points
            ORDER BY q.id
            ''', (bank_id,))

            questions = cursor.fetchall()
            conn.close()

            if not questions:
                print("No questions in this bank.")
                return

            print(f"{'ID':<5} {'Question':<30} {'Type':<12} {'Diff':<8} "
                  f"{'Attempts':<10} {'% Wrong':<10} {'Avg Time':<10}")
            print("-" * 90)

            for qid, text, q_type, diff, pts, attempts, correct, avg_time in questions:
                if attempts and attempts > 0:
                    pct_wrong = ((attempts - (correct or 0)) / attempts) * 100
                    time_str = f"{avg_time:.1f}s" if avg_time else "N/A"
                else:
                    pct_wrong = 0.0
                    time_str = "N/A"

                q_text = text[:28] if text else "(no text)"
                print(f"{qid:<5} {q_text:<30} {q_type:<12} {diff:<8} "
                      f"{attempts or 0:<10} {pct_wrong:>6.1f}%   {time_str:<10}")

            # Summary
            total_questions = len(questions)
            total_attempts = sum(q[5] or 0 for q in questions)
            total_correct = sum(q[6] or 0 for q in questions)

            print("\nSummary:")
            print(f"  Total questions: {total_questions}")
            print(f"  Total attempts: {total_attempts}")
            if total_attempts > 0:
                overall_pct = ((total_attempts - total_correct) / total_attempts) * 100
                print(f"  Overall % wrong: {overall_pct:.1f}%")

        except Exception as e:
            print(f"Error viewing question bank stats: {e}")

    def generate_random_quiz(self, bank_id, count):
        """Select random questions from a question bank."""
        if not self._check_permission('manage_assignments'):
            return None

        try:
            bank_id = int(bank_id)
            count = int(count)

            if count <= 0:
                print("Count must be a positive integer.")
                return None

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT name FROM question_banks WHERE id = ?', (bank_id,))
            bank = cursor.fetchone()

            if not bank:
                print("Question bank not found.")
                conn.close()
                return None

            cursor.execute('''
            SELECT id, question_type, question_text, options, correct_answer,
                   points, difficulty
            FROM questions
            WHERE bank_id = ?
            ''', (bank_id,))

            all_questions = cursor.fetchall()
            conn.close()

            if not all_questions:
                print("No questions available in this bank.")
                return None

            if count > len(all_questions):
                print(f"Requested {count} questions but only {len(all_questions)} available. "
                      f"Using all questions.")
                count = len(all_questions)

            selected = random.sample(all_questions, count)

            total_points = 0
            print(f"\nGenerated Quiz from: {bank[0]}")
            print(f"Questions: {count}")
            print("=" * 60)

            quiz_questions = []
            for i, (qid, q_type, text, options, answer, pts, diff) in enumerate(selected, 1):
                print(f"\nQ{i}. [{q_type.upper()}] ({pts} pts, {diff})")
                print(f"    {text}")

                if q_type == 'mcq' and options:
                    try:
                        opts = json.loads(options)
                        for opt in opts:
                            print(f"      {opt['label']}. {opt['text']}")
                    except (json.JSONDecodeError, TypeError):
                        pass

                total_points += pts
                quiz_questions.append({
                    'question_id': qid,
                    'question_type': q_type,
                    'question_text': text,
                    'options': options,
                    'points': pts,
                    'difficulty': diff
                })

            print(f"\nTotal points: {total_points}")
            print(f"Question breakdown: "
                  f"{sum(1 for q in selected if q[1] == 'mcq')} MCQ, "
                  f"{sum(1 for q in selected if q[1] == 'fill_blank')} fill-blank, "
                  f"{sum(1 for q in selected if q[1] == 'coding')} coding")

            return quiz_questions

        except ValueError:
            print("Invalid bank_id or count value.")
            return None
        except Exception as e:
            print(f"Error generating random quiz: {e}")
            return None
