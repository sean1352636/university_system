from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import json


class TemplatesMixin:
    def save_schedule_template(self, template_name, description=""):
        """Save current schedule as a template"""
        try:
            with get_connection(self.db_path, row_factory=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Get all current schedules
                cursor.execute('''
                SELECT module_code, day_of_week, start_time, end_time,
                       room_id, instructor_id, session_type
                FROM module_schedule
                ORDER BY module_code, day_of_week, start_time
                ''')

                schedules = cursor.fetchall()

                # Convert to JSON
                template_data = []
                for schedule in schedules:
                    template_data.append({
                        'module_code': schedule[0],
                        'day_of_week': schedule[1],
                        'start_time': schedule[2],
                        'end_time': schedule[3],
                        'room_id': schedule[4],
                        'instructor_id': schedule[5],
                        'session_type': schedule[6]
                    })

                template_json = json.dumps(template_data, indent=2)

                cursor.execute('''
                INSERT INTO schedule_templates (template_name, description, template_data, created_by)
                VALUES (?, ?, ?, ?)
                ''', (template_name, description, template_json, 'admin'))

                print(f"Schedule template '{template_name}' saved successfully.")
                return True

        except sqlite3.IntegrityError:
            print(f"Template name '{template_name}' already exists.")
            return False
        except Exception as e:
            print(f"Error saving template: {e}")
            return False

    def load_schedule_template(self, template_name, clear_existing=False):
        """Load schedules from a template"""
        try:
            with get_connection(self.db_path, row_factory=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute('''
                SELECT template_data FROM schedule_templates WHERE template_name = ?
                ''', (template_name,))

                result = cursor.fetchone()
                if not result:
                    print(f"Template '{template_name}' not found.")
                    return False

                template_data = json.loads(result[0])

                if clear_existing:
                    confirm = input("This will delete all existing schedules. Continue? (y/n): ")
                    if confirm.lower() == 'y':
                        cursor.execute('DELETE FROM module_schedule')
                        print("Existing schedules cleared.")
                    else:
                        return False

                success_count = 0
                error_count = 0

                for schedule in template_data:
                    try:
                        cursor.execute('''
                        INSERT INTO module_schedule
                        (module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (schedule['module_code'], schedule['day_of_week'], schedule['start_time'],
                              schedule['end_time'], schedule['room_id'], schedule['instructor_id'],
                              schedule['session_type']))
                        success_count += 1
                    except Exception as e:
                        print(f"Error loading schedule: {e}")
                        error_count += 1

                print(f"Template loaded: {success_count} schedules added, {error_count} errors")

                # Log the action
                self._log_system_action('template_load', f"Loaded template '{template_name}'")

                return True

        except Exception as e:
            print(f"Error loading template: {e}")
            return False

    def list_schedule_templates(self):
        """List all saved schedule templates"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT template_name, description, created_date, created_by
        FROM schedule_templates
        ORDER BY created_date DESC
        ''')

        templates = cursor.fetchall()
        conn.close()

        if not templates:
            print("No schedule templates found.")
            return []

        print("\nSchedule Templates:")
        print("=" * 80)
        print(f"{'Name':<20} {'Description':<30} {'Created':<15} {'By':<10}")
        print("-" * 80)

        for template in templates:
            name, desc, created, created_by = template
            created_date = datetime.fromisoformat(created).strftime("%Y-%m-%d")
            print(f"{name:<20} {desc[:28]:<30} {created_date:<15} {created_by:<10}")

        print("=" * 80)
        return templates
