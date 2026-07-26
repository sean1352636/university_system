from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime


class GradeDisputeMixin:
    """Mixin providing grade dispute submission, review, history, and analytics."""

    def submit_grade_dispute(self):
        """Submit a grade dispute for a graded assignment"""
        if not self._check_permission('submit_assignment'):
            return

        try:
            student_id = self._get_student_id()
            if not student_id:
                print("No student ID associated with your account.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT s.id, a.title, a.module_code, s.grade, s.graded_date
                FROM assignment_submissions s
                JOIN assignments a ON s.assignment_id = a.id
                WHERE s.student_id = ? AND s.grade IS NOT NULL
                ORDER BY s.graded_date DESC
                ''', (student_id,))

                submissions = cursor.fetchall()

                if not submissions:
                    print("No graded assignments found.")
                    return

                print("\nGraded Assignments:")
                print("=" * 80)
                print(f"{'#':<4} {'Assignment':<30} {'Module':<12} {'Grade':<10} {'Graded':<20}")
                print("-" * 80)
                for i, (sid, title, module, grade, graded_date) in enumerate(submissions, 1):
                    title_display = title[:28] if title else "N/A"
                    grade_display = f"{grade:.1f}%" if grade is not None else "N/A"
                    print(f"{i:<4} {title_display:<30} {module:<12} {grade_display:<10} {graded_date or 'N/A':<20}")

                choice = input("\nSelect assignment number to dispute: ").strip()
                try:
                    index = int(choice) - 1
                    if not (0 <= index < len(submissions)):
                        print("Invalid selection.")
                        return
                except ValueError:
                    print("Please enter a number.")
                    return

                submission_id = submissions[index][0]

                # Check for existing pending dispute
                cursor.execute('''
                SELECT id FROM grade_disputes
                WHERE submission_id = ? AND student_id = ? AND status = 'pending'
                ''', (submission_id, student_id))

                if cursor.fetchone():
                    print("You already have a pending dispute for this assignment.")
                    return

                print("\nGrade Dispute Form:")
                reason = input("Reason for dispute: ").strip()
                if not reason:
                    print("Reason cannot be empty.")
                    return

                evidence_path = input("Evidence file path (optional, press Enter to skip): ").strip()
                if evidence_path:
                    import os
                    if not os.path.exists(evidence_path):
                        confirm = input("File not found. Continue without evidence? (y/n): ").lower()
                        if confirm != 'y':
                            print("Dispute cancelled.")
                            return
                        evidence_path = ""

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO grade_disputes
                (submission_id, student_id, reason, evidence_path, status, submitted_date)
                VALUES (?, ?, ?, ?, 'pending', ?)
                ''', (submission_id, student_id, reason, evidence_path or None, timestamp))

                conn.commit()

                print("\nGrade dispute submitted successfully!")
                print("You will be notified when it has been reviewed.")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error submitting grade dispute: {e}")

    def view_my_disputes(self):
        """View current student's grade disputes with status"""
        if not self._check_permission('submit_assignment'):
            return

        try:
            student_id = self._get_student_id()
            if not student_id:
                print("No student ID associated with your account.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT gd.id, a.title, a.module_code, s.grade, gd.reason,
                       gd.status, gd.submitted_date, gd.reviewed_date,
                       gd.reviewer_comments, gd.updated_grade
                FROM grade_disputes gd
                JOIN assignment_submissions s ON gd.submission_id = s.id
                JOIN assignments a ON s.assignment_id = a.id
                WHERE gd.student_id = ?
                ORDER BY gd.submitted_date DESC
                ''', (student_id,))

                disputes = cursor.fetchall()

                if not disputes:
                    print("You have no grade disputes.")
                    return

                print("\nMy Grade Disputes:")
                print("=" * 100)
                for dispute in disputes:
                    (dispute_id, title, module, grade, reason, status,
                     submitted, reviewed, comments, updated_grade) = dispute
                    print(f"\nDispute ID: {dispute_id}")
                    print(f"Assignment: {title} ({module})")
                    print(f"Original Grade: {grade:.1f}%" if grade is not None else "Original Grade: N/A")
                    print(f"Reason: {reason}")
                    print(f"Status: {status.upper()}")
                    print(f"Submitted: {submitted}")
                    if reviewed:
                        print(f"Reviewed: {reviewed}")
                    if comments:
                        print(f"Reviewer Comments: {comments}")
                    if updated_grade is not None:
                        print(f"Updated Grade: {updated_grade:.1f}%")
                    print("-" * 100)

            finally:
                conn.close()

        except Exception as e:
            print(f"Error viewing disputes: {e}")

    def view_regrade_queue(self):
        """View all pending regrade requests (instructor/admin only)"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT gd.id, gd.student_id, st.first_name, st.last_name,
                       a.title, a.module_code, s.grade, gd.reason,
                       gd.submitted_date, gd.evidence_path
                FROM grade_disputes gd
                JOIN assignment_submissions s ON gd.submission_id = s.id
                JOIN assignments a ON s.assignment_id = a.id
                JOIN students st ON gd.student_id = st.student_id
                WHERE gd.status = 'pending'
                ORDER BY gd.submitted_date
                ''')

                disputes = cursor.fetchall()

                if not disputes:
                    print("No pending regrade requests.")
                    return

                print("\nPending Regrade Queue:")
                print("=" * 110)
                print(f"{'ID':<6} {'Student':<25} {'Assignment':<25} {'Module':<12} {'Grade':<8} {'Submitted':<20}")
                print("-" * 110)

                for dispute in disputes:
                    (dispute_id, sid, fname, lname, title, module,
                     grade, reason, submitted, evidence) = dispute
                    student_name = f"{fname} {lname}"[:23]
                    title_display = title[:23] if title else "N/A"
                    grade_display = f"{grade:.1f}%" if grade is not None else "N/A"
                    print(f"{dispute_id:<6} {student_name:<25} {title_display:<25} {module:<12} {grade_display:<8} {submitted:<20}")

                print(f"\nTotal pending: {len(disputes)}")

                # Show details for a specific dispute
                detail = input("\nEnter dispute ID for details (or press Enter to skip): ").strip()
                if detail and detail.isdigit():
                    dispute_id = int(detail)
                    for dispute in disputes:
                        if dispute[0] == dispute_id:
                            print("\nDispute Details:")
                            print(f"Student: {dispute[2]} {dispute[3]} ({dispute[1]})")
                            print(f"Assignment: {dispute[4]} ({dispute[5]})")
                            print(f"Current Grade: {dispute[6]:.1f}%" if dispute[6] is not None else "Current Grade: N/A")
                            print(f"Reason: {dispute[7]}")
                            print(f"Submitted: {dispute[8]}")
                            if dispute[9]:
                                print(f"Evidence: {dispute[9]}")
                            break
                    else:
                        print("Dispute not found in pending queue.")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error viewing regrade queue: {e}")

    def review_grade_dispute(self):
        """Review and resolve a grade dispute (instructor/admin only)"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT gd.id, gd.submission_id, gd.student_id, st.first_name, st.last_name,
                       a.title, a.module_code, s.grade, gd.reason, gd.evidence_path
                FROM grade_disputes gd
                JOIN assignment_submissions s ON gd.submission_id = s.id
                JOIN assignments a ON s.assignment_id = a.id
                JOIN students st ON gd.student_id = st.student_id
                WHERE gd.status = 'pending'
                ORDER BY gd.submitted_date
                ''')

                disputes = cursor.fetchall()

                if not disputes:
                    print("No pending grade disputes to review.")
                    return

                print("\nPending Grade Disputes:")
                print("=" * 100)
                for dispute in disputes:
                    (dispute_id, sub_id, sid, fname, lname,
                     title, module, grade, reason, evidence) = dispute
                    print(f"\nDispute ID: {dispute_id}")
                    print(f"Student: {fname} {lname} ({sid})")
                    print(f"Assignment: {title} ({module})")
                    print(f"Current Grade: {grade:.1f}%" if grade is not None else "Current Grade: N/A")
                    print(f"Reason: {reason}")
                    if evidence:
                        print(f"Evidence: {evidence}")
                    print("-" * 100)

                req_id = input("\nEnter dispute ID to review: ").strip()
                if not req_id.isdigit():
                    print("Invalid dispute ID.")
                    return

                dispute_id = int(req_id)

                # Find the selected dispute
                selected = None
                for dispute in disputes:
                    if dispute[0] == dispute_id:
                        selected = dispute
                        break

                if not selected:
                    print("Dispute not found in pending queue.")
                    return

                (dispute_id, submission_id, student_id, fname, lname,
                 title, module, current_grade, reason, evidence) = selected

                print(f"\nReviewing dispute from {fname} {lname}")
                print(f"Assignment: {title}")
                print(f"Current Grade: {current_grade:.1f}%" if current_grade is not None else "Current Grade: N/A")
                print(f"Dispute Reason: {reason}")

                decision = input("\nDecision - (a)pprove / (d)eny: ").lower().strip()
                if decision not in ('a', 'd'):
                    print("Invalid decision. Please enter 'a' or 'd'.")
                    return

                comments = input("Reviewer comments: ").strip()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if decision == 'a':
                    # Optionally adjust grade
                    new_grade_str = input(f"New grade (current: {current_grade:.1f}%, press Enter to keep): ").strip() if current_grade is not None else input("New grade (press Enter to skip): ").strip()

                    updated_grade = None
                    if new_grade_str:
                        try:
                            updated_grade = float(new_grade_str)
                            if updated_grade < 0 or updated_grade > 100:
                                print("Grade must be between 0 and 100.")
                                return
                        except ValueError:
                            print("Invalid grade value.")
                            return

                    cursor.execute('''
                    UPDATE grade_disputes
                    SET status = 'approved', reviewed_by = ?, reviewed_date = ?,
                        reviewer_comments = ?, updated_grade = ?
                    WHERE id = ?
                    ''', (self.auth.current_user['id'], timestamp,
                          comments, updated_grade, dispute_id))

                    # Update the submission grade if a new grade was provided
                    if updated_grade is not None:
                        cursor.execute('''
                        UPDATE assignment_submissions
                        SET grade = ?, graded_by = ?, graded_date = ?
                        WHERE id = ?
                        ''', (updated_grade, self.auth.current_user['id'],
                              timestamp, submission_id))
                        print(f"\nDispute approved. Grade updated to {updated_grade:.1f}%.")
                    else:
                        print("\nDispute approved. Grade unchanged.")

                else:
                    cursor.execute('''
                    UPDATE grade_disputes
                    SET status = 'denied', reviewed_by = ?, reviewed_date = ?,
                        reviewer_comments = ?
                    WHERE id = ?
                    ''', (self.auth.current_user['id'], timestamp,
                          comments, dispute_id))

                    print("\nGrade dispute denied.")

                conn.commit()

            finally:
                conn.close()

        except Exception as e:
            print(f"Error reviewing grade dispute: {e}")

    def view_dispute_history(self):
        """View full dispute history with filters"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                print("\nDispute History Filters:")
                print("1. All disputes")
                print("2. Filter by status")
                print("3. Filter by student ID")
                print("4. Filter by date range")

                filter_choice = input("\nSelect filter (1-4): ").strip()

                base_query = '''
                SELECT gd.id, gd.student_id, st.first_name, st.last_name,
                       a.title, a.module_code, s.grade, gd.status,
                       gd.submitted_date, gd.reviewed_date, gd.reviewer_comments,
                       gd.updated_grade, gd.reason
                FROM grade_disputes gd
                JOIN assignment_submissions s ON gd.submission_id = s.id
                JOIN assignments a ON s.assignment_id = a.id
                JOIN students st ON gd.student_id = st.student_id
                '''

                params = []

                if filter_choice == '2':
                    print("\nStatus options: pending, approved, denied")
                    status = input("Enter status: ").strip().lower()
                    if status not in ('pending', 'approved', 'denied'):
                        print("Invalid status.")
                        return
                    base_query += " WHERE gd.status = ?"
                    params.append(status)

                elif filter_choice == '3':
                    student_id = input("Enter student ID: ").strip()
                    if not student_id:
                        print("Student ID cannot be empty.")
                        return
                    base_query += " WHERE gd.student_id = ?"
                    params.append(student_id)

                elif filter_choice == '4':
                    start_date = input("Start date (YYYY-MM-DD): ").strip()
                    end_date = input("End date (YYYY-MM-DD): ").strip()
                    try:
                        datetime.strptime(start_date, '%Y-%m-%d')
                        datetime.strptime(end_date, '%Y-%m-%d')
                    except ValueError:
                        print("Invalid date format. Use YYYY-MM-DD.")
                        return
                    base_query += " WHERE date(gd.submitted_date) BETWEEN ? AND ?"
                    params.append(start_date)
                    params.append(end_date)

                elif filter_choice != '1':
                    print("Invalid selection.")
                    return

                base_query += " ORDER BY gd.submitted_date DESC"

                cursor.execute(base_query, params)
                disputes = cursor.fetchall()

                if not disputes:
                    print("No disputes found matching the criteria.")
                    return

                print(f"\nDispute History ({len(disputes)} records):")
                print("=" * 120)
                print(f"{'ID':<6} {'Student':<25} {'Assignment':<25} {'Grade':<8} {'Status':<10} {'Submitted':<20} {'Reviewed':<20}")
                print("-" * 120)

                for dispute in disputes:
                    (dispute_id, sid, fname, lname, title, module,
                     grade, status, submitted, reviewed, comments,
                     updated_grade, reason) = dispute
                    student_name = f"{fname} {lname}"[:23]
                    title_display = title[:23] if title else "N/A"
                    grade_display = f"{grade:.1f}%" if grade is not None else "N/A"
                    reviewed_display = reviewed or "Pending"
                    print(f"{dispute_id:<6} {student_name:<25} {title_display:<25} {grade_display:<8} {status:<10} {submitted:<20} {reviewed_display:<20}")

                # Offer to view details
                detail = input("\nEnter dispute ID for full details (or press Enter to skip): ").strip()
                if detail and detail.isdigit():
                    detail_id = int(detail)
                    for dispute in disputes:
                        if dispute[0] == detail_id:
                            print(f"\nFull Details - Dispute #{detail_id}:")
                            print("-" * 60)
                            print(f"Student: {dispute[2]} {dispute[3]} ({dispute[1]})")
                            print(f"Assignment: {dispute[4]} ({dispute[5]})")
                            print(f"Original Grade: {dispute[6]:.1f}%" if dispute[6] is not None else "Original Grade: N/A")
                            print(f"Reason: {dispute[12]}")
                            print(f"Status: {dispute[7].upper()}")
                            print(f"Submitted: {dispute[8]}")
                            if dispute[9]:
                                print(f"Reviewed: {dispute[9]}")
                            if dispute[10]:
                                print(f"Reviewer Comments: {dispute[10]}")
                            if dispute[11] is not None:
                                print(f"Updated Grade: {dispute[11]:.1f}%")
                            break
                    else:
                        print("Dispute not found.")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error viewing dispute history: {e}")

    def dispute_analytics(self):
        """Display grade dispute analytics and statistics"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                print("\nGrade Dispute Analytics")
                print("=" * 60)

                # Total disputes
                cursor.execute('SELECT COUNT(*) FROM grade_disputes')
                total = cursor.fetchone()[0]
                print(f"\nTotal Disputes: {total}")

                if total == 0:
                    print("No dispute data available.")
                    return

                # Disputes by status
                cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM grade_disputes
                GROUP BY status
                ORDER BY count DESC
                ''')
                status_counts = cursor.fetchall()

                print("\nDisputes by Status:")
                for status, count in status_counts:
                    percentage = (count / total) * 100
                    print(f"  {status.capitalize():<12} {count:>5}  ({percentage:.1f}%)")

                # Average resolution time
                cursor.execute('''
                SELECT AVG(julianday(reviewed_date) - julianday(submitted_date))
                FROM grade_disputes
                WHERE reviewed_date IS NOT NULL AND submitted_date IS NOT NULL
                ''')
                avg_days = cursor.fetchone()[0]
                if avg_days is not None:
                    print(f"\nAvg Resolution Time: {avg_days:.1f} days")
                else:
                    print("\nAvg Resolution Time: N/A (no resolved disputes)")

                # Approval rate
                cursor.execute('''
                SELECT COUNT(*) FROM grade_disputes WHERE status = 'approved'
                ''')
                approved = cursor.fetchone()[0]

                cursor.execute('''
                SELECT COUNT(*) FROM grade_disputes WHERE status IN ('approved', 'denied')
                ''')
                resolved = cursor.fetchone()[0]

                if resolved > 0:
                    approval_rate = (approved / resolved) * 100
                    print(f"Approval Rate: {approval_rate:.1f}% ({approved}/{resolved} resolved)")

                # Common reasons (top 10 keywords)
                cursor.execute('''
                SELECT reason FROM grade_disputes
                WHERE reason IS NOT NULL AND reason != ''
                ''')
                reasons = cursor.fetchall()

                if reasons:
                    print("\nMost Common Dispute Reasons:")
                    word_counts = {}
                    stop_words = {'the', 'a', 'an', 'is', 'was', 'i', 'my', 'and', 'or', 'to',
                                  'of', 'in', 'for', 'on', 'it', 'that', 'this', 'with', 'not'}
                    for (reason_text,) in reasons:
                        words = reason_text.lower().split()
                        for word in words:
                            cleaned = ''.join(c for c in word if c.isalnum())
                            if cleaned and len(cleaned) > 2 and cleaned not in stop_words:
                                word_counts[cleaned] = word_counts.get(cleaned, 0) + 1

                    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                    for word, count in sorted_words:
                        print(f"  '{word}': {count} mentions")

                # Disputes by module
                cursor.execute('''
                SELECT a.module_code, COUNT(*) as count
                FROM grade_disputes gd
                JOIN assignment_submissions s ON gd.submission_id = s.id
                JOIN assignments a ON s.assignment_id = a.id
                GROUP BY a.module_code
                ORDER BY count DESC
                LIMIT 10
                ''')
                module_disputes = cursor.fetchall()

                if module_disputes:
                    print("\nDisputes by Module:")
                    for module, count in module_disputes:
                        print(f"  {module:<15} {count:>5}")

                # Monthly trend
                cursor.execute('''
                SELECT strftime('%Y-%m', submitted_date) as month, COUNT(*) as count
                FROM grade_disputes
                WHERE submitted_date IS NOT NULL
                GROUP BY month
                ORDER BY month DESC
                LIMIT 6
                ''')
                monthly = cursor.fetchall()

                if monthly:
                    print("\nMonthly Trend (recent 6 months):")
                    for month, count in monthly:
                        bar = '#' * count
                        print(f"  {month}  {count:>4}  {bar}")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error generating dispute analytics: {e}")
