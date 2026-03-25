from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime


class PeerReviewMixin:
    """Mixin providing peer review setup, assignment, submission, and management."""

    def setup_peer_review(self):
        """Set up peer review for an assignment"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, title, module_code, due_date
            FROM assignments
            WHERE is_active = 1
            ORDER BY due_date
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("No assignments found.")
                conn.close()
                return

            print("\nSelect Assignment for Peer Review:")
            for i, (aid, title, module, due_date) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Due: {due_date}")

            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(assignments):
                    assignment_id = assignments[index][0]
                    self._configure_peer_review(cursor, assignment_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")

            conn.close()

        except Exception as e:
            print(f"Error setting up peer review: {e}")

    def _configure_peer_review(self, cursor, assignment_id):
        """Configure peer review settings"""
        print("\nPeer Review Configuration:")

        cursor.execute('''
        UPDATE assignments SET peer_review_enabled = 1 WHERE id = ?
        ''', (assignment_id,))

        criteria = []
        print("\nAdd review criteria (type 'done' when finished):")
        while True:
            criterion = input("Criterion name (or 'done'): ").strip()
            if criterion.lower() == 'done':
                break
            criteria.append(criterion)

        print("\nAssigning peer reviewers...")
        self._assign_peer_reviewers(cursor, assignment_id, criteria)

        cursor.connection.commit()
        print("Peer review setup completed!")

    def _assign_peer_reviewers(self, cursor, assignment_id, criteria):
        """Assign peer reviewers for an assignment"""
        cursor.execute('''
        SELECT student_id FROM assignment_submissions
        WHERE assignment_id = ? AND status = 'submitted'
        ''', (assignment_id,))

        students = [row[0] for row in cursor.fetchall()]

        if len(students) < 2:
            print("Need at least 2 submissions for peer review.")
            return

        assignments = []
        for i, reviewer in enumerate(students):
            reviewee = students[(i + 1) % len(students)]
            assignments.append((reviewer, reviewee))

        for reviewer, reviewee in assignments:
            cursor.execute('''
            SELECT id FROM assignment_submissions
            WHERE assignment_id = ? AND student_id = ? AND status = 'submitted'
            ORDER BY submission_date DESC LIMIT 1
            ''', (assignment_id, reviewee))

            submission_id = cursor.fetchone()[0]

            cursor.execute('''
            INSERT INTO peer_reviews (assignment_id, reviewer_id, reviewee_id, submission_id, review_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (assignment_id, reviewer, reviewee, submission_id,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'pending'))

        print(f"Assigned {len(assignments)} peer reviews.")

    def assign_peer_reviewers(self, assignment_id, reviews_per_submission=2):
        """Assign peer reviewers for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT id, student_id FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))
            submissions = cursor.fetchall()

            if len(submissions) < 2:
                print("Not enough submissions for peer review")
                return False

            for submission_id, student_id in submissions:
                other_submissions = [s for s in submissions if s[1] != student_id]

                import random
                reviewers = random.sample(other_submissions, min(reviews_per_submission, len(other_submissions)))

                for reviewer_submission in reviewers:
                    reviewer_id = reviewer_submission[1]
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute('''
                        INSERT INTO peer_review_assignments (
                            assignment_id, submission_id, reviewer_id, status, assigned_at
                        ) VALUES (?, ?, ?, 'pending', ?)
                    ''', (assignment_id, submission_id, reviewer_id, timestamp))

            conn.commit()
            self._log_action('create', 'peer_review_assignments', None, {'assignment_id': assignment_id})
            conn.close()

            print(f"Peer reviewers assigned for {len(submissions)} submissions")
            return True

        except Exception as e:
            print(f"Error assigning peer reviewers: {e}")
            return False

    def submit_peer_review(self, review_assignment_id, feedback, rating):
        """Submit a peer review"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE peer_review_assignments
                SET feedback = ?, rating = ?, status = 'completed', completed_at = ?
                WHERE id = ?
            ''', (feedback, rating, timestamp, review_assignment_id))

            conn.commit()
            self._log_action('update', 'peer_review_assignments', review_assignment_id)
            conn.close()

            print("Peer review submitted successfully!")
            return True

        except Exception as e:
            print(f"Error submitting peer review: {e}")
            return False

    def get_peer_review_assignments(self, reviewer_id=None):
        """Get peer review assignments for a reviewer"""
        try:
            if not reviewer_id:
                reviewer_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM peer_review_assignments
                    WHERE reviewer_id = ?
                    ORDER BY assigned_at DESC
                ''', (reviewer_id,))

                assignments = cursor.fetchall()
            finally:
                conn.close()
            return assignments

        except Exception as e:
            print(f"Error retrieving peer review assignments: {e}")
            return []

    def configure_peer_review_criteria(self, assignment_id, criteria):
        """Configure peer review criteria for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peer_review_criteria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    criterion_name TEXT NOT NULL,
                    criterion_description TEXT,
                    max_points INTEGER DEFAULT 10,
                    FOREIGN KEY (assignment_id) REFERENCES assignments (id)
                )
            ''')

            for criterion in criteria:
                cursor.execute('''
                    INSERT INTO peer_review_criteria (assignment_id, criterion_name, criterion_description, max_points)
                    VALUES (?, ?, ?, ?)
                ''', (assignment_id, criterion['name'], criterion.get('description', ''), criterion.get('max_points', 10)))

            conn.commit()
            self._log_action('create', 'peer_review_criteria', None, {'assignment_id': assignment_id})
            conn.close()

            print("Peer review criteria configured successfully!")
            return True

        except Exception as e:
            print(f"Error configuring peer review criteria: {e}")
            return False

    def complete_peer_review(self, review_assignment_id):
        """Mark a peer review as complete"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE peer_review_assignments
                SET status = 'completed', completed_at = ?
                WHERE id = ?
            ''', (timestamp, review_assignment_id))

            conn.commit()
            self._log_action('update', 'peer_review_assignments', review_assignment_id)
            conn.close()

            print("Peer review completed successfully!")
            return True

        except Exception as e:
            print(f"Error completing peer review: {e}")
            return False
