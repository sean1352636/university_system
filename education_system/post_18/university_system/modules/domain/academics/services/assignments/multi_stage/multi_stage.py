from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import json
import re


class MultiStageMixin:
    """Mixin providing multi-stage assignment management and external submission handling."""

    def manage_multi_stage_assignments(self):
        """Main menu for multi-stage assignments"""
        while True:
            print("\n" + "=" * 60)
            print("MULTI-STAGE ASSIGNMENT MANAGEMENT")
            print("=" * 60)
            print("1. Create Multi-Stage Assignment")
            print("2. View Stage Progress")
            print("3. Submit Stage")
            print("4. Review Stage Submission")
            print("5. Manage External Submissions")
            print("0. Back")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self.create_multi_stage_assignment()
            elif choice == '2':
                self.view_stage_progress()
            elif choice == '3':
                self.submit_stage()
            elif choice == '4':
                self.review_stage()
            elif choice == '5':
                self.manage_external_submissions()
            elif choice == '0':
                break
            else:
                print("Invalid option. Please try again.")

    def create_multi_stage_assignment(self):
        """Create an assignment with multiple stages"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Select an existing assignment to add stages to
            cursor.execute('''
            SELECT id, title, module_code, due_date
            FROM assignments
            WHERE is_active = 1
            ORDER BY due_date DESC
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("No active assignments found. Create an assignment first.")
                conn.close()
                return

            print("\nSelect Assignment to Add Stages:")
            for i, (aid, title, module, due_date) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Due: {due_date}")

            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(assignments)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assignment_id = assignments[index][0]
            assignment_title = assignments[index][1]

            # Check if stages already exist
            cursor.execute(
                'SELECT COUNT(*) FROM assignment_stages WHERE assignment_id = ?',
                (assignment_id,)
            )
            existing_count = cursor.fetchone()[0]
            if existing_count > 0:
                print(f"\nThis assignment already has {existing_count} stage(s).")
                overwrite = input("Remove existing stages and create new ones? (y/n): ").lower()
                if overwrite != 'y':
                    conn.close()
                    return
                cursor.execute(
                    'DELETE FROM assignment_stages WHERE assignment_id = ?',
                    (assignment_id,)
                )

            # Get number of stages
            num_stages_str = input("\nNumber of stages: ").strip()
            try:
                num_stages = int(num_stages_str)
                if num_stages < 2:
                    print("Multi-stage assignments require at least 2 stages.")
                    conn.close()
                    return
                if num_stages > 20:
                    print("Maximum 20 stages allowed.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a valid number.")
                conn.close()
                return

            # Collect stage details
            stages = []
            total_weight = 0

            print(f"\nConfiguring {num_stages} stages for: {assignment_title}")
            print("-" * 60)

            for i in range(1, num_stages + 1):
                print(f"\n--- Stage {i} of {num_stages} ---")

                name = input("Stage name: ").strip()
                if not name:
                    print("Stage name cannot be empty.")
                    conn.close()
                    return

                description = input("Stage description: ").strip()

                while True:
                    weight_str = input(f"Weight % (remaining: {100 - total_weight}%): ").strip()
                    try:
                        weight = float(weight_str)
                        if weight <= 0:
                            print("Weight must be positive.")
                            continue
                        if weight > (100 - total_weight):
                            print(f"Weight exceeds remaining allocation ({100 - total_weight}%).")
                            continue
                        break
                    except ValueError:
                        print("Please enter a valid number.")

                while True:
                    deadline_str = input("Deadline (YYYY-MM-DD HH:MM): ").strip()
                    try:
                        deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M")
                        if deadline <= datetime.now():
                            print("Deadline must be in the future.")
                            continue
                        if stages and deadline <= stages[-1]['deadline']:
                            print("Deadline must be after the previous stage's deadline.")
                            continue
                        break
                    except ValueError:
                        print("Invalid date format. Use YYYY-MM-DD HH:MM")

                feedback_input = input("Feedback required before next stage? (y/n): ").lower()
                feedback_required = 1 if feedback_input == 'y' else 0

                total_weight += weight
                stages.append({
                    'name': name,
                    'description': description,
                    'weight': weight,
                    'deadline': deadline,
                    'feedback_required': feedback_required
                })

            # Validate total weight
            if abs(total_weight - 100) > 0.01:
                print(f"\nWarning: Total weight is {total_weight}%, not 100%.")
                proceed = input("Continue anyway? (y/n): ").lower()
                if proceed != 'y':
                    conn.close()
                    return

            # Insert stages
            for order, stage in enumerate(stages, 1):
                cursor.execute('''
                INSERT INTO assignment_stages
                (assignment_id, stage_order, stage_name, description, weight_percent,
                 deadline, feedback_required, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    assignment_id,
                    order,
                    stage['name'],
                    stage['description'],
                    stage['weight'],
                    stage['deadline'].strftime('%Y-%m-%d %H:%M:%S'),
                    stage['feedback_required'],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))

            conn.commit()
            conn.close()

            print("\nMulti-stage assignment created successfully!")
            print(f"Assignment: {assignment_title}")
            print(f"Stages: {num_stages}")
            print(f"Total weight: {total_weight}%")
            for i, stage in enumerate(stages, 1):
                fb = " [Feedback Required]" if stage['feedback_required'] else ""
                print(f"  Stage {i}: {stage['name']} ({stage['weight']}%) "
                      f"- Due: {stage['deadline'].strftime('%Y-%m-%d %H:%M')}{fb}")

        except Exception as e:
            print(f"Error creating multi-stage assignment: {e}")

    def view_stage_progress(self):
        """Show all students' progress through stages (tabular display)"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get assignments that have stages
            cursor.execute('''
            SELECT DISTINCT a.id, a.title, a.module_code
            FROM assignments a
            JOIN assignment_stages s ON a.id = s.assignment_id
            WHERE a.is_active = 1
            ORDER BY a.title
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("No multi-stage assignments found.")
                conn.close()
                return

            print("\nMulti-Stage Assignments:")
            for i, (aid, title, module) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module})")

            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(assignments)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assignment_id = assignments[index][0]
            assignment_title = assignments[index][1]

            # Get stages
            cursor.execute('''
            SELECT id, stage_order, stage_name, weight_percent, deadline, feedback_required
            FROM assignment_stages
            WHERE assignment_id = ?
            ORDER BY stage_order
            ''', (assignment_id,))

            stages = cursor.fetchall()

            # Get enrolled students
            cursor.execute('''
            SELECT DISTINCT st.student_id, st.first_name, st.last_name
            FROM students st
            JOIN student_modules sm ON st.student_id = sm.student_id
            JOIN assignments a ON a.module_code = sm.module_code
            WHERE a.id = ?
            ORDER BY st.last_name, st.first_name
            ''', (assignment_id,))

            students = cursor.fetchall()

            if not students:
                print("No students enrolled for this assignment.")
                conn.close()
                return

            # Get all stage submissions
            cursor.execute('''
            SELECT ss.student_id, ss.stage_id, ss.status
            FROM stage_submissions ss
            WHERE ss.stage_id IN (
                SELECT id FROM assignment_stages WHERE assignment_id = ?
            )
            ''', (assignment_id,))

            submissions = {}
            for student_id, stage_id, status in cursor.fetchall():
                key = (student_id, stage_id)
                submissions[key] = status

            conn.close()

            # Display progress table
            print(f"\n{'=' * 80}")
            print(f"Stage Progress: {assignment_title}")
            print(f"{'=' * 80}")

            # Header row
            stage_names = [s[2][:10] for s in stages]
            header = f"{'Student':<25}"
            for name in stage_names:
                header += f" | {name:<12}"
            print(header)
            print("-" * len(header))

            # Student rows
            for student_id, first_name, last_name in students:
                row = f"{last_name}, {first_name}"[:25].ljust(25)
                for stage in stages:
                    stage_id = stage[0]
                    status = submissions.get((student_id, stage_id), 'not started')
                    status_display = {
                        'submitted': 'Submitted',
                        'approved': 'Approved',
                        'revision': 'Revision',
                        'not started': '-',
                    }.get(status, status[:10])
                    row += f" | {status_display:<12}"
                print(row)

            # Summary
            print("-" * len(header))
            print("\nStage Details:")
            for stage in stages:
                fb = " [Feedback Required]" if stage[5] else ""
                print(f"  Stage {stage[1]}: {stage[2]} ({stage[3]}%) "
                      f"- Due: {stage[4]}{fb}")

        except Exception as e:
            print(f"Error viewing stage progress: {e}")

    def submit_stage(self):
        """Student submits a specific stage"""
        if not self._check_permission('submit_assignment'):
            return

        try:
            student_id = self._get_student_id()
            if not student_id:
                print("No student ID associated with your account.")
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get assignments with stages that the student is enrolled in
            cursor.execute('''
            SELECT DISTINCT a.id, a.title, a.module_code
            FROM assignments a
            JOIN assignment_stages s ON a.id = s.assignment_id
            JOIN student_modules sm ON a.module_code = sm.module_code
            WHERE sm.student_id = ? AND a.is_active = 1
            ORDER BY a.title
            ''', (student_id,))

            assignments = cursor.fetchall()

            if not assignments:
                print("No multi-stage assignments found for your modules.")
                conn.close()
                return

            print("\nYour Multi-Stage Assignments:")
            for i, (aid, title, module) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module})")

            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(assignments)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assignment_id = assignments[index][0]

            # Get stages for this assignment
            cursor.execute('''
            SELECT id, stage_order, stage_name, weight_percent, deadline, feedback_required
            FROM assignment_stages
            WHERE assignment_id = ?
            ORDER BY stage_order
            ''', (assignment_id,))

            stages = cursor.fetchall()

            # Show stages with current status
            print("\nStages:")
            for stage in stages:
                stage_id, order, name, weight, deadline, fb_req = stage

                cursor.execute('''
                SELECT status FROM stage_submissions
                WHERE stage_id = ? AND student_id = ?
                ORDER BY submitted_at DESC LIMIT 1
                ''', (stage_id, student_id))

                sub = cursor.fetchone()
                status = sub[0] if sub else 'not started'
                fb_label = " [Feedback Required]" if fb_req else ""
                print(f"  {order}. {name} ({weight}%) - Due: {deadline} "
                      f"- Status: {status}{fb_label}")

            stage_choice = input("\nSelect stage number to submit: ").strip()
            try:
                stage_order = int(stage_choice)
            except ValueError:
                print("Please enter a valid number.")
                conn.close()
                return

            # Find the selected stage
            selected_stage = None
            for stage in stages:
                if stage[1] == stage_order:
                    selected_stage = stage
                    break

            if not selected_stage:
                print("Invalid stage number.")
                conn.close()
                return

            stage_id, order, name, weight, deadline, fb_req = selected_stage

            # Enforce progression: check previous stage
            if order > 1:
                prev_stage = None
                for stage in stages:
                    if stage[1] == order - 1:
                        prev_stage = stage
                        break

                if prev_stage:
                    prev_stage_id = prev_stage[0]
                    prev_fb_required = prev_stage[5]

                    cursor.execute('''
                    SELECT status FROM stage_submissions
                    WHERE stage_id = ? AND student_id = ?
                    ORDER BY submitted_at DESC LIMIT 1
                    ''', (prev_stage_id, student_id))

                    prev_sub = cursor.fetchone()

                    if not prev_sub:
                        print(f"You must submit stage {order - 1} "
                              f"({prev_stage[2]}) before this stage.")
                        conn.close()
                        return

                    if prev_fb_required and prev_sub[0] != 'approved':
                        print(f"Stage {order - 1} ({prev_stage[2]}) requires "
                              f"instructor feedback/approval before you can proceed.")
                        print(f"Current status: {prev_sub[0]}")
                        conn.close()
                        return

            # Check if already submitted and approved
            cursor.execute('''
            SELECT status FROM stage_submissions
            WHERE stage_id = ? AND student_id = ?
            ORDER BY submitted_at DESC LIMIT 1
            ''', (stage_id, student_id))

            existing = cursor.fetchone()
            if existing and existing[0] == 'approved':
                print("This stage has already been approved.")
                conn.close()
                return

            # Check deadline
            stage_deadline = datetime.strptime(deadline, '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            if now > stage_deadline:
                print(f"Warning: This stage's deadline has passed ({deadline}).")
                proceed = input("Submit anyway? (y/n): ").lower()
                if proceed != 'y':
                    conn.close()
                    return

            # Get submission content
            print(f"\nSubmitting: Stage {order} - {name}")
            content = input("Enter your submission text (or file path): ").strip()

            if not content:
                print("Submission cannot be empty.")
                conn.close()
                return

            comments = input("Additional comments (optional): ").strip()

            # Insert or update submission
            cursor.execute('''
            INSERT INTO stage_submissions
            (stage_id, student_id, content, comments, status, submitted_at)
            VALUES (?, ?, ?, ?, 'submitted', ?)
            ''', (
                stage_id,
                student_id,
                content,
                comments,
                now.strftime('%Y-%m-%d %H:%M:%S')
            ))

            conn.commit()
            conn.close()

            print(f"\nStage {order} ({name}) submitted successfully!")
            print(f"Submitted at: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            print(f"Error submitting stage: {e}")

    def review_stage(self):
        """Instructor reviews a stage submission"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get pending stage submissions
            cursor.execute('''
            SELECT ss.id, ss.stage_id, ss.student_id, ss.content, ss.comments,
                   ss.submitted_at, st.first_name, st.last_name,
                   ags.stage_name, ags.stage_order, a.title
            FROM stage_submissions ss
            JOIN assignment_stages ags ON ss.stage_id = ags.id
            JOIN assignments a ON ags.assignment_id = a.id
            JOIN students st ON ss.student_id = st.student_id
            WHERE ss.status = 'submitted'
            ORDER BY ss.submitted_at
            ''')

            submissions = cursor.fetchall()

            if not submissions:
                print("No pending stage submissions to review.")
                conn.close()
                return

            print("\nPending Stage Submissions:")
            print("=" * 80)
            for i, sub in enumerate(submissions, 1):
                (sub_id, stage_id, student_id, content, comments,
                 submitted_at, first, last, stage_name, stage_order, title) = sub
                print(f"\n{i}. Submission #{sub_id}")
                print(f"   Assignment: {title}")
                print(f"   Stage {stage_order}: {stage_name}")
                print(f"   Student: {first} {last} ({student_id})")
                print(f"   Submitted: {submitted_at}")
                print(f"   Content: {content[:100]}{'...' if len(content) > 100 else ''}")
                if comments:
                    print(f"   Comments: {comments}")
            print("-" * 80)

            choice = input("\nSelect submission number to review: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(submissions)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            selected = submissions[index]
            sub_id = selected[0]
            content = selected[3]

            # Show full submission
            print(f"\n{'=' * 60}")
            print(f"REVIEWING SUBMISSION #{sub_id}")
            print(f"{'=' * 60}")
            print(f"Assignment: {selected[10]}")
            print(f"Stage {selected[9]}: {selected[8]}")
            print(f"Student: {selected[6]} {selected[7]} ({selected[2]})")
            print(f"Submitted: {selected[5]}")
            print("\nContent:")
            print("-" * 40)
            print(content)
            print("-" * 40)
            if selected[4]:
                print(f"Student Comments: {selected[4]}")

            # Decision
            print("\nDecision:")
            print("1. Approve")
            print("2. Request Revision")

            decision = input("\nSelect option: ").strip()

            if decision not in ('1', '2'):
                print("Invalid option.")
                conn.close()
                return

            feedback = input("Feedback for student: ").strip()
            if not feedback:
                print("Feedback cannot be empty.")
                conn.close()
                return

            score_str = input("Score (0-100, optional, press Enter to skip): ").strip()
            score = None
            if score_str:
                try:
                    score = float(score_str)
                    if not (0 <= score <= 100):
                        print("Score must be between 0 and 100.")
                        conn.close()
                        return
                except ValueError:
                    print("Invalid score.")
                    conn.close()
                    return

            new_status = 'approved' if decision == '1' else 'revision'
            reviewer_id = self.auth.current_user['id']
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            UPDATE stage_submissions
            SET status = ?, feedback = ?, score = ?, reviewed_by = ?, reviewed_at = ?
            WHERE id = ?
            ''', (new_status, feedback, score, reviewer_id, now, sub_id))

            conn.commit()
            conn.close()

            status_label = "Approved" if decision == '1' else "Revision Requested"
            print(f"\nSubmission #{sub_id}: {status_label}")
            print("Feedback provided to student.")
            if score is not None:
                print(f"Score: {score}/100")

        except Exception as e:
            print(f"Error reviewing stage submission: {e}")

    def manage_external_submissions(self):
        """Menu for external tool submissions"""
        while True:
            print("\n" + "=" * 60)
            print("EXTERNAL SUBMISSIONS MANAGEMENT")
            print("=" * 60)
            print("1. Submit External Link")
            print("2. View External Submissions")
            print("3. Validate External Links")
            print("0. Back")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self.submit_external_link()
            elif choice == '2':
                self.view_external_submissions()
            elif choice == '3':
                self.validate_external_links()
            elif choice == '0':
                break
            else:
                print("Invalid option. Please try again.")

    def submit_external_link(self):
        """Student submits an external URL"""
        if not self._check_permission('submit_assignment'):
            return

        try:
            student_id = self._get_student_id()
            if not student_id:
                print("No student ID associated with your account.")
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get assignments the student is enrolled in
            cursor.execute('''
            SELECT a.id, a.title, a.module_code, a.due_date
            FROM assignments a
            JOIN student_modules sm ON a.module_code = sm.module_code
            WHERE sm.student_id = ? AND a.is_active = 1
            ORDER BY a.due_date
            ''', (student_id,))

            assignments = cursor.fetchall()

            if not assignments:
                print("No active assignments found for your modules.")
                conn.close()
                return

            print("\nYour Assignments:")
            for i, (aid, title, module, due_date) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Due: {due_date}")

            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(assignments)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assignment_id = assignments[index][0]

            # External tool type
            print("\nExternal Tool Type:")
            print("1. GitHub")
            print("2. Google Docs")
            print("3. Figma")
            print("4. Other")

            type_choice = input("\nSelect type: ").strip()
            tool_types = {'1': 'github', '2': 'google_docs', '3': 'figma', '4': 'other'}
            tool_type = tool_types.get(type_choice)

            if not tool_type:
                print("Invalid selection.")
                conn.close()
                return

            # Get URL
            url = input("Enter the URL: ").strip()

            if not url:
                print("URL cannot be empty.")
                conn.close()
                return

            # Basic URL validation
            url_pattern = re.compile(
                r'^https?://'
                r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*'
                r'[a-zA-Z]{2,}'
                r'(?:/[^\s]*)?$'
            )

            if not url_pattern.match(url):
                print("Invalid URL format. Must start with http:// or https://")
                conn.close()
                return

            # Type-specific validation
            valid = True
            validation_message = ""

            if tool_type == 'github':
                if 'github.com' not in url and 'github.io' not in url:
                    valid = False
                    validation_message = "URL does not appear to be a GitHub link."
            elif tool_type == 'google_docs':
                if 'docs.google.com' not in url and 'drive.google.com' not in url:
                    valid = False
                    validation_message = "URL does not appear to be a Google Docs/Drive link."
            elif tool_type == 'figma':
                if 'figma.com' not in url:
                    valid = False
                    validation_message = "URL does not appear to be a Figma link."

            if not valid:
                print(f"Warning: {validation_message}")
                proceed = input("Submit anyway? (y/n): ").lower()
                if proceed != 'y':
                    conn.close()
                    return

            description = input("Description (optional): ").strip()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO external_submissions
            (assignment_id, student_id, tool_type, url, description,
             is_validated, submitted_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            ''', (assignment_id, student_id, tool_type, url, description, now))

            conn.commit()
            submission_id = cursor.lastrowid
            conn.close()

            print("\nExternal submission recorded successfully!")
            print(f"Submission ID: {submission_id}")
            print(f"Type: {tool_type}")
            print(f"URL: {url}")
            print("Status: Pending validation")

        except Exception as e:
            print(f"Error submitting external link: {e}")

    def view_external_submissions(self):
        """View all external submissions for an assignment"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get assignments with external submissions
            cursor.execute('''
            SELECT DISTINCT a.id, a.title, a.module_code
            FROM assignments a
            JOIN external_submissions es ON a.id = es.assignment_id
            WHERE a.is_active = 1
            ORDER BY a.title
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("No assignments with external submissions found.")
                conn.close()
                return

            print("\nAssignments with External Submissions:")
            for i, (aid, title, module) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module})")

            choice = input("\nSelect assignment number (or 'all' for all): ").strip()

            if choice.lower() == 'all':
                assignment_filter = None
            else:
                try:
                    index = int(choice) - 1
                    if not (0 <= index < len(assignments)):
                        print("Invalid selection.")
                        conn.close()
                        return
                    assignment_filter = assignments[index][0]
                except ValueError:
                    print("Please enter a number or 'all'.")
                    conn.close()
                    return

            # Fetch external submissions
            if assignment_filter:
                cursor.execute('''
                SELECT es.id, es.assignment_id, es.student_id, es.tool_type, es.url,
                       es.description, es.is_validated, es.submitted_at,
                       st.first_name, st.last_name, a.title
                FROM external_submissions es
                JOIN students st ON es.student_id = st.student_id
                JOIN assignments a ON es.assignment_id = a.id
                WHERE es.assignment_id = ?
                ORDER BY es.submitted_at DESC
                ''', (assignment_filter,))
            else:
                cursor.execute('''
                SELECT es.id, es.assignment_id, es.student_id, es.tool_type, es.url,
                       es.description, es.is_validated, es.submitted_at,
                       st.first_name, st.last_name, a.title
                FROM external_submissions es
                JOIN students st ON es.student_id = st.student_id
                JOIN assignments a ON es.assignment_id = a.id
                ORDER BY es.submitted_at DESC
                ''')

            submissions = cursor.fetchall()
            conn.close()

            if not submissions:
                print("No external submissions found.")
                return

            print(f"\n{'=' * 90}")
            print("EXTERNAL SUBMISSIONS")
            print(f"{'=' * 90}")
            print(f"{'ID':<6}{'Student':<25}{'Type':<14}{'Validated':<12}{'Assignment':<20}{'URL'}")
            print("-" * 90)

            for sub in submissions:
                (sub_id, aid, sid, tool_type, url, desc, validated,
                 submitted_at, first, last, title) = sub
                student_name = f"{first} {last}"[:24]
                validated_str = "Yes" if validated else "No"
                title_short = title[:19]
                print(f"{sub_id:<6}{student_name:<25}{tool_type:<14}"
                      f"{validated_str:<12}{title_short:<20}{url}")

            print(f"\nTotal: {len(submissions)} submission(s)")

        except Exception as e:
            print(f"Error viewing external submissions: {e}")

    def validate_external_links(self):
        """Batch validate all unvalidated external links"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT es.id, es.tool_type, es.url, es.student_id,
                   st.first_name, st.last_name, a.title
            FROM external_submissions es
            JOIN students st ON es.student_id = st.student_id
            JOIN assignments a ON es.assignment_id = a.id
            WHERE es.is_validated = 0
            ORDER BY es.submitted_at
            ''')

            unvalidated = cursor.fetchall()

            if not unvalidated:
                print("No unvalidated external submissions found.")
                conn.close()
                return

            print(f"\nFound {len(unvalidated)} unvalidated submission(s).")
            print("=" * 80)

            validated_count = 0
            failed_count = 0

            url_pattern = re.compile(
                r'^https?://'
                r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*'
                r'[a-zA-Z]{2,}'
                r'(?:/[^\s]*)?$'
            )

            domain_patterns = {
                'github': re.compile(r'github\.com|github\.io'),
                'google_docs': re.compile(r'docs\.google\.com|drive\.google\.com'),
                'figma': re.compile(r'figma\.com'),
            }

            for sub in unvalidated:
                sub_id, tool_type, url, student_id, first, last, title = sub

                is_valid = True
                issues = []

                # Check URL format
                if not url_pattern.match(url):
                    is_valid = False
                    issues.append("Invalid URL format")

                # Check domain matches tool type
                if tool_type in domain_patterns:
                    if not domain_patterns[tool_type].search(url):
                        is_valid = False
                        issues.append(f"URL domain does not match tool type '{tool_type}'")

                # Check for common issues
                if len(url) > 2048:
                    is_valid = False
                    issues.append("URL exceeds maximum length")

                if ' ' in url:
                    is_valid = False
                    issues.append("URL contains spaces")

                status_str = "VALID" if is_valid else "INVALID"
                issue_str = "; ".join(issues) if issues else "OK"

                print(f"\n  [{status_str}] Submission #{sub_id}")
                print(f"    Student: {first} {last}")
                print(f"    Type: {tool_type} | URL: {url}")
                print(f"    Result: {issue_str}")

                if is_valid:
                    cursor.execute('''
                    UPDATE external_submissions
                    SET is_validated = 1, validated_at = ?
                    WHERE id = ?
                    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sub_id))
                    validated_count += 1
                else:
                    cursor.execute('''
                    UPDATE external_submissions
                    SET is_validated = 0, validation_notes = ?
                    WHERE id = ?
                    ''', (issue_str, sub_id))
                    failed_count += 1

            conn.commit()
            conn.close()

            print(f"\n{'=' * 80}")
            print("Validation complete:")
            print(f"  Validated: {validated_count}")
            print(f"  Failed: {failed_count}")
            print(f"  Total: {len(unvalidated)}")

        except Exception as e:
            print(f"Error validating external links: {e}")
