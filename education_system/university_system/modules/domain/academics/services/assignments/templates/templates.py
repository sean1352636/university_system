from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
import json


class TemplatesMixin:
    """Mixin providing assignment template creation, usage, and management."""

    def create_assignment_template(self):
        """Create an assignment template"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nCreate Assignment Template")
            print("=" * 50)

            name = input("Template name: ").strip()
            if not name:
                print("Name cannot be empty.")
                return

            description = input("Description: ").strip()
            category = input("Category (e.g., Programming, Essay, Lab): ").strip()

            template_data = {
                'title_template': input("Title template (use {module}, {week} etc.): ").strip(),
                'description_template': input("Description template: ").strip(),
                'default_max_marks': input("Default max marks: ").strip(),
                'default_file_types': input("Default allowed file types: ").strip(),
                'default_max_size': input("Default max file size (MB): ").strip(),
                'instructions_template': input("Instructions template: ").strip()
            }

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO assignment_templates (name, description, template_data, category, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, description, json.dumps(template_data), category,
                  self.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            conn.close()

            print(f"Template '{name}' created successfully!")

        except Exception as e:
            print(f"Error creating template: {e}")

    def use_assignment_template(self):
        """Create assignment from template"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, name, description, category
            FROM assignment_templates
            WHERE is_active = 1
            ORDER BY category, name
            ''')

            templates = cursor.fetchall()

            if not templates:
                print("No templates available.")
                conn.close()
                return

            print("\nAvailable Templates:")
            for i, (tid, name, desc, category) in enumerate(templates, 1):
                print(f"{i}. {name} ({category})")
                if desc:
                    print(f"   Description: {desc}")

            choice = input("\nSelect template number: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(templates):
                    template_id = templates[index][0]
                    self._create_from_template(cursor, template_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")

            conn.close()

        except Exception as e:
            print(f"Error using template: {e}")

    def _create_from_template(self, cursor, template_id):
        """Create assignment from template"""
        cursor.execute('SELECT name, template_data FROM assignment_templates WHERE id = ?', (template_id,))
        result = cursor.fetchone()

        if not result:
            print("Template not found.")
            return

        template_name, template_data_json = result
        template_data = json.loads(template_data_json)

        print(f"Creating assignment from template: {template_name}")

        cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
        modules = cursor.fetchall()

        print("\nSelect module:")
        for i, (code, name) in enumerate(modules, 1):
            print(f"{i}. {code} - {name}")

        choice = input("Module number: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(modules):
                module_code = modules[index][0]

                title = input(f"Title [{template_data.get('title_template', '')}]: ").strip()
                if not title:
                    title = template_data.get('title_template', '').format(module=module_code, week='X')

                description = input(f"Description [{template_data.get('description_template', '')}]: ").strip()
                if not description:
                    description = template_data.get('description_template', '')

                max_marks = int(template_data.get('default_max_marks', 100))
                file_types = template_data.get('default_file_types', '')
                max_size = int(template_data.get('default_max_size', 10))
                instructions = template_data.get('instructions_template', '')

                due_date_str = input("Due date (YYYY-MM-DD HH:MM): ")
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO assignments
                (module_code, title, description, instructions, due_date, max_marks,
                 file_types_allowed, max_file_size_mb, template_id, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (module_code, title, description, instructions,
                      due_date.strftime('%Y-%m-%d %H:%M:%S'), max_marks, file_types, max_size,
                      template_id, self.auth.current_user['id'], timestamp, timestamp))

                cursor.execute('UPDATE assignment_templates SET usage_count = usage_count + 1 WHERE id = ?', (template_id,))

                cursor.connection.commit()
                print(f"Assignment '{title}' created from template!")

        except (ValueError, IndexError):
            print("Invalid selection.")
        except ValueError as e:
            print(f"Invalid date format: {e}")

    # API methods

    def create_template(self, template_name, template_data):
        """Create a new assignment template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            user_id = self._get_student_id()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            template_json = json.dumps(template_data)

            cursor.execute('''
                INSERT INTO assignment_templates (template_name, template_data, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (template_name, template_json, user_id, timestamp, timestamp))

            template_id = cursor.lastrowid
            conn.commit()
            self._log_action('create', 'assignment_templates', template_id)
            conn.close()

            print(f"Template created successfully! ID: {template_id}")
            return template_id

        except Exception as e:
            print(f"Error creating template: {e}")
            return None

    def edit_template(self, template_id, **kwargs):
        """Edit an existing template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            update_fields = []
            values = []

            if 'template_name' in kwargs:
                update_fields.append("template_name = ?")
                values.append(kwargs['template_name'])

            if 'template_data' in kwargs:
                update_fields.append("template_data = ?")
                values.append(json.dumps(kwargs['template_data']))

            if not update_fields:
                print("No valid fields to update")
                return False

            update_fields.append("updated_at = ?")
            values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            values.append(template_id)

            query = f"UPDATE assignment_templates SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)

            conn.commit()
            self._log_action('update', 'assignment_templates', template_id, kwargs)
            conn.close()

            print("Template updated successfully!")
            return True

        except Exception as e:
            print(f"Error editing template: {e}")
            return False

    def delete_template(self, template_id):
        """Delete a template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM assignment_templates WHERE id = ?', (template_id,))

            conn.commit()
            self._log_action('delete', 'assignment_templates', template_id)
            conn.close()

            print("Template deleted successfully!")
            return True

        except Exception as e:
            print(f"Error deleting template: {e}")
            return False

    def duplicate_template(self, template_id):
        """Duplicate an existing template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT template_name, template_data FROM assignment_templates WHERE id = ?', (template_id,))
            result = cursor.fetchone()

            if not result:
                print("Template not found")
                return None

            template_name, template_data = result
            new_name = f"{template_name} (Copy)"

            user_id = self._get_student_id()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO assignment_templates (template_name, template_data, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (new_name, template_data, user_id, timestamp, timestamp))

            new_id = cursor.lastrowid
            conn.commit()
            self._log_action('create', 'assignment_templates', new_id)
            conn.close()

            print(f"Template duplicated successfully! New ID: {new_id}")
            return new_id

        except Exception as e:
            print(f"Error duplicating template: {e}")
            return None

    def get_templates(self, created_by=None):
        """Get all templates, optionally filtered by creator"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if created_by:
                cursor.execute('SELECT * FROM assignment_templates WHERE created_by = ? ORDER BY created_at DESC', (created_by,))
            else:
                cursor.execute('SELECT * FROM assignment_templates ORDER BY created_at DESC')

            templates = cursor.fetchall()
            conn.close()
            return templates

        except Exception as e:
            print(f"Error retrieving templates: {e}")
            return []

    def save_template_from_assignment(self, assignment_id, template_name):
        """Save an assignment as a template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
            assignment = cursor.fetchone()

            if not assignment:
                print("Assignment not found")
                return None

            template_data = {
                'title': assignment[2],
                'description': assignment[3],
                'max_marks': assignment[5],
                'file_types_allowed': assignment[6],
                'max_file_size_mb': assignment[7],
                'assignment_type': assignment[11],
                'allow_late_submission': assignment[12],
                'late_penalty_per_day': assignment[13],
                'instructions': assignment[14]
            }

            return self.create_template(template_name, template_data)

        except Exception as e:
            print(f"Error saving template from assignment: {e}")
            return None
