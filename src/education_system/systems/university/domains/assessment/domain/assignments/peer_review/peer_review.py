from education_system.systems.university.infrastructure.database.db import sqlite3
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

            # Clear any unstarted allocation for this pair so re-running is safe.
            cursor.execute('''
            DELETE FROM peer_reviews WHERE assignment_id = ? AND reviewer_id = ?
               AND reviewee_id = ? AND status = 'pending'
            ''', (assignment_id, reviewer, reviewee))
            cursor.execute('''
            INSERT INTO peer_reviews (assignment_id, reviewer_id, reviewee_id, submission_id,
                                      status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            ''', (assignment_id, reviewer, reviewee, submission_id,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

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

    # ── review lists (both storage tables) ─────────────────────────────
    #
    # Reviews are allocated into one of two tables depending on which screen
    # set them up: the CLI writes ``peer_reviews``, the GUI writes
    # ``peer_review_assignments``. These helpers read both, tagged with the
    # source, so students and staff see every review wherever it lives.

    PEER_CRITERIA = ("Content quality", "Organisation", "Clarity", "Use of evidence")

    @staticmethod
    def _table_columns(conn, table):
        return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}

    def _peer_review_rows(self, conn, reviewer_id=None, assignment_id=None, status=None):
        rows = []
        sources = (
            ("peer_reviews", "COALESCE(pr.submission_id, pr.reviewee_submission_id)", "pr.created_at",
             "pr.overall_score", "pr.review_text"),
            ("peer_review_assignments", "pr.submission_id", "COALESCE(pr.assigned_date, pr.assigned_at)",
             "pr.rating", "pr.feedback"),
        )
        for table, sub_col, when_col, score_col, text_col in sources:
            if not self._table_columns(conn, table):
                continue
            where, params = [], []
            if reviewer_id is not None:
                where.append("CAST(pr.reviewer_id AS TEXT) = ?")
                params.append(str(reviewer_id))
            if assignment_id is not None:
                where.append("CAST(pr.assignment_id AS TEXT) = ?")
                params.append(str(assignment_id))
            if status:
                where.append("pr.status = ?")
                params.append(status)
            sql = (f"SELECT pr.id, '{table}' AS source, pr.reviewer_id, pr.reviewee_id, pr.status, "
                   f"       {sub_col} AS submission_id, {when_col} AS assigned, "
                   f"       {score_col} AS score, {text_col} AS review_text, "
                   f"       a.id AS assignment_id, a.title, a.module_code, s.file_name, s.file_path "
                   f"FROM {table} pr "
                   f"LEFT JOIN assignment_submissions s ON s.id = {sub_col} "
                   f"LEFT JOIN assignments a ON a.id = COALESCE(s.assignment_id, pr.assignment_id) "
                   + ("WHERE " + " AND ".join(where) if where else ""))  # nosec B608 - fixed names
            try:
                rows.extend(dict(r) for r in conn.execute(sql, params))
            except sqlite3.Error as e:
                print(f"Warning: could not read {table}: {e}")
        return rows

    def complete_peer_reviews(self):
        """Student: complete the peer reviews you have been allocated."""
        if not self._check_permission('view_assignments'):
            return
        student_id = self._get_student_id()
        if not student_id:
            print("No student ID associated with your account.")
            return
        while True:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                pending = self._peer_review_rows(conn, reviewer_id=student_id, status='pending')
            finally:
                conn.close()
            if not pending:
                print("\nYou have no peer reviews to complete.")
                return
            print(f"\n{'#':<4} {'Assignment':<34} {'Module':<11} {'Work to review':<28}")
            print("-" * 80)
            for i, r in enumerate(pending, 1):
                print(f"{i:<4} {str(r['title'] or '—')[:33]:<34} {str(r['module_code'] or '')[:10]:<11} "
                      f"{str(r['file_name'] or '—')[:27]:<28}")
            choice = input("\nReview number to complete (Enter to go back): ").strip()
            if not choice.isdigit() or not 0 < int(choice) <= len(pending):
                return
            self._complete_one_peer_review(pending[int(choice) - 1])

    def _complete_one_peer_review(self, review):
        print(f"\nReviewing work for: {review['title']}  (the author is not shown to you)")
        if review['file_path']:
            print(f"File: {review['file_path']}")
        scores = {}
        for criterion in self.PEER_CRITERIA:
            while True:
                value = input(f"{criterion} (1-5): ").strip()
                if value in {'1', '2', '3', '4', '5'}:
                    scores[criterion] = int(value)
                    break
                print("Enter a whole number from 1 to 5.")
        comments = input("Comments for the author: ").strip()
        if not comments:
            print("Please leave at least a short comment; the review was not saved.")
            return
        overall = round(sum(scores.values()) / len(scores), 2)
        breakdown = "; ".join(f"{k}: {v}/5" for k, v in scores.items())
        text = f"{comments}\n\n[{breakdown}]"
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(self.db_path)
        try:
            if review['source'] == 'peer_reviews':
                conn.execute(
                    "UPDATE peer_reviews SET overall_score = ?, review_text = ?, status = 'completed', "
                    "review_date = ? WHERE id = ?", (overall, text, now, review['id']))
            else:
                conn.execute(
                    "UPDATE peer_review_assignments SET rating = ?, feedback = ?, status = 'completed', "
                    "completed_at = ? WHERE id = ?", (overall, text, now, review['id']))
            conn.commit()
        finally:
            conn.close()
        self._log_action('update', review['source'], review['id'], None, {'status': 'completed'})
        print(f"Review submitted (average {overall:g}/5). Thank you.")

    def manage_peer_reviews(self):
        """Staff: progress of peer review per assignment; allocate, reopen or remove reviews."""
        if not self._check_permission('manage_assignments'):
            return
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            assignments = conn.execute(
                "SELECT id, module_code, title, due_date FROM assignments "
                "WHERE COALESCE(peer_review_enabled, 0) = 1 AND COALESCE(is_active, 1) = 1 "
                "ORDER BY due_date DESC").fetchall()
            all_reviews = self._peer_review_rows(conn)
        finally:
            conn.close()
        by_assignment = {}
        for r in all_reviews:
            by_assignment.setdefault(r['assignment_id'], []).append(r)
        if not assignments and not all_reviews:
            print("\nNo assignments use peer review. Enable it with 'Setup Peer Review'.")
            return
        print(f"\n{'ID':<5} {'Module':<11} {'Title':<36} {'Done':>6} {'Pending':>8}")
        print("-" * 70)
        for a in assignments:
            reviews = by_assignment.get(a['id'], [])
            done = sum(1 for r in reviews if r['status'] == 'completed')
            print(f"{a['id']:<5} {str(a['module_code'])[:10]:<11} {str(a['title'])[:35]:<36} "
                  f"{done:>6} {len(reviews) - done:>8}")
        choice = input("\nAssignment ID to manage (Enter to go back): ").strip()
        if not choice.isdigit():
            return
        aid = int(choice)
        reviews = by_assignment.get(aid, [])
        if reviews:
            print(f"\n{'#':<4} {'Reviewer':<12} {'Reviewee':<12} {'Status':<10} {'Score':>6}")
            for i, r in enumerate(reviews, 1):
                score = '' if r['score'] in (None, '') else f"{float(r['score']):.1f}"
                print(f"{i:<4} {str(r['reviewer_id'])[:11]:<12} {str(r['reviewee_id'] or '—')[:11]:<12} "
                      f"{str(r['status'])[:9]:<10} {score:>6}")
        else:
            print("No reviews allocated yet.")
        print("\n1. Allocate reviewers  2. Read a review  3. Reopen a review  4. Remove a review  0. Back")
        action = input("Choice: ").strip()
        if action == '1':
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                self._assign_peer_reviewers(cursor, aid, list(self.PEER_CRITERIA))
                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                print(f"Could not allocate reviewers: {e}")
            finally:
                conn.close()
            return
        if action not in ('2', '3', '4') or not reviews:
            return
        pick = input("Review #: ").strip()
        if not pick.isdigit() or not 0 < int(pick) <= len(reviews):
            print("Invalid review number.")
            return
        r = reviews[int(pick) - 1]
        if action == '2':
            print(f"\nReviewer {r['reviewer_id']} on {r['reviewee_id']}'s work ({r['status']}):")
            print(r['review_text'] or '(no text yet)')
            return
        conn = sqlite3.connect(self.db_path)
        try:
            if action == '3':
                conn.execute(f"UPDATE {r['source']} SET status = 'pending' WHERE id = ?", (r['id'],))  # nosec B608
                message = "Review reopened."
            else:
                conn.execute(f"DELETE FROM {r['source']} WHERE id = ?", (r['id'],))  # nosec B608
                message = "Review removed."
            conn.commit()
        finally:
            conn.close()
        self._log_action('update' if action == '3' else 'delete', r['source'], r['id'])
        print(message)
