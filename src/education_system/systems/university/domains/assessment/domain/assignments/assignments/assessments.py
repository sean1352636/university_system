from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime


ASSESSMENT_TYPES = ("exam", "quiz", "test", "project", "presentation", "practical")
ASSESSMENT_STATUSES = ("Active", "Draft", "Archived")


class AssessmentsMixin:
    """Mixin for non-submission assessments (exams, tests, presentations…).

    These live in the ``assessments`` table that Grade Tracking marks against
    and the module-grade calculation weights. Types and statuses match the
    GUI's Create Assessment form.
    """

    def _assessment_columns(self, conn):
        return {r[1] for r in conn.execute('PRAGMA table_info("assessments")')}

    def _module_weight_used(self, conn, module_code, exclude_id=None):
        archived = ("AND COALESCE(status, 'Active') <> 'Archived' "
                    if 'status' in self._assessment_columns(conn) else "")
        row = conn.execute(
            "SELECT COALESCE(SUM(weight), 0) FROM assessments WHERE module_code = ? "
            + archived + "AND assessment_id <> COALESCE(?, -1)",
            (module_code, exclude_id)).fetchone()
        return float(row[0] or 0)

    @staticmethod
    def _ask_choice(label, options, default):
        print(f"{label}: " + ", ".join(f"{i}. {o}" for i, o in enumerate(options, 1)))
        answer = input(f"Choice (default {default}): ").strip()
        if answer.isdigit() and 0 < int(answer) <= len(options):
            return options[int(answer) - 1]
        return default

    def create_assessment(self):
        """Create an exam, test, quiz, presentation, practical or project."""
        if not self._check_permission('manage_assignments'):
            return
        conn = sqlite3.connect(self.db_path)
        try:
            columns = self._assessment_columns(conn)
            if not columns:
                print("The assessments table has not been set up yet. Open Grade Tracking once to create it.")
                return
            modules = {r[0].lower(): r[0] for r in conn.execute(
                "SELECT module_code FROM modules WHERE module_code IS NOT NULL AND TRIM(module_code) <> ''")}
        finally:
            conn.close()

        print("\nCreate Assessment")
        print("=" * 50)
        code = input("Module code: ").strip()
        if code.lower() not in modules:
            print(f"Unknown module code '{code}'.")
            return
        module_code = modules[code.lower()]
        name = input("Assessment name: ").strip()
        if not name:
            print("Name cannot be empty.")
            return
        kind = self._ask_choice("Type", ASSESSMENT_TYPES, "exam")

        due = input("Date (YYYY-MM-DD HH:MM): ").strip()
        try:
            due_date = datetime.strptime(due, "%Y-%m-%d %H:%M").strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD HH:MM")
            return
        try:
            max_points = float(input("Maximum points (default 100): ").strip() or 100)
            weight = float(input("Weight in the module, % : ").strip())
            duration = int(input("Duration in minutes (0 if not timed): ").strip() or 0)
        except ValueError:
            print("Points, weight and duration must be numbers.")
            return
        if max_points <= 0 or not 0 < weight <= 100 or duration < 0:
            print("Points must be positive, weight between 0 and 100, duration not negative.")
            return
        description = input("Description: ").strip()
        status = self._ask_choice("Status", ASSESSMENT_STATUSES, "Active")

        conn = sqlite3.connect(self.db_path)
        try:
            used = self._module_weight_used(conn, module_code)
            if used + weight > 100.0001:
                print(f"Warning: {module_code} assessments would total {used + weight:g}% (over 100%).")
                if input("Save anyway? (y/n): ").strip().lower() != 'y':
                    return
            values = {
                'assessment_name': name, 'assessment_type': kind, 'module_code': module_code,
                'max_points': max_points, 'weight': weight, 'due_date': due_date,
                'description': description, 'duration_minutes': duration, 'status': status,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            # Older definitions of the table lack duration/status/updated_at.
            values = {k: v for k, v in values.items() if k in columns}
            cols = ", ".join(values)
            marks = ", ".join("?" for _ in values)
            cur = conn.execute(f"INSERT INTO assessments ({cols}) VALUES ({marks})",  # nosec B608 - whitelisted keys
                               tuple(values.values()))
            conn.commit()
            new_id = cur.lastrowid
        finally:
            conn.close()

        self._log_action('create', 'assessments', new_id, None, {'name': name, 'module': module_code})
        print(f"\nAssessment '{name}' created (ID {new_id}) for {module_code}, worth {weight:g}%.")
        if kind == 'exam':
            print("To book an exam room, use Exam Scheduling (or Create Assessment in the GUI).")

    def manage_assessments(self):
        """List assessments; edit, re-date, change status or delete one."""
        if not self._check_permission('manage_assignments'):
            return
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            if not self._assessment_columns(conn):
                print("No assessments table yet.")
                return
            module = input("Filter by module code (Enter for all): ").strip()
            sql = ("SELECT a.*, (SELECT COUNT(*) FROM grades g WHERE g.assessment_id = a.assessment_id) "
                   "AS graded FROM assessments a ")
            params = ()
            if module:
                sql += "WHERE a.module_code = ? "
                params = (module,)
            rows = [dict(r) for r in conn.execute(sql + "ORDER BY a.module_code, a.due_date", params)]
        finally:
            conn.close()
        if not rows:
            print("No assessments found.")
            return

        print(f"\n{'ID':<5} {'Module':<11} {'Name':<30} {'Type':<12} {'Date':<17} {'Weight':>7} {'Status':<9} {'Graded':>6}")
        print("-" * 104)
        for r in rows:
            print(f"{r['assessment_id']:<5} {str(r['module_code'])[:10]:<11} {str(r['assessment_name'])[:29]:<30} "
                  f"{str(r['assessment_type'])[:11]:<12} {str(r.get('due_date') or '')[:16]:<17} "
                  f"{float(r['weight'] or 0):>6g}% {str(r.get('status') or 'Active')[:8]:<9} {r['graded']:>6}")

        choice = input("\nAssessment ID to manage (Enter to go back): ").strip()
        chosen = next((r for r in rows if choice.isdigit() and r['assessment_id'] == int(choice)), None)
        if chosen is None:
            return
        print("\n1. Edit  2. Change status  3. Delete  0. Back")
        action = input("Choice: ").strip()
        aid = chosen['assessment_id']

        if action == '1':
            updates = {}
            name = input(f"Name [{chosen['assessment_name']}]: ").strip()
            if name:
                updates['assessment_name'] = name
            due = input(f"Date YYYY-MM-DD HH:MM [{str(chosen.get('due_date') or '')[:16]}]: ").strip()
            if due:
                try:
                    updates['due_date'] = datetime.strptime(due, "%Y-%m-%d %H:%M").strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    print("Invalid date; left unchanged.")
            for key, label in (('max_points', 'Maximum points'), ('weight', 'Weight %')):
                value = input(f"{label} [{chosen[key]:g}]: ").strip()
                if value:
                    try:
                        updates[key] = float(value)
                    except ValueError:
                        print(f"{label} must be a number; left unchanged.")
            desc = input(f"Description [{chosen.get('description') or ''}]: ").strip()
            if desc:
                updates['description'] = desc
            if 'weight' in updates and not 0 < updates['weight'] <= 100:
                print("Weight must be between 0 and 100; left unchanged.")
                del updates['weight']
            if 'max_points' in updates and chosen['graded'] and updates['max_points'] != chosen['max_points']:
                print(f"Note: {chosen['graded']} grade(s) were recorded out of {chosen['max_points']:g}; "
                      "their percentages will change.")
            self._update_assessment(aid, chosen['module_code'], updates)
        elif action == '2':
            status = self._ask_choice("Status", ASSESSMENT_STATUSES, chosen.get('status') or 'Active')
            self._update_assessment(aid, chosen['module_code'], {'status': status})
        elif action == '3':
            if chosen['graded']:
                print(f"This assessment has {chosen['graded']} recorded grade(s); archive it instead "
                      "(Change status → Archived) to keep them.")
                return
            if input(f"Delete '{chosen['assessment_name']}'? (y/n): ").strip().lower() == 'y':
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.execute("DELETE FROM assessments WHERE assessment_id = ?", (aid,))
                    conn.commit()
                finally:
                    conn.close()
                self._log_action('delete', 'assessments', aid)
                print("Assessment deleted.")

    def _update_assessment(self, assessment_id, module_code, updates):
        if not updates:
            print("Nothing changed.")
            return
        conn = sqlite3.connect(self.db_path)
        try:
            columns = self._assessment_columns(conn)
            if 'updated_at' in columns:
                updates['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            updates = {k: v for k, v in updates.items() if k in columns}
            if 'weight' in updates:
                total = self._module_weight_used(conn, module_code, assessment_id) + updates['weight']
                if total > 100.0001:
                    print(f"Warning: {module_code} assessments now total {total:g}% (over 100%).")
            assignments = ", ".join(f'"{k}" = ?' for k in updates)
            conn.execute(f"UPDATE assessments SET {assignments} WHERE assessment_id = ?",  # nosec B608 - column names come from PRAGMA
                         (*updates.values(), assessment_id))
            conn.commit()
        finally:
            conn.close()
        self._log_action('update', 'assessments', assessment_id, None, updates)
        print("Assessment updated.")
