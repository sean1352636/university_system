from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import json


class LatePolicyMixin:
    """Mixin providing late submission policy management, penalty calculation, and late passes."""

    def manage_late_policies(self):
        """Main menu for managing late submission policies"""
        if not self._check_permission('manage_assignments'):
            return

        while True:
            print("\n=== Late Policy Management ===")
            print("1. List late policies")
            print("2. Create late policy")
            print("3. Edit late policy")
            print("4. Delete late policy")
            print("5. Apply policy to assignment")
            print("6. Apply policy to module")
            print("7. Create from template")
            print("8. Back")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self._list_late_policies()
            elif choice == '2':
                self.create_late_policy()
            elif choice == '3':
                self.edit_late_policy()
            elif choice == '4':
                self._delete_late_policy()
            elif choice == '5':
                self.apply_policy_to_assignment()
            elif choice == '6':
                self.apply_policy_to_module()
            elif choice == '7':
                self.use_policy_template()
            elif choice == '8':
                break
            else:
                print("Invalid option.")

    def _list_late_policies(self):
        """Display all late policies"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, name, description, penalty_type, penalty_per_day,
                   max_late_days, grace_period_hours, min_grade_floor
            FROM late_policies
            ORDER BY name
            ''')

            policies = cursor.fetchall()
            conn.close()

            if not policies:
                print("\nNo late policies found.")
                return

            print("\nLate Policies:")
            print("=" * 90)
            for p in policies:
                pid, name, desc, ptype, ppd, max_days, grace, floor = p
                print(f"\nID: {pid}")
                print(f"  Name: {name}")
                print(f"  Description: {desc}")
                print(f"  Penalty type: {ptype}")
                print(f"  Penalty per day: {ppd}")
                print(f"  Max late days: {max_days}")
                print(f"  Grace period: {grace} hours")
                print(f"  Min grade floor: {floor}")
                print("-" * 90)

        except Exception as e:
            print(f"Error listing late policies: {e}")

    def create_late_policy(self):
        """Create a new late submission policy"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\n=== Create Late Policy ===")

            name = input("Policy name: ").strip()
            if not name:
                print("Name cannot be empty.")
                return

            description = input("Description: ").strip()

            print("\nPenalty types:")
            print("1. percentage - Deduct a percentage per day late")
            print("2. fixed - Deduct fixed points per day late")
            print("3. none - No penalty (tracking only)")

            ptype_choice = input("Select penalty type (1/2/3): ").strip()
            penalty_type_map = {'1': 'percentage', '2': 'fixed', '3': 'none'}
            penalty_type = penalty_type_map.get(ptype_choice)
            if not penalty_type:
                print("Invalid penalty type.")
                return

            penalty_per_day = 0.0
            if penalty_type != 'none':
                try:
                    penalty_per_day = float(input("Penalty per day late: ").strip())
                    if penalty_per_day < 0:
                        print("Penalty must be non-negative.")
                        return
                except ValueError:
                    print("Invalid number.")
                    return

            try:
                max_late_days = int(input("Maximum late days allowed (0 = unlimited): ").strip())
                if max_late_days < 0:
                    print("Max late days must be non-negative.")
                    return
            except ValueError:
                print("Invalid number.")
                return

            try:
                grace_period_hours = float(input("Grace period hours (0 = none): ").strip())
                if grace_period_hours < 0:
                    print("Grace period must be non-negative.")
                    return
            except ValueError:
                print("Invalid number.")
                return

            try:
                min_grade_floor = float(input("Minimum grade floor (0 = no floor): ").strip())
                if min_grade_floor < 0:
                    print("Grade floor must be non-negative.")
                    return
            except ValueError:
                print("Invalid number.")
                return

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO late_policies
            (name, description, penalty_type, penalty_per_day, max_late_days,
             grace_period_hours, min_grade_floor, created_by, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, penalty_type, penalty_per_day, max_late_days,
                  grace_period_hours, min_grade_floor,
                  self.auth.current_user['id'],
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            policy_id = cursor.lastrowid
            conn.close()

            print(f"\nLate policy '{name}' created successfully (ID: {policy_id}).")

        except Exception as e:
            print(f"Error creating late policy: {e}")

    def edit_late_policy(self):
        """Edit an existing late policy"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, name, description, penalty_type, penalty_per_day,
                   max_late_days, grace_period_hours, min_grade_floor
            FROM late_policies
            ORDER BY name
            ''')

            policies = cursor.fetchall()

            if not policies:
                print("\nNo late policies found.")
                conn.close()
                return

            print("\nExisting Policies:")
            for i, (pid, name, desc, ptype, ppd, max_d, grace, floor) in enumerate(policies, 1):
                print(f"{i}. {name} (ID: {pid}) - {ptype}, {ppd}/day")

            choice = input("\nSelect policy number to edit: ").strip()
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(policies):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            policy = policies[index]
            pid, cur_name, cur_desc, cur_ptype, cur_ppd, cur_max, cur_grace, cur_floor = policy

            print(f"\nEditing policy: {cur_name}")
            print("Press Enter to keep current value.\n")

            name = input(f"Name [{cur_name}]: ").strip() or cur_name
            description = input(f"Description [{cur_desc}]: ").strip() or cur_desc

            print(f"\nCurrent penalty type: {cur_ptype}")
            print("1. percentage  2. fixed  3. none  (Enter to keep)")
            ptype_input = input("Penalty type: ").strip()
            if ptype_input:
                ptype_map = {'1': 'percentage', '2': 'fixed', '3': 'none'}
                penalty_type = ptype_map.get(ptype_input)
                if not penalty_type:
                    print("Invalid penalty type. Keeping current.")
                    penalty_type = cur_ptype
            else:
                penalty_type = cur_ptype

            ppd_input = input(f"Penalty per day [{cur_ppd}]: ").strip()
            if ppd_input:
                try:
                    penalty_per_day = float(ppd_input)
                except ValueError:
                    print("Invalid number. Keeping current.")
                    penalty_per_day = cur_ppd
            else:
                penalty_per_day = cur_ppd

            max_input = input(f"Max late days [{cur_max}]: ").strip()
            if max_input:
                try:
                    max_late_days = int(max_input)
                except ValueError:
                    print("Invalid number. Keeping current.")
                    max_late_days = cur_max
            else:
                max_late_days = cur_max

            grace_input = input(f"Grace period hours [{cur_grace}]: ").strip()
            if grace_input:
                try:
                    grace_period_hours = float(grace_input)
                except ValueError:
                    print("Invalid number. Keeping current.")
                    grace_period_hours = cur_grace
            else:
                grace_period_hours = cur_grace

            floor_input = input(f"Min grade floor [{cur_floor}]: ").strip()
            if floor_input:
                try:
                    min_grade_floor = float(floor_input)
                except ValueError:
                    print("Invalid number. Keeping current.")
                    min_grade_floor = cur_floor
            else:
                min_grade_floor = cur_floor

            cursor.execute('''
            UPDATE late_policies
            SET name = ?, description = ?, penalty_type = ?, penalty_per_day = ?,
                max_late_days = ?, grace_period_hours = ?, min_grade_floor = ?
            WHERE id = ?
            ''', (name, description, penalty_type, penalty_per_day,
                  max_late_days, grace_period_hours, min_grade_floor, pid))

            conn.commit()
            conn.close()

            print(f"\nPolicy '{name}' updated successfully.")

        except Exception as e:
            print(f"Error editing late policy: {e}")

    def _delete_late_policy(self):
        """Delete a late policy"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT id, name FROM late_policies ORDER BY name')
            policies = cursor.fetchall()

            if not policies:
                print("\nNo late policies found.")
                conn.close()
                return

            print("\nLate Policies:")
            for i, (pid, name) in enumerate(policies, 1):
                print(f"{i}. {name} (ID: {pid})")

            choice = input("\nSelect policy number to delete: ").strip()
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(policies):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            pid, name = policies[index]

            cursor.execute(
                'SELECT COUNT(*) FROM assignment_late_policies WHERE policy_id = ?', (pid,))
            linked = cursor.fetchone()[0]

            if linked > 0:
                print(f"\nWarning: This policy is linked to {linked} assignment(s).")
                confirm = input("Delete anyway? (yes/no): ").strip().lower()
                if confirm != 'yes':
                    print("Deletion cancelled.")
                    conn.close()
                    return
                cursor.execute(
                    'DELETE FROM assignment_late_policies WHERE policy_id = ?', (pid,))

            cursor.execute('DELETE FROM late_policies WHERE id = ?', (pid,))
            conn.commit()
            conn.close()

            print(f"\nPolicy '{name}' deleted successfully.")

        except Exception as e:
            print(f"Error deleting late policy: {e}")

    def apply_policy_to_assignment(self):
        """Link a late policy to a specific assignment"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT id, name, penalty_type, penalty_per_day FROM late_policies ORDER BY name')
            policies = cursor.fetchall()

            if not policies:
                print("\nNo late policies available. Create one first.")
                conn.close()
                return

            print("\nAvailable Late Policies:")
            for i, (pid, name, ptype, ppd) in enumerate(policies, 1):
                print(f"{i}. {name} ({ptype}, {ppd}/day)")

            policy_choice = input("\nSelect policy number: ").strip()
            try:
                p_index = int(policy_choice) - 1
                if p_index < 0 or p_index >= len(policies):
                    print("Invalid selection.")
                    conn.close()
                    return
                policy_id = policies[p_index][0]
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            cursor.execute('''
            SELECT id, title, module_code, due_date
            FROM assignments
            WHERE is_active = 1
            ORDER BY due_date DESC
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("\nNo active assignments found.")
                conn.close()
                return

            print("\nActive Assignments:")
            for i, (aid, title, module, due) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Due: {due}")

            assign_choice = input("\nSelect assignment number: ").strip()
            try:
                a_index = int(assign_choice) - 1
                if a_index < 0 or a_index >= len(assignments):
                    print("Invalid selection.")
                    conn.close()
                    return
                assignment_id = assignments[a_index][0]
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            cursor.execute('''
            SELECT id FROM assignment_late_policies
            WHERE assignment_id = ?
            ''', (assignment_id,))

            existing = cursor.fetchone()
            if existing:
                confirm = input("This assignment already has a late policy. Replace it? (y/n): ").strip().lower()
                if confirm != 'y':
                    print("Cancelled.")
                    conn.close()
                    return
                cursor.execute('''
                UPDATE assignment_late_policies
                SET policy_id = ?, applied_date = ?, applied_by = ?
                WHERE assignment_id = ?
                ''', (policy_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      self.auth.current_user['id'], assignment_id))
            else:
                cursor.execute('''
                INSERT INTO assignment_late_policies
                (assignment_id, policy_id, applied_date, applied_by)
                VALUES (?, ?, ?, ?)
                ''', (assignment_id, policy_id,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      self.auth.current_user['id']))

            conn.commit()
            conn.close()

            print(f"\nPolicy '{policies[p_index][1]}' applied to '{assignments[a_index][1]}'.")

        except Exception as e:
            print(f"Error applying policy to assignment: {e}")

    def apply_policy_to_module(self):
        """Apply a late policy to all assignments in a module"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT id, name, penalty_type, penalty_per_day FROM late_policies ORDER BY name')
            policies = cursor.fetchall()

            if not policies:
                print("\nNo late policies available. Create one first.")
                conn.close()
                return

            print("\nAvailable Late Policies:")
            for i, (pid, name, ptype, ppd) in enumerate(policies, 1):
                print(f"{i}. {name} ({ptype}, {ppd}/day)")

            policy_choice = input("\nSelect policy number: ").strip()
            try:
                p_index = int(policy_choice) - 1
                if p_index < 0 or p_index >= len(policies):
                    print("Invalid selection.")
                    conn.close()
                    return
                policy_id = policies[p_index][0]
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            module_code = input("Enter module code: ").strip()
            if not module_code:
                print("Module code cannot be empty.")
                conn.close()
                return

            cursor.execute('''
            SELECT id, title, due_date
            FROM assignments
            WHERE module_code = ? AND is_active = 1
            ORDER BY due_date
            ''', (module_code,))

            assignments = cursor.fetchall()

            if not assignments:
                print(f"\nNo active assignments found for module '{module_code}'.")
                conn.close()
                return

            print(f"\nFound {len(assignments)} assignment(s) in module '{module_code}':")
            for aid, title, due in assignments:
                print(f"  - {title} (Due: {due})")

            confirm = input(f"\nApply policy '{policies[p_index][1]}' to all? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Cancelled.")
                conn.close()
                return

            applied = 0
            updated = 0
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user_id = self.auth.current_user['id']

            for aid, title, due in assignments:
                cursor.execute(
                    'SELECT id FROM assignment_late_policies WHERE assignment_id = ?', (aid,))
                existing = cursor.fetchone()

                if existing:
                    cursor.execute('''
                    UPDATE assignment_late_policies
                    SET policy_id = ?, applied_date = ?, applied_by = ?
                    WHERE assignment_id = ?
                    ''', (policy_id, now, user_id, aid))
                    updated += 1
                else:
                    cursor.execute('''
                    INSERT INTO assignment_late_policies
                    (assignment_id, policy_id, applied_date, applied_by)
                    VALUES (?, ?, ?, ?)
                    ''', (aid, policy_id, now, user_id))
                    applied += 1

            conn.commit()
            conn.close()

            print(f"\nPolicy applied: {applied} new, {updated} updated.")

        except Exception as e:
            print(f"Error applying policy to module: {e}")

    def calculate_late_penalty(self):
        """Calculate the penalty that would apply to a specific submission"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            assignment_id_str = input("Enter assignment ID: ").strip()
            if not assignment_id_str.isdigit():
                print("Invalid assignment ID.")
                conn.close()
                return
            assignment_id = int(assignment_id_str)

            student_id = input("Enter student ID: ").strip()
            if not student_id:
                print("Student ID cannot be empty.")
                conn.close()
                return

            cursor.execute('''
            SELECT a.due_date, a.title, a.max_grade
            FROM assignments a
            WHERE a.id = ?
            ''', (assignment_id,))

            assignment = cursor.fetchone()
            if not assignment:
                print("Assignment not found.")
                conn.close()
                return

            due_date_str, title, max_grade = assignment
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            SELECT lp.id, lp.name, lp.penalty_type, lp.penalty_per_day,
                   lp.max_late_days, lp.grace_period_hours, lp.min_grade_floor
            FROM late_policies lp
            JOIN assignment_late_policies alp ON lp.id = alp.policy_id
            WHERE alp.assignment_id = ?
            ''', (assignment_id,))

            policy = cursor.fetchone()
            if not policy:
                print(f"\nNo late policy assigned to '{title}'.")
                conn.close()
                return

            pol_id, pol_name, penalty_type, ppd, max_late, grace_hours, grade_floor = policy

            cursor.execute('''
            SELECT submission_date FROM assignment_submissions
            WHERE assignment_id = ? AND student_id = ?
            ORDER BY submission_date DESC LIMIT 1
            ''', (assignment_id, student_id))

            submission = cursor.fetchone()
            if not submission:
                print(f"\nNo submission found for student '{student_id}' on '{title}'.")
                conn.close()
                return

            submit_date = datetime.strptime(submission[0], '%Y-%m-%d %H:%M:%S')

            # Check for late pass
            cursor.execute('''
            SELECT extra_days FROM late_passes
            WHERE student_id = ? AND assignment_id = ? AND status = 'active'
            ''', (student_id, assignment_id))

            late_pass = cursor.fetchone()
            extra_days = late_pass[0] if late_pass else 0

            effective_due = due_date + timedelta(days=extra_days)

            conn.close()

            # Calculate lateness
            delta = submit_date - effective_due
            hours_late = delta.total_seconds() / 3600

            print(f"\n=== Penalty Calculation for '{title}' ===")
            print(f"Policy: {pol_name}")
            print(f"Due date: {due_date_str}")
            if extra_days > 0:
                print(f"Late pass: +{extra_days} day(s)")
                print(f"Effective due: {effective_due.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Submitted: {submission[0]}")

            if hours_late <= 0:
                print("\nSubmission is ON TIME. No penalty.")
                return

            if grace_hours > 0 and hours_late <= grace_hours:
                print(f"\nSubmission is within grace period ({grace_hours}h). No penalty.")
                return

            days_late = int((hours_late - grace_hours) / 24) + 1 if grace_hours > 0 else int(hours_late / 24) + 1

            if max_late > 0 and days_late > max_late:
                print(f"\nSubmission is {days_late} day(s) late (max allowed: {max_late}).")
                print("Submission REJECTED - exceeds maximum late days.")
                return

            if penalty_type == 'none':
                print(f"\nSubmission is {days_late} day(s) late. No penalty (tracking only).")
                return

            if penalty_type == 'percentage':
                penalty = ppd * days_late
                penalty = min(penalty, 100.0)
                if max_grade:
                    deduction = max_grade * (penalty / 100)
                    adjusted = max(max_grade - deduction, grade_floor)
                    print(f"\nDays late: {days_late}")
                    print(f"Penalty: {penalty}% ({ppd}% x {days_late} days)")
                    print(f"Max grade after penalty: {adjusted:.1f} / {max_grade}")
                else:
                    print(f"\nDays late: {days_late}")
                    print(f"Penalty: {penalty}% deduction")
            elif penalty_type == 'fixed':
                penalty = ppd * days_late
                if max_grade:
                    adjusted = max(max_grade - penalty, grade_floor)
                    print(f"\nDays late: {days_late}")
                    print(f"Penalty: {penalty} points ({ppd} x {days_late} days)")
                    print(f"Max grade after penalty: {adjusted:.1f} / {max_grade}")
                else:
                    print(f"\nDays late: {days_late}")
                    print(f"Penalty: {penalty} points deduction")

            if grade_floor > 0:
                print(f"Grade floor: {grade_floor}")

        except Exception as e:
            print(f"Error calculating late penalty: {e}")

    def apply_late_penalties_batch(self):
        """Batch apply penalties to all late submissions for an assignment"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT a.id, a.title, a.module_code, a.due_date, a.max_grade
            FROM assignments a
            JOIN assignment_late_policies alp ON a.id = alp.assignment_id
            WHERE a.is_active = 1
            ORDER BY a.due_date DESC
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("\nNo assignments with late policies found.")
                conn.close()
                return

            print("\nAssignments with Late Policies:")
            for i, (aid, title, module, due, max_g) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Due: {due}")

            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(assignments):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assignment_id, title, module, due_date_str, max_grade = assignments[index]
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            SELECT lp.penalty_type, lp.penalty_per_day, lp.max_late_days,
                   lp.grace_period_hours, lp.min_grade_floor
            FROM late_policies lp
            JOIN assignment_late_policies alp ON lp.id = alp.policy_id
            WHERE alp.assignment_id = ?
            ''', (assignment_id,))

            policy = cursor.fetchone()
            if not policy:
                print("Policy not found.")
                conn.close()
                return

            penalty_type, ppd, max_late, grace_hours, grade_floor = policy

            cursor.execute('''
            SELECT s.id, s.student_id, s.submission_date, s.grade
            FROM assignment_submissions s
            WHERE s.assignment_id = ? AND s.submission_date > ?
            ORDER BY s.student_id
            ''', (assignment_id, due_date_str))

            late_subs = cursor.fetchall()

            if not late_subs:
                print(f"\nNo late submissions found for '{title}'.")
                conn.close()
                return

            print(f"\nFound {len(late_subs)} late submission(s) for '{title}'.")
            print(f"Policy: {penalty_type}, {ppd}/day, grace: {grace_hours}h")

            penalties = []
            for sub_id, student_id, submit_str, current_grade in late_subs:
                submit_date = datetime.strptime(submit_str, '%Y-%m-%d %H:%M:%S')

                # Check late pass
                cursor.execute('''
                SELECT extra_days FROM late_passes
                WHERE student_id = ? AND assignment_id = ? AND status = 'active'
                ''', (student_id, assignment_id))

                late_pass = cursor.fetchone()
                extra_days = late_pass[0] if late_pass else 0
                effective_due = due_date + timedelta(days=extra_days)

                delta = submit_date - effective_due
                hours_late = delta.total_seconds() / 3600

                if hours_late <= 0:
                    continue

                if grace_hours > 0 and hours_late <= grace_hours:
                    continue

                days_late = (int((hours_late - grace_hours) / 24) + 1 if grace_hours > 0
                             else int(hours_late / 24) + 1)

                rejected = False
                if max_late > 0 and days_late > max_late:
                    rejected = True

                penalty_amount = 0.0
                if not rejected and penalty_type != 'none':
                    if penalty_type == 'percentage' and max_grade:
                        pct = min(ppd * days_late, 100.0)
                        penalty_amount = max_grade * (pct / 100)
                    elif penalty_type == 'fixed':
                        penalty_amount = ppd * days_late

                penalties.append({
                    'sub_id': sub_id,
                    'student_id': student_id,
                    'days_late': days_late,
                    'penalty': penalty_amount,
                    'rejected': rejected,
                    'current_grade': current_grade,
                    'extra_days': extra_days
                })

            if not penalties:
                print("No penalties to apply (all within grace period or have late passes).")
                conn.close()
                return

            print(f"\nPenalties to apply ({len(penalties)} submission(s)):")
            print("-" * 70)
            for p in penalties:
                status = "REJECTED" if p['rejected'] else f"-{p['penalty']:.1f}"
                pass_note = f" (late pass: +{p['extra_days']}d)" if p['extra_days'] > 0 else ""
                print(f"  Student {p['student_id']}: {p['days_late']} day(s) late -> {status}{pass_note}")

            confirm = input("\nApply all penalties? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("Cancelled.")
                conn.close()
                return

            applied_count = 0
            for p in penalties:
                if p['rejected']:
                    cursor.execute('''
                    UPDATE assignment_submissions
                    SET grade = 0, feedback = COALESCE(feedback, '') ||
                        ' [LATE PENALTY: Submission rejected - exceeded max late days]'
                    WHERE id = ?
                    ''', (p['sub_id'],))
                elif p['current_grade'] is not None and penalty_type != 'none':
                    new_grade = max(p['current_grade'] - p['penalty'], grade_floor)
                    cursor.execute('''
                    UPDATE assignment_submissions
                    SET grade = ?, feedback = COALESCE(feedback, '') ||
                        ' [LATE PENALTY: -' || ? || ' (' || ? || ' day(s) late)]'
                    WHERE id = ?
                    ''', (new_grade, p['penalty'], p['days_late'], p['sub_id']))
                applied_count += 1

            conn.commit()
            conn.close()

            print(f"\nPenalties applied to {applied_count} submission(s).")

        except Exception as e:
            print(f"Error applying batch penalties: {e}")

    def manage_late_passes(self):
        """Grant, view, or revoke late passes for students"""
        if not self._check_permission('manage_assignments'):
            return

        while True:
            print("\n=== Late Pass Management ===")
            print("1. Grant late pass")
            print("2. View late passes")
            print("3. Revoke late pass")
            print("4. Back")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self._grant_late_pass()
            elif choice == '2':
                self._view_late_passes()
            elif choice == '3':
                self._revoke_late_pass()
            elif choice == '4':
                break
            else:
                print("Invalid option.")

    def _grant_late_pass(self):
        """Grant a late pass to a student for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            student_id = input("Enter student ID: ").strip()
            if not student_id:
                print("Student ID cannot be empty.")
                conn.close()
                return

            cursor.execute(
                'SELECT student_id, first_name, last_name FROM students WHERE student_id = ?',
                (student_id,))
            student = cursor.fetchone()
            if not student:
                print("Student not found.")
                conn.close()
                return

            print(f"Student: {student[1]} {student[2]} ({student[0]})")

            cursor.execute('''
            SELECT a.id, a.title, a.module_code, a.due_date
            FROM assignments a
            JOIN student_modules sm ON a.module_code = sm.module_code
            WHERE sm.student_id = ? AND a.is_active = 1
            ORDER BY a.due_date
            ''', (student_id,))

            assignments = cursor.fetchall()

            if not assignments:
                print("No active assignments found for this student.")
                conn.close()
                return

            print("\nAssignments:")
            for i, (aid, title, module, due) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Due: {due}")

            assign_choice = input("\nSelect assignment number: ").strip()
            try:
                a_index = int(assign_choice) - 1
                if a_index < 0 or a_index >= len(assignments):
                    print("Invalid selection.")
                    conn.close()
                    return
                assignment_id = assignments[a_index][0]
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            cursor.execute('''
            SELECT id FROM late_passes
            WHERE student_id = ? AND assignment_id = ? AND status = 'active'
            ''', (student_id, assignment_id))

            existing = cursor.fetchone()
            if existing:
                print("Student already has an active late pass for this assignment.")
                conn.close()
                return

            try:
                extra_days = int(input("Extra days to grant: ").strip())
                if extra_days <= 0:
                    print("Must grant at least 1 day.")
                    conn.close()
                    return
            except ValueError:
                print("Invalid number.")
                conn.close()
                return

            reason = input("Reason for late pass: ").strip()

            cursor.execute('''
            INSERT INTO late_passes
            (student_id, assignment_id, extra_days, reason, status, granted_by, granted_date)
            VALUES (?, ?, ?, ?, 'active', ?, ?)
            ''', (student_id, assignment_id, extra_days, reason,
                  self.auth.current_user['id'],
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            conn.close()

            print(f"\nLate pass granted: +{extra_days} day(s) for '{assignments[a_index][1]}'.")

        except Exception as e:
            print(f"Error granting late pass: {e}")

    def _view_late_passes(self):
        """View late passes, optionally filtered by student"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            student_filter = input("Filter by student ID (Enter for all): ").strip()

            if student_filter:
                cursor.execute('''
                SELECT lp.id, lp.student_id, s.first_name, s.last_name,
                       a.title, lp.extra_days, lp.reason, lp.status, lp.granted_date
                FROM late_passes lp
                JOIN students s ON lp.student_id = s.student_id
                JOIN assignments a ON lp.assignment_id = a.id
                WHERE lp.student_id = ?
                ORDER BY lp.granted_date DESC
                ''', (student_filter,))
            else:
                cursor.execute('''
                SELECT lp.id, lp.student_id, s.first_name, s.last_name,
                       a.title, lp.extra_days, lp.reason, lp.status, lp.granted_date
                FROM late_passes lp
                JOIN students s ON lp.student_id = s.student_id
                JOIN assignments a ON lp.assignment_id = a.id
                ORDER BY lp.granted_date DESC
                ''')

            passes = cursor.fetchall()
            conn.close()

            if not passes:
                print("\nNo late passes found.")
                return

            print("\nLate Passes:")
            print("=" * 90)
            for lp_id, sid, fname, lname, title, days, reason, status, granted in passes:
                print(f"\nPass ID: {lp_id}")
                print(f"  Student: {fname} {lname} ({sid})")
                print(f"  Assignment: {title}")
                print(f"  Extra days: {days}")
                print(f"  Reason: {reason}")
                print(f"  Status: {status}")
                print(f"  Granted: {granted}")
                print("-" * 90)

        except Exception as e:
            print(f"Error viewing late passes: {e}")

    def _revoke_late_pass(self):
        """Revoke an active late pass"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT lp.id, lp.student_id, s.first_name, s.last_name,
                   a.title, lp.extra_days
            FROM late_passes lp
            JOIN students s ON lp.student_id = s.student_id
            JOIN assignments a ON lp.assignment_id = a.id
            WHERE lp.status = 'active'
            ORDER BY lp.granted_date DESC
            ''')

            passes = cursor.fetchall()

            if not passes:
                print("\nNo active late passes found.")
                conn.close()
                return

            print("\nActive Late Passes:")
            for i, (lp_id, sid, fname, lname, title, days) in enumerate(passes, 1):
                print(f"{i}. Pass {lp_id}: {fname} {lname} ({sid}) - {title} (+{days} days)")

            choice = input("\nSelect pass number to revoke: ").strip()
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(passes):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            lp_id = passes[index][0]

            confirm = input("Confirm revocation? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Cancelled.")
                conn.close()
                return

            cursor.execute('''
            UPDATE late_passes SET status = 'revoked' WHERE id = ?
            ''', (lp_id,))

            conn.commit()
            conn.close()

            print("Late pass revoked successfully.")

        except Exception as e:
            print(f"Error revoking late pass: {e}")

    def late_submission_report(self):
        """Generate a report of all late submissions with penalties"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            print("\n=== Late Submission Report ===")
            print("Filter options:")
            print("1. All late submissions")
            print("2. By module code")
            print("3. By assignment")

            filter_choice = input("\nSelect filter: ").strip()

            base_query = '''
            SELECT a.id, a.title, a.module_code, a.due_date, a.max_grade,
                   sub.student_id, s.first_name, s.last_name,
                   sub.submission_date, sub.grade,
                   lp.name as policy_name, lp.penalty_type, lp.penalty_per_day,
                   lp.grace_period_hours, lp.max_late_days
            FROM assignment_submissions sub
            JOIN assignments a ON sub.assignment_id = a.id
            JOIN students s ON sub.student_id = s.student_id
            LEFT JOIN assignment_late_policies alp ON a.id = alp.assignment_id
            LEFT JOIN late_policies lp ON alp.policy_id = lp.id
            WHERE sub.submission_date > a.due_date
            '''

            params = []

            if filter_choice == '2':
                module_code = input("Enter module code: ").strip()
                base_query += ' AND a.module_code = ?'
                params.append(module_code)
            elif filter_choice == '3':
                assign_id = input("Enter assignment ID: ").strip()
                base_query += ' AND a.id = ?'
                params.append(assign_id)

            base_query += ' ORDER BY a.module_code, a.title, sub.submission_date'

            cursor.execute(base_query, params)
            rows = cursor.fetchall()

            # Also fetch late passes for cross-reference
            cursor.execute('''
            SELECT student_id, assignment_id, extra_days, status
            FROM late_passes WHERE status = 'active'
            ''')
            active_passes = {}
            for sid, aid, extra, status in cursor.fetchall():
                active_passes[(sid, aid)] = extra

            conn.close()

            if not rows:
                print("\nNo late submissions found.")
                return

            print(f"\nFound {len(rows)} late submission(s):")
            print("=" * 110)

            total_penalties = 0
            current_assignment = None

            for row in rows:
                (aid, title, module, due_str, max_grade, student_id, fname, lname,
                 submit_str, grade, pol_name, pen_type, ppd, grace_h, max_late) = row

                if current_assignment != aid:
                    current_assignment = aid
                    print(f"\n  Assignment: {title} ({module}) - Due: {due_str}")
                    if pol_name:
                        print(f"  Policy: {pol_name} ({pen_type}, {ppd}/day)")
                    else:
                        print("  Policy: None assigned")
                    print(f"  {'Student':<30} {'Submitted':<22} {'Days Late':<12} {'Penalty':<15} {'Grade'}")
                    print(f"  {'-'*30} {'-'*22} {'-'*12} {'-'*15} {'-'*10}")

                due_date = datetime.strptime(due_str, '%Y-%m-%d %H:%M:%S')
                submit_date = datetime.strptime(submit_str, '%Y-%m-%d %H:%M:%S')

                extra = active_passes.get((student_id, aid), 0)
                effective_due = due_date + timedelta(days=extra)
                delta = submit_date - effective_due
                hours_late = delta.total_seconds() / 3600

                if hours_late <= 0:
                    days_late_str = "On time*"
                    penalty_str = "None (pass)"
                elif grace_h and hours_late <= grace_h:
                    days_late_str = "Grace"
                    penalty_str = "None"
                else:
                    effective_grace = grace_h if grace_h else 0
                    days_late = (int((hours_late - effective_grace) / 24) + 1
                                 if effective_grace > 0 else int(hours_late / 24) + 1)
                    days_late_str = str(days_late)

                    if max_late and days_late > max_late:
                        penalty_str = "REJECTED"
                    elif pen_type == 'percentage' and ppd:
                        pct = min(ppd * days_late, 100.0)
                        penalty_str = f"-{pct:.0f}%"
                        total_penalties += 1
                    elif pen_type == 'fixed' and ppd:
                        pts = ppd * days_late
                        penalty_str = f"-{pts:.1f} pts"
                        total_penalties += 1
                    else:
                        penalty_str = "N/A"

                grade_str = f"{grade}" if grade is not None else "Ungraded"
                pass_note = " (pass)" if extra > 0 else ""

                print(f"  {fname} {lname} ({student_id}){pass_note:<{max(0, 30 - len(fname) - len(lname) - len(student_id) - len(pass_note) - 4)}} "
                      f"{submit_str:<22} {days_late_str:<12} {penalty_str:<15} {grade_str}")

            print(f"\n{'=' * 110}")
            print(f"Total late submissions: {len(rows)}")
            print(f"Submissions with penalties: {total_penalties}")

        except Exception as e:
            print(f"Error generating late submission report: {e}")

    def use_policy_template(self):
        """Quick-create a late policy from predefined templates"""
        if not self._check_permission('manage_assignments'):
            return

        templates = {
            '1': {
                'name': 'Strict',
                'description': 'Strict late policy: 20% penalty per day, max 3 days, no grace period',
                'penalty_type': 'percentage',
                'penalty_per_day': 20.0,
                'max_late_days': 3,
                'grace_period_hours': 0,
                'min_grade_floor': 0
            },
            '2': {
                'name': 'Standard',
                'description': 'Standard late policy: 10% penalty per day, max 5 days, 1 hour grace',
                'penalty_type': 'percentage',
                'penalty_per_day': 10.0,
                'max_late_days': 5,
                'grace_period_hours': 1,
                'min_grade_floor': 0
            },
            '3': {
                'name': 'Lenient',
                'description': 'Lenient late policy: 5% penalty per day, max 7 days, 6 hour grace',
                'penalty_type': 'percentage',
                'penalty_per_day': 5.0,
                'max_late_days': 7,
                'grace_period_hours': 6,
                'min_grade_floor': 0
            }
        }

        print("\n=== Late Policy Templates ===")
        print("1. Strict  - 20%/day, max 3 days, no grace period")
        print("2. Standard - 10%/day, max 5 days, 1h grace period")
        print("3. Lenient - 5%/day, max 7 days, 6h grace period")

        choice = input("\nSelect template (1/2/3): ").strip()
        template = templates.get(choice)

        if not template:
            print("Invalid selection.")
            return

        custom_name = input(f"Policy name [{template['name']}]: ").strip()
        if custom_name:
            template['name'] = custom_name

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO late_policies
            (name, description, penalty_type, penalty_per_day, max_late_days,
             grace_period_hours, min_grade_floor, created_by, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (template['name'], template['description'], template['penalty_type'],
                  template['penalty_per_day'], template['max_late_days'],
                  template['grace_period_hours'], template['min_grade_floor'],
                  self.auth.current_user['id'],
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            policy_id = cursor.lastrowid
            conn.close()

            print(f"\nPolicy '{template['name']}' created from template (ID: {policy_id}).")
            print(f"  Penalty: {template['penalty_per_day']}% per day")
            print(f"  Max late days: {template['max_late_days']}")
            print(f"  Grace period: {template['grace_period_hours']}h")

        except Exception as e:
            print(f"Error creating policy from template: {e}")
