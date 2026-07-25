from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
import json
import csv
import os


class AdminToolsMixin:
    """Mixin providing SIS roster sync, academic integrity, grade audit,
    accommodations, and TA assignment management."""

    def sis_roster_sync(self):
        """Main SIS roster synchronisation menu"""
        if not self._check_permission('manage_assignments'):
            return

        while True:
            print("\nSIS Roster Sync")
            print("=" * 50)
            print("1. Import roster from CSV")
            print("2. Validate current enrolments")
            print("3. View sync history")
            print("0. Back")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self.import_roster_csv()
            elif choice == '2':
                self.sync_roster_validation()
            elif choice == '3':
                self._view_sync_history()
            elif choice == '0':
                break
            else:
                print("Invalid option.")

    def import_roster_csv(self):
        """Import student roster from CSV file"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nImport Student Roster from CSV")
            print("=" * 50)
            print("Expected columns: student_id, first_name, last_name, email, module_code")

            file_path = input("CSV file path: ").strip()
            if not file_path:
                print("No file path provided.")
                return

            if not os.path.isfile(file_path):
                print(f"File not found: {file_path}")
                return

            rows = []
            try:
                with open(file_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    required = {'student_id', 'first_name', 'last_name', 'email', 'module_code'}
                    if not required.issubset(set(reader.fieldnames or [])):
                        missing = required - set(reader.fieldnames or [])
                        print(f"Missing required columns: {', '.join(missing)}")
                        return
                    for row in reader:
                        rows.append(row)
            except Exception as e:
                print(f"Error reading CSV: {e}")
                return

            if not rows:
                print("CSV file is empty.")
                return

            print(f"\nFound {len(rows)} rows. Proceed with import? (y/n): ", end='')
            confirm = input().strip().lower()
            if confirm != 'y':
                print("Import cancelled.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                inserted = 0
                updated = 0
                enrolled = 0
                errors = []

                for i, row in enumerate(rows, 1):
                    try:
                        sid = row['student_id'].strip()
                        fname = row['first_name'].strip()
                        lname = row['last_name'].strip()
                        email = row['email'].strip()
                        module = row['module_code'].strip()

                        if not all([sid, fname, lname, email, module]):
                            errors.append(f"Row {i}: missing required field(s)")
                            continue

                        # Upsert student
                        cursor.execute(
                            'SELECT id FROM students WHERE student_id = ?', (sid,))
                        existing = cursor.fetchone()

                        if existing:
                            cursor.execute('''
                                UPDATE students
                                SET first_name = ?, last_name = ?, email = ?, updated_at = ?
                                WHERE student_id = ?
                            ''', (fname, lname, email, timestamp, sid))
                            updated += 1
                        else:
                            cursor.execute('''
                                INSERT INTO students (student_id, first_name, last_name, email, created_at)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (sid, fname, lname, email, timestamp))
                            inserted += 1

                        # Upsert enrolment
                        cursor.execute('''
                            SELECT id FROM student_modules
                            WHERE student_id = ? AND module_code = ?
                        ''', (sid, module))
                        if not cursor.fetchone():
                            cursor.execute('''
                                INSERT INTO student_modules (student_id, module_code, enrolled_at)
                                VALUES (?, ?, ?)
                            ''', (sid, module, timestamp))
                            enrolled += 1

                    except Exception as e:
                        errors.append(f"Row {i}: {e}")

                # Log sync
                sync_details = json.dumps({
                    'file': file_path,
                    'total_rows': len(rows),
                    'inserted': inserted,
                    'updated': updated,
                    'enrolled': enrolled,
                    'errors': len(errors)
                })
                cursor.execute('''
                    INSERT INTO sis_sync_log
                        (sync_type, source_file, records_processed, records_added,
                         records_updated, errors, details, synced_at, synced_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', ('csv_import', file_path, len(rows), inserted, updated,
                      len(errors), sync_details, timestamp,
                      self.auth.current_user['id']))

                conn.commit()

                print("\nImport Complete")
                print(f"  New students: {inserted}")
                print(f"  Updated students: {updated}")
                print(f"  New enrolments: {enrolled}")
                if errors:
                    print(f"  Errors: {len(errors)}")
                    for err in errors[:10]:
                        print(f"    - {err}")
                    if len(errors) > 10:
                        print(f"    ... and {len(errors) - 10} more")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error importing roster: {e}")

    def sync_roster_validation(self):
        """Validate current enrolments against database records"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                print("\nRoster Validation Report")
                print("=" * 50)

                # Students with no module enrolments
                cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name
                    FROM students s
                    LEFT JOIN student_modules sm ON s.student_id = sm.student_id
                    WHERE sm.id IS NULL
                ''')
                no_modules = cursor.fetchall()
                print(f"\nStudents with no enrolments: {len(no_modules)}")
                for sid, fname, lname in no_modules[:10]:
                    print(f"  {sid}: {fname} {lname}")
                if len(no_modules) > 10:
                    print(f"  ... and {len(no_modules) - 10} more")

                # Modules with no enrolled students
                cursor.execute('''
                    SELECT DISTINCT a.module_code
                    FROM assignments a
                    LEFT JOIN student_modules sm ON a.module_code = sm.module_code
                    WHERE sm.id IS NULL AND a.is_active = 1
                ''')
                empty_modules = cursor.fetchall()
                print(f"\nActive assignment modules with no students: {len(empty_modules)}")
                for (mod,) in empty_modules:
                    print(f"  {mod}")

                # Submissions from non-enrolled students
                cursor.execute('''
                    SELECT sub.student_id, a.module_code, COUNT(*) as cnt
                    FROM assignment_submissions sub
                    JOIN assignments a ON sub.assignment_id = a.id
                    LEFT JOIN student_modules sm
                        ON sub.student_id = sm.student_id
                        AND a.module_code = sm.module_code
                    WHERE sm.id IS NULL
                    GROUP BY sub.student_id, a.module_code
                ''')
                mismatched = cursor.fetchall()
                print(f"\nSubmissions from non-enrolled students: {len(mismatched)}")
                for sid, mod, cnt in mismatched[:10]:
                    print(f"  {sid} in {mod}: {cnt} submission(s)")
                if len(mismatched) > 10:
                    print(f"  ... and {len(mismatched) - 10} more")

                # Summary
                cursor.execute('SELECT COUNT(*) FROM students')
                total_students = cursor.fetchone()[0]
                cursor.execute('SELECT COUNT(*) FROM student_modules')
                total_enrolments = cursor.fetchone()[0]

                print("\nSummary")
                print(f"  Total students: {total_students}")
                print(f"  Total enrolments: {total_enrolments}")
                print(f"  Issues found: {len(no_modules) + len(empty_modules) + len(mismatched)}")

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO sis_sync_log
                        (sync_type, records_processed, errors, details, synced_at, synced_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('validation', total_students,
                      len(no_modules) + len(empty_modules) + len(mismatched),
                      json.dumps({
                          'no_enrolments': len(no_modules),
                          'empty_modules': len(empty_modules),
                          'mismatched_submissions': len(mismatched)
                      }),
                      timestamp, self.auth.current_user['id']))
                conn.commit()

            finally:
                conn.close()

        except Exception as e:
            print(f"Error validating roster: {e}")

    def _view_sync_history(self):
        """View SIS sync history"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, sync_type, source_file, records_processed,
                           records_added, records_updated, errors, synced_at
                    FROM sis_sync_log
                    ORDER BY synced_at DESC
                    LIMIT 20
                ''')
                logs = cursor.fetchall()

                if not logs:
                    print("\nNo sync history found.")
                    return

                print("\nSIS Sync History (last 20)")
                print("=" * 90)
                print(f"{'ID':<5} {'Type':<14} {'Source':<20} {'Processed':<10} "
                      f"{'Added':<7} {'Updated':<8} {'Errors':<7} {'Date'}")
                print("-" * 90)
                for log_id, stype, src, proc, added, upd, errs, dt in logs:
                    src_display = (src or '-')[:18]
                    print(f"{log_id:<5} {stype:<14} {src_display:<20} "
                          f"{proc or 0:<10} {added or 0:<7} {upd or 0:<8} "
                          f"{errs or 0:<7} {dt}")
            finally:
                conn.close()

        except Exception as e:
            print(f"Error viewing sync history: {e}")

    def manage_integrity_cases(self):
        """Manage academic integrity cases"""
        if not self._check_permission('manage_assignments'):
            return

        while True:
            print("\nAcademic Integrity Management")
            print("=" * 50)
            print("1. View all cases")
            print("2. Create new case")
            print("3. Review/update case")
            print("4. Filter cases by status")
            print("0. Back")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self._list_integrity_cases()
            elif choice == '2':
                self.create_integrity_case()
            elif choice == '3':
                self.review_integrity_case()
            elif choice == '4':
                self._filter_integrity_cases()
            elif choice == '0':
                break
            else:
                print("Invalid option.")

    def _list_integrity_cases(self, status_filter=None):
        """List academic integrity cases, optionally filtered by status"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                if status_filter:
                    cursor.execute('''
                        SELECT ic.id, ic.student_id, ic.assignment_id, ic.case_type,
                               ic.status, ic.created_at, a.title
                        FROM integrity_cases ic
                        LEFT JOIN assignments a ON ic.assignment_id = a.id
                        WHERE ic.status = ?
                        ORDER BY ic.created_at DESC
                    ''', (status_filter,))
                else:
                    cursor.execute('''
                        SELECT ic.id, ic.student_id, ic.assignment_id, ic.case_type,
                               ic.status, ic.created_at, a.title
                        FROM integrity_cases ic
                        LEFT JOIN assignments a ON ic.assignment_id = a.id
                        ORDER BY ic.created_at DESC
                    ''')

                cases = cursor.fetchall()

                if not cases:
                    print("\nNo integrity cases found.")
                    return

                print(f"\nAcademic Integrity Cases"
                      f"{' (Status: ' + status_filter + ')' if status_filter else ''}")
                print("=" * 95)
                print(f"{'ID':<5} {'Student':<12} {'Assignment':<25} "
                      f"{'Type':<16} {'Status':<12} {'Date'}")
                print("-" * 95)
                for cid, sid, aid, ctype, status, dt, title in cases:
                    title_display = (title or f'#{aid}')[:23]
                    print(f"{cid:<5} {sid:<12} {title_display:<25} "
                          f"{ctype:<16} {status:<12} {dt}")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error listing integrity cases: {e}")

    def _filter_integrity_cases(self):
        """Filter integrity cases by status"""
        print("\nFilter by status:")
        print("1. Open")
        print("2. Under Review")
        print("3. Resolved")
        print("4. Dismissed")

        status_map = {
            '1': 'open',
            '2': 'under_review',
            '3': 'resolved',
            '4': 'dismissed'
        }

        choice = input("Select status: ").strip()
        status = status_map.get(choice)
        if status:
            self._list_integrity_cases(status_filter=status)
        else:
            print("Invalid selection.")

    def create_integrity_case(self):
        """Create a new academic integrity case"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nCreate Academic Integrity Case")
            print("=" * 50)

            student_id = input("Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                # Verify student exists
                cursor.execute(
                    'SELECT student_id, first_name, last_name FROM students WHERE student_id = ?',
                    (student_id,))
                student = cursor.fetchone()
                if not student:
                    print(f"Student '{student_id}' not found.")
                    return
                print(f"Student: {student[1]} {student[2]} ({student[0]})")

                # Select assignment
                cursor.execute('''
                    SELECT a.id, a.title, a.module_code
                    FROM assignments a
                    JOIN student_modules sm ON a.module_code = sm.module_code
                    WHERE sm.student_id = ? AND a.is_active = 1
                    ORDER BY a.module_code, a.title
                ''', (student_id,))
                assignments = cursor.fetchall()

                if not assignments:
                    print("No assignments found for this student.")
                    return

                print("\nAssignments:")
                for i, (aid, title, mod) in enumerate(assignments, 1):
                    print(f"  {i}. [{mod}] {title}")

                a_choice = input("Select assignment number: ").strip()
                try:
                    a_index = int(a_choice) - 1
                    if not (0 <= a_index < len(assignments)):
                        print("Invalid selection.")
                        return
                except ValueError:
                    print("Please enter a number.")
                    return

                assignment_id = assignments[a_index][0]

                # Case type
                print("\nCase type:")
                print("  1. Plagiarism")
                print("  2. Collusion")
                print("  3. Contract cheating")
                print("  4. Falsification")
                print("  5. Other")

                type_map = {
                    '1': 'plagiarism',
                    '2': 'collusion',
                    '3': 'contract_cheating',
                    '4': 'falsification',
                    '5': 'other'
                }
                t_choice = input("Select type: ").strip()
                case_type = type_map.get(t_choice)
                if not case_type:
                    print("Invalid type selection.")
                    return

                description = input("Description: ").strip()
                if not description:
                    print("Description is required.")
                    return

                evidence = input("Evidence details (or press Enter to skip): ").strip()

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO integrity_cases
                        (student_id, assignment_id, case_type, description, evidence,
                         status, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, assignment_id, case_type, description,
                      evidence or None, 'open',
                      self.auth.current_user['id'], timestamp))

                conn.commit()
                case_id = cursor.lastrowid
                print(f"\nIntegrity case #{case_id} created successfully.")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error creating integrity case: {e}")

    def review_integrity_case(self):
        """Review and update an academic integrity case"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            case_id_str = input("\nEnter case ID to review: ").strip()
            if not case_id_str:
                return

            try:
                case_id = int(case_id_str)
            except ValueError:
                print("Invalid case ID.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ic.id, ic.student_id, ic.assignment_id, ic.case_type,
                           ic.description, ic.evidence, ic.status, ic.outcome,
                           ic.penalty, ic.created_at, ic.resolved_at,
                           a.title, s.first_name, s.last_name
                    FROM integrity_cases ic
                    LEFT JOIN assignments a ON ic.assignment_id = a.id
                    LEFT JOIN students s ON ic.student_id = s.student_id
                    WHERE ic.id = ?
                ''', (case_id,))
                case = cursor.fetchone()

                if not case:
                    print(f"Case #{case_id} not found.")
                    return

                (cid, sid, aid, ctype, desc, evidence, status, outcome,
                 penalty, created, resolved, atitle, fname, lname) = case

                print(f"\nCase #{cid}")
                print("=" * 50)
                print(f"Student:    {fname} {lname} ({sid})")
                print(f"Assignment: {atitle or f'#{aid}'}")
                print(f"Type:       {ctype}")
                print(f"Status:     {status}")
                print(f"Created:    {created}")
                print(f"Description: {desc}")
                if evidence:
                    print(f"Evidence:   {evidence}")
                if outcome:
                    print(f"Outcome:    {outcome}")
                if penalty:
                    print(f"Penalty:    {penalty}")
                if resolved:
                    print(f"Resolved:   {resolved}")

                print("\nActions:")
                print("1. Change status")
                print("2. Set outcome and penalty")
                print("3. Add evidence")
                print("0. Back")

                action = input("Select action: ").strip()

                if action == '1':
                    print("\nNew status:")
                    print("  1. Open")
                    print("  2. Under Review")
                    print("  3. Resolved")
                    print("  4. Dismissed")

                    s_map = {
                        '1': 'open',
                        '2': 'under_review',
                        '3': 'resolved',
                        '4': 'dismissed'
                    }
                    s_choice = input("Select status: ").strip()
                    new_status = s_map.get(s_choice)
                    if not new_status:
                        print("Invalid status.")
                        return

                    resolved_at = None
                    if new_status in ('resolved', 'dismissed'):
                        resolved_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute('''
                        UPDATE integrity_cases
                        SET status = ?, resolved_at = ?, updated_at = ?
                        WHERE id = ?
                    ''', (new_status, resolved_at,
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), case_id))
                    conn.commit()
                    print(f"Status updated to '{new_status}'.")

                elif action == '2':
                    new_outcome = input("Outcome: ").strip()
                    new_penalty = input("Penalty: ").strip()

                    if not new_outcome:
                        print("Outcome is required.")
                        return

                    cursor.execute('''
                        UPDATE integrity_cases
                        SET outcome = ?, penalty = ?, updated_at = ?
                        WHERE id = ?
                    ''', (new_outcome, new_penalty or None,
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), case_id))
                    conn.commit()
                    print("Outcome and penalty updated.")

                elif action == '3':
                    additional = input("Additional evidence: ").strip()
                    if not additional:
                        print("No evidence provided.")
                        return

                    current_evidence = evidence or ''
                    updated_evidence = (current_evidence + '\n' + additional).strip()

                    cursor.execute('''
                        UPDATE integrity_cases
                        SET evidence = ?, updated_at = ?
                        WHERE id = ?
                    ''', (updated_evidence,
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), case_id))
                    conn.commit()
                    print("Evidence updated.")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error reviewing integrity case: {e}")

    def view_grade_audit_log(self):
        """View grade change history with filters"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nGrade Audit Log")
            print("=" * 50)
            print("Filter options (press Enter to skip):")

            student_filter = input("Student ID: ").strip() or None
            assignment_filter = input("Assignment ID: ").strip() or None

            date_from = input("From date (YYYY-MM-DD): ").strip() or None
            date_to = input("To date (YYYY-MM-DD): ").strip() or None

            # Validate date formats
            if date_from:
                try:
                    datetime.strptime(date_from, '%Y-%m-%d')
                except ValueError:
                    print("Invalid from-date format.")
                    return
            if date_to:
                try:
                    datetime.strptime(date_to, '%Y-%m-%d')
                except ValueError:
                    print("Invalid to-date format.")
                    return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                query = '''
                    SELECT gal.id, gal.student_id, gal.assignment_id,
                           gal.old_grade, gal.new_grade, gal.changed_by,
                           gal.reason, gal.changed_at, a.title
                    FROM grade_audit_log gal
                    LEFT JOIN assignments a ON gal.assignment_id = a.id
                    WHERE 1=1
                '''
                params = []

                if student_filter:
                    query += ' AND gal.student_id = ?'
                    params.append(student_filter)
                if assignment_filter:
                    try:
                        query += ' AND gal.assignment_id = ?'
                        params.append(int(assignment_filter))
                    except ValueError:
                        print("Invalid assignment ID.")
                        return
                if date_from:
                    query += ' AND gal.changed_at >= ?'
                    params.append(date_from + ' 00:00:00')
                if date_to:
                    query += ' AND gal.changed_at <= ?'
                    params.append(date_to + ' 23:59:59')

                query += ' ORDER BY gal.changed_at DESC LIMIT 50'

                cursor.execute(query, params)
                logs = cursor.fetchall()

                if not logs:
                    print("\nNo grade changes found matching filters.")
                    return

                print(f"\nGrade Change History ({len(logs)} records)")
                print("=" * 105)
                print(f"{'ID':<5} {'Student':<12} {'Assignment':<22} "
                      f"{'Old':<8} {'New':<8} {'Changed By':<12} {'Reason':<18} {'Date'}")
                print("-" * 105)
                for (lid, sid, aid, old_g, new_g, changed_by,
                     reason, changed_at, atitle) in logs:
                    title_display = (atitle or f'#{aid}')[:20]
                    reason_display = (reason or '-')[:16]
                    old_display = f"{old_g}" if old_g is not None else '-'
                    new_display = f"{new_g}" if new_g is not None else '-'
                    print(f"{lid:<5} {sid:<12} {title_display:<22} "
                          f"{old_display:<8} {new_display:<8} "
                          f"{changed_by or '-':<12} {reason_display:<18} {changed_at}")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error viewing grade audit log: {e}")

    def manage_accommodations(self):
        """View, add, and deactivate student accessibility accommodations"""
        if not self._check_permission('manage_assignments'):
            return

        while True:
            print("\nStudent Accommodations Management")
            print("=" * 50)
            print("1. View all active accommodations")
            print("2. View accommodations for a student")
            print("3. Add new accommodation")
            print("4. Deactivate accommodation")
            print("0. Back")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self._list_accommodations()
            elif choice == '2':
                sid = input("Student ID: ").strip()
                if sid:
                    self._list_accommodations(student_id=sid)
            elif choice == '3':
                self.add_accommodation()
            elif choice == '4':
                self._deactivate_accommodation()
            elif choice == '0':
                break
            else:
                print("Invalid option.")

    def _list_accommodations(self, student_id=None):
        """List active accommodations"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                if student_id:
                    cursor.execute('''
                        SELECT sa.id, sa.student_id, sa.accommodation_type,
                               sa.details, sa.time_multiplier, sa.expiry_date,
                               sa.is_active, s.first_name, s.last_name
                        FROM student_accommodations sa
                        LEFT JOIN students s ON sa.student_id = s.student_id
                        WHERE sa.student_id = ? AND sa.is_active = 1
                        ORDER BY sa.accommodation_type
                    ''', (student_id,))
                else:
                    cursor.execute('''
                        SELECT sa.id, sa.student_id, sa.accommodation_type,
                               sa.details, sa.time_multiplier, sa.expiry_date,
                               sa.is_active, s.first_name, s.last_name
                        FROM student_accommodations sa
                        LEFT JOIN students s ON sa.student_id = s.student_id
                        WHERE sa.is_active = 1
                        ORDER BY sa.student_id, sa.accommodation_type
                    ''')

                records = cursor.fetchall()

                if not records:
                    print("\nNo active accommodations found.")
                    return

                print(f"\nActive Accommodations ({len(records)} records)")
                print("=" * 100)
                print(f"{'ID':<5} {'Student':<12} {'Name':<20} "
                      f"{'Type':<18} {'Multiplier':<11} {'Expiry':<12} {'Details'}")
                print("-" * 100)
                for (aid, sid, atype, details, mult, expiry,
                     active, fname, lname) in records:
                    name = f"{fname} {lname}" if fname else '-'
                    name = name[:18]
                    mult_str = f"x{mult:.1f}" if mult else '-'
                    expiry_str = expiry[:10] if expiry else 'None'
                    details_str = (details or '-')[:25]
                    print(f"{aid:<5} {sid:<12} {name:<20} "
                          f"{atype:<18} {mult_str:<11} {expiry_str:<12} {details_str}")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error listing accommodations: {e}")

    def add_accommodation(self):
        """Add a new student accommodation"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nAdd Student Accommodation")
            print("=" * 50)

            student_id = input("Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute(
                    'SELECT student_id, first_name, last_name FROM students WHERE student_id = ?',
                    (student_id,))
                student = cursor.fetchone()
                if not student:
                    print(f"Student '{student_id}' not found.")
                    return
                print(f"Student: {student[1]} {student[2]}")

                print("\nAccommodation type:")
                print("  1. Extra time")
                print("  2. Rest breaks")
                print("  3. Alternative format")
                print("  4. Assistive technology")
                print("  5. Separate room")
                print("  6. Other")

                type_map = {
                    '1': 'extra_time',
                    '2': 'rest_breaks',
                    '3': 'alternative_format',
                    '4': 'assistive_technology',
                    '5': 'separate_room',
                    '6': 'other'
                }
                t_choice = input("Select type: ").strip()
                acc_type = type_map.get(t_choice)
                if not acc_type:
                    print("Invalid type selection.")
                    return

                details = input("Details: ").strip()
                if not details:
                    print("Details are required.")
                    return

                time_multiplier = 1.0
                mult_input = input("Time multiplier (default 1.0, e.g. 1.5 for 50% extra): ").strip()
                if mult_input:
                    try:
                        time_multiplier = float(mult_input)
                        if time_multiplier <= 0:
                            print("Multiplier must be positive.")
                            return
                    except ValueError:
                        print("Invalid multiplier value.")
                        return

                expiry_date = input("Expiry date (YYYY-MM-DD, or Enter for none): ").strip()
                if expiry_date:
                    try:
                        datetime.strptime(expiry_date, '%Y-%m-%d')
                    except ValueError:
                        print("Invalid date format.")
                        return
                else:
                    expiry_date = None

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO student_accommodations
                        (student_id, accommodation_type, details, time_multiplier,
                         expiry_date, is_active, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ''', (student_id, acc_type, details, time_multiplier,
                      expiry_date, self.auth.current_user['id'], timestamp))

                conn.commit()
                acc_id = cursor.lastrowid
                print(f"\nAccommodation #{acc_id} added successfully.")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error adding accommodation: {e}")

    def _deactivate_accommodation(self):
        """Deactivate an existing accommodation"""
        try:
            acc_id_str = input("Accommodation ID to deactivate: ").strip()
            if not acc_id_str:
                return

            try:
                acc_id = int(acc_id_str)
            except ValueError:
                print("Invalid accommodation ID.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT sa.id, sa.student_id, sa.accommodation_type, sa.is_active,
                           s.first_name, s.last_name
                    FROM student_accommodations sa
                    LEFT JOIN students s ON sa.student_id = s.student_id
                    WHERE sa.id = ?
                ''', (acc_id,))
                record = cursor.fetchone()

                if not record:
                    print(f"Accommodation #{acc_id} not found.")
                    return

                if not record[3]:
                    print(f"Accommodation #{acc_id} is already inactive.")
                    return

                name = f"{record[4]} {record[5]}" if record[4] else record[1]
                print(f"Deactivate {record[2]} for {name}? (y/n): ", end='')
                confirm = input().strip().lower()
                if confirm != 'y':
                    print("Cancelled.")
                    return

                cursor.execute('''
                    UPDATE student_accommodations
                    SET is_active = 0, updated_at = ?
                    WHERE id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), acc_id))
                conn.commit()
                print(f"Accommodation #{acc_id} deactivated.")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error deactivating accommodation: {e}")

    def manage_ta_assignments(self):
        """Manage teaching assistant assignments"""
        if not self._check_permission('manage_assignments'):
            return

        while True:
            print("\nTA Assignment Management")
            print("=" * 50)
            print("1. View current TA assignments")
            print("2. Assign TA to module/section")
            print("3. Configure TA permissions")
            print("4. Remove TA assignment")
            print("0. Back")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self._list_ta_assignments()
            elif choice == '2':
                self.assign_ta()
            elif choice == '3':
                self.configure_ta_permissions()
            elif choice == '4':
                self._remove_ta_assignment()
            elif choice == '0':
                break
            else:
                print("Invalid option.")

    def _list_ta_assignments(self):
        """List all current TA assignments"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ta.id, ta.ta_user_id, ta.module_code, ta.section,
                           ta.can_grade, ta.can_manage_assignments,
                           ta.can_view_analytics, ta.assigned_at
                    FROM ta_assignments ta
                    WHERE ta.is_active = 1
                    ORDER BY ta.module_code, ta.section
                ''')
                records = cursor.fetchall()

                if not records:
                    print("\nNo active TA assignments found.")
                    return

                print(f"\nActive TA Assignments ({len(records)})")
                print("=" * 100)
                print(f"{'ID':<5} {'TA User':<14} {'Module':<12} {'Section':<10} "
                      f"{'Grade':<7} {'Manage':<8} {'Analytics':<10} {'Assigned'}")
                print("-" * 100)
                for (tid, ta_user, mod, section, can_grade,
                     can_manage, can_analytics, assigned) in records:
                    section_str = section or 'All'
                    print(f"{tid:<5} {ta_user:<14} {mod:<12} {section_str:<10} "
                          f"{'Yes' if can_grade else 'No':<7} "
                          f"{'Yes' if can_manage else 'No':<8} "
                          f"{'Yes' if can_analytics else 'No':<10} {assigned}")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error listing TA assignments: {e}")

    def assign_ta(self):
        """Assign a TA to a module/section"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nAssign Teaching Assistant")
            print("=" * 50)

            ta_user_id = input("TA user ID: ").strip()
            if not ta_user_id:
                print("TA user ID is required.")
                return

            module_code = input("Module code: ").strip()
            if not module_code:
                print("Module code is required.")
                return

            section = input("Section (or Enter for all sections): ").strip() or None

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                # Check for duplicate assignment
                cursor.execute('''
                    SELECT id FROM ta_assignments
                    WHERE ta_user_id = ? AND module_code = ?
                    AND (section = ? OR (section IS NULL AND ? IS NULL))
                    AND is_active = 1
                ''', (ta_user_id, module_code, section, section))
                if cursor.fetchone():
                    print("This TA is already assigned to this module/section.")
                    return

                # Configure permissions
                print("\nPermissions:")
                can_grade = input("Can grade submissions? (y/n): ").strip().lower() == 'y'
                can_manage = input("Can manage assignments? (y/n): ").strip().lower() == 'y'
                can_analytics = input("Can view analytics? (y/n): ").strip().lower() == 'y'

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO ta_assignments
                        (ta_user_id, module_code, section, can_grade,
                         can_manage_assignments, can_view_analytics,
                         is_active, assigned_by, assigned_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                ''', (ta_user_id, module_code, section, int(can_grade),
                      int(can_manage), int(can_analytics),
                      self.auth.current_user['id'], timestamp))

                conn.commit()
                ta_id = cursor.lastrowid
                print(f"\nTA assignment #{ta_id} created successfully.")
                print(f"  TA: {ta_user_id}")
                print(f"  Module: {module_code}")
                print(f"  Section: {section or 'All'}")
                print(f"  Permissions: grade={'Yes' if can_grade else 'No'}, "
                      f"manage={'Yes' if can_manage else 'No'}, "
                      f"analytics={'Yes' if can_analytics else 'No'}")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error assigning TA: {e}")

    def configure_ta_permissions(self):
        """Configure permissions for an existing TA assignment"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            ta_id_str = input("\nTA assignment ID: ").strip()
            if not ta_id_str:
                return

            try:
                ta_id = int(ta_id_str)
            except ValueError:
                print("Invalid assignment ID.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, ta_user_id, module_code, section,
                           can_grade, can_manage_assignments, can_view_analytics
                    FROM ta_assignments
                    WHERE id = ? AND is_active = 1
                ''', (ta_id,))
                record = cursor.fetchone()

                if not record:
                    print(f"Active TA assignment #{ta_id} not found.")
                    return

                _, ta_user, mod, section, cur_grade, cur_manage, cur_analytics = record

                print(f"\nTA: {ta_user} | Module: {mod} | Section: {section or 'All'}")
                print("Current permissions:")
                print(f"  Grade:     {'Yes' if cur_grade else 'No'}")
                print(f"  Manage:    {'Yes' if cur_manage else 'No'}")
                print(f"  Analytics: {'Yes' if cur_analytics else 'No'}")

                print("\nUpdate permissions (y/n, or Enter to keep current):")

                grade_input = input(
                    f"  Can grade submissions? [{'Y' if cur_grade else 'N'}]: ").strip().lower()
                manage_input = input(
                    f"  Can manage assignments? [{'Y' if cur_manage else 'N'}]: ").strip().lower()
                analytics_input = input(
                    f"  Can view analytics? [{'Y' if cur_analytics else 'N'}]: ").strip().lower()

                new_grade = (
                    grade_input == 'y' if grade_input in ('y', 'n') else bool(cur_grade))
                new_manage = (
                    manage_input == 'y' if manage_input in ('y', 'n') else bool(cur_manage))
                new_analytics = (
                    analytics_input == 'y' if analytics_input in ('y', 'n') else bool(cur_analytics))

                cursor.execute('''
                    UPDATE ta_assignments
                    SET can_grade = ?, can_manage_assignments = ?,
                        can_view_analytics = ?, updated_at = ?
                    WHERE id = ?
                ''', (int(new_grade), int(new_manage), int(new_analytics),
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ta_id))

                conn.commit()
                print(f"\nPermissions updated for TA assignment #{ta_id}.")
                print(f"  Grade:     {'Yes' if new_grade else 'No'}")
                print(f"  Manage:    {'Yes' if new_manage else 'No'}")
                print(f"  Analytics: {'Yes' if new_analytics else 'No'}")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error configuring TA permissions: {e}")

    def _remove_ta_assignment(self):
        """Remove (deactivate) a TA assignment"""
        try:
            ta_id_str = input("TA assignment ID to remove: ").strip()
            if not ta_id_str:
                return

            try:
                ta_id = int(ta_id_str)
            except ValueError:
                print("Invalid assignment ID.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT ta_user_id, module_code, section
                    FROM ta_assignments
                    WHERE id = ? AND is_active = 1
                ''', (ta_id,))
                record = cursor.fetchone()

                if not record:
                    print(f"Active TA assignment #{ta_id} not found.")
                    return

                ta_user, mod, section = record
                print(f"Remove TA {ta_user} from {mod}"
                      f"{' section ' + section if section else ''}? (y/n): ", end='')
                confirm = input().strip().lower()
                if confirm != 'y':
                    print("Cancelled.")
                    return

                cursor.execute('''
                    UPDATE ta_assignments
                    SET is_active = 0, updated_at = ?
                    WHERE id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ta_id))
                conn.commit()
                print(f"TA assignment #{ta_id} removed.")

            finally:
                conn.close()

        except Exception as e:
            print(f"Error removing TA assignment: {e}")
