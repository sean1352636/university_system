import csv
from typing import Dict, List

import pandas as pd

from education_system.university_system.core.i18n import get_text as _t


class TemplatesMixin:
    """Mixin providing import template generation methods."""

    def generate_import_template(self):
        """Enhanced template generation with more options"""
        print("\n" + _t("shared.utils.batch_operations.title_generate_template"))

        print(_t("shared.utils.batch_operations.template_types"))
        print(_t("shared.utils.batch_operations.template_new_student"))
        print(_t("shared.utils.batch_operations.template_student_update"))
        print(_t("shared.utils.batch_operations.template_module_enrollment"))
        print(_t("shared.utils.batch_operations.template_grade_import"))
        print(_t("shared.utils.batch_operations.template_custom"))

        template_type = input(_t("shared.utils.batch_operations.prompt_choose_template"))

        if template_type not in ['1', '2', '3', '4', '5']:
            print(_t("shared.utils.batch_operations.invalid_choice"))
            return

        file_format = input(_t("shared.utils.batch_operations.prompt_template_format"))
        if file_format not in ['1', '2']:
            print(_t("shared.utils.batch_operations.invalid_choice"))
            return

        # Define field sets for different templates
        template_fields = {
            '1': ['first_name', 'middle_name', 'last_name', 'gender', 'dob', 'course', 'email_address', 'phone_number'],
            '2': ['student_id', 'first_name', 'middle_name', 'last_name', 'gender', 'dob', 'course', 'email_address'],
            '3': ['student_id', 'module_code', 'module_name', 'module_type'],
            '4': ['student_id', 'module_code', 'grade', 'semester', 'year'],
            '5': []  # Custom - will be defined by user
        }

        if template_type == '5':
            print("\n" + _t("shared.utils.batch_operations.enter_field_names"))
            fields = []
            while True:
                field = input(_t("shared.utils.batch_operations.prompt_field_name")).strip()
                if not field:
                    break
                fields.append(field.lower().replace(' ', '_'))
        else:
            fields = template_fields[template_type]

        # Generate template
        template_names = {
            '1': 'new_students_template',
            '2': 'update_students_template',
            '3': 'module_enrollment_template',
            '4': 'grade_import_template',
            '5': 'custom_template'
        }

        extension = 'csv' if file_format == '1' else 'xlsx'
        filename = f"{template_names[template_type]}.{extension}"

        # Get output location
        output_path = input(_t("shared.utils.batch_operations.prompt_save_as", default=filename)).strip()
        if not output_path:
            output_path = filename

        try:
            self.create_template_file(fields, output_path, file_format, template_type)
            print(_t("shared.utils.batch_operations.template_created", path=output_path))

            # Show usage instructions
            self.show_template_instructions(template_type)

        except Exception as e:
            print(_t("shared.utils.batch_operations.error_creating_template", error=str(e)))

    def create_template_file(self, fields: List[str], filename: str, file_format: str, template_type: str):
        """Create template file with example data"""
        example_data = self.get_example_data(template_type)

        if file_format == '1':  # CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fields)
                writer.writeheader()

                # Add example row
                if example_data:
                    example_row = {field: example_data.get(field, '') for field in fields}
                    writer.writerow(example_row)
        else:  # Excel
            df = pd.DataFrame(columns=fields)

            if example_data:
                example_row = {field: example_data.get(field, '') for field in fields}
                df = df.append(example_row, ignore_index=True)

            df.to_excel(filename, index=False)

    def get_example_data(self, template_type: str) -> Dict:
        """Get example data for templates"""
        examples = {
            '1': {  # New students
                'first_name': 'John',
                'middle_name': 'William',
                'last_name': 'Doe',
                'gender': 'male',
                'dob': '1995-01-15',
                'course': 'CS',
                'email_address': 'john.doe@example.com',
                'phone_number': '+44123456789'
            },
            '2': {  # Student updates
                'student_id': '1234567',
                'first_name': 'John (leave blank to keep current)',
                'course': 'DS (to change course)'
            },
            '3': {  # Module enrollment
                'student_id': '1234567',
                'module_code': 'CS101',
                'module_name': 'Introduction to Programming',
                'module_type': 'compulsory'
            },
            '4': {  # Grades
                'student_id': '1234567',
                'module_code': 'CS101',
                'grade': '85.5',
                'semester': 'Fall',
                'year': '2024'
            }
        }

        return examples.get(template_type, {})

    def show_template_instructions(self, template_type: str):
        """Show usage instructions for templates"""
        instructions = {
            '1': [
                _t("batch_ops.instructions.new_student_title"),
                _t("batch_ops.instructions.required_fields"),
                _t("batch_ops.instructions.gender_values"),
                _t("batch_ops.instructions.dob_format"),
                _t("batch_ops.instructions.course_values"),
                _t("batch_ops.instructions.optional_fields")
            ],
            '2': [
                _t("batch_ops.instructions.update_title"),
                _t("batch_ops.instructions.student_id_required"),
                _t("batch_ops.instructions.update_partial"),
                _t("batch_ops.instructions.leave_blank"),
                _t("batch_ops.instructions.same_validation")
            ],
            '3': [
                _t("batch_ops.instructions.enrollment_title"),
                _t("batch_ops.instructions.student_id_exists"),
                _t("batch_ops.instructions.module_code_unique"),
                _t("batch_ops.instructions.module_types")
            ],
            '4': [
                _t("batch_ops.instructions.grade_title"),
                _t("batch_ops.instructions.grade_ids_required"),
                _t("batch_ops.instructions.grade_range"),
                _t("batch_ops.instructions.grade_optional_fields")
            ]
        }

        if template_type in instructions:
            print(f"\n\U0001f4cb {instructions[template_type][0]}")
            for instruction in instructions[template_type][1:]:
                print(f"   {instruction}")
