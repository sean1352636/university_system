"""Template generation mixin."""

from education_system.university_system.modules.shared.gui.batch_operations.constants import (
    csv, logging,
    Dict, List,
    pd,
    DATA_DIR,
    logger,
)


class TemplatesMixin:
    """Mixin providing import template generation and instruction display."""

    def create_template_file(self, fields: List[str], filename: str,
                            file_format: str, template_type: str,
                            include_examples: bool = True,
                            progress_callback=None) -> str:
        """Create import template file - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Creating {template_type} template...")

            # Create templates directory
            templates_dir = DATA_DIR / 'templates'
            templates_dir.mkdir(parents=True, exist_ok=True)

            # Ensure correct extension
            if file_format == 'csv' and not filename.endswith('.csv'):
                filename += '.csv'
            elif file_format == 'excel' and not filename.endswith('.xlsx'):
                filename += '.xlsx'

            template_path = templates_dir / filename

            if progress_callback:
                progress_callback(30, "Adding field headers...")

            if file_format == 'csv':
                with open(template_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(fields)

                    if include_examples:
                        example_data = self.get_example_data(template_type)
                        example_row = [example_data.get(field, '') for field in fields]
                        writer.writerow(example_row)

            elif file_format == 'excel':
                data = [fields]
                if include_examples:
                    example_data = self.get_example_data(template_type)
                    example_row = [example_data.get(field, '') for field in fields]
                    data.append(example_row)

                df = pd.DataFrame(data[1:] if include_examples else [], columns=fields)
                df.to_excel(template_path, index=False, engine='openpyxl')

            if progress_callback:
                progress_callback(100, f"Template created: {template_path}")

            logger.info(f"Created {template_type} template at {template_path}")
            return str(template_path)

        except Exception as e:
            logger.error(f"Error creating template file: {e}")
            raise

    def get_example_data(self, template_type: str) -> Dict:
        """Get example data for templates - GUI version"""
        examples = {
            'student': {
                'student_id': 'S12345',
                'first_name': 'John',
                'last_name': 'Smith',
                'date_of_birth': '2000-01-15',
                'email': 'john.smith@university.edu',
                'phone_number': '555-0123',
                'address': '123 Main St, City, State 12345',
                'course': 'COMPUTER SCIENCE',
                'enrollment_date': '2024-09-01',
                'status': 'Active'
            },
            'grade': {
                'student_id': 'S12345',
                'module_code': 'CS101',
                'grade': 'A',
                'grade_point': '4.0',
                'percentage': '92.5',
                'semester': 'Fall',
                'academic_year': '2024-2025'
            },
            'module': {
                'student_id': 'S12345',
                'module_type': 'optional_module_1',
                'module_code': 'CS201',
                'module_name': 'Data Structures'
            },
            'enrollment': {
                'student_id': 'S12345',
                'course_code': 'CS101',
                'semester': 'Fall',
                'academic_year': '2024-2025',
                'enrollment_status': 'Enrolled'
            }
        }

        return examples.get(template_type, {})

    def show_template_instructions_gui(self, template_type: str,
                                       callback=None) -> str:
        """Display template usage instructions - GUI version"""
        instructions = {
            'student': """
STUDENT IMPORT TEMPLATE INSTRUCTIONS

Required Fields:
- student_id: Unique student identifier (e.g., S12345)
- first_name: Student's first name
- last_name: Student's last name
- email: Valid email address (must contain @)
- course: Course enrollment (COMPUTER SCIENCE, DATA SCIENCE, etc.)

Optional Fields:
- date_of_birth: Format YYYY-MM-DD
- phone_number: Contact number
- address: Full address
- enrollment_date: Format YYYY-MM-DD (defaults to today)
- status: Active, Inactive, or Graduated (defaults to Active)

File Format:
- CSV: Comma-separated values
- Excel: .xlsx format
- First row must contain column headers
- One student per row

Validation Rules:
- student_id must be unique
- email must be valid format
- dates must be YYYY-MM-DD format
- course must match existing course codes
""",
            'grade': """
GRADE IMPORT TEMPLATE INSTRUCTIONS

Required Fields:
- student_id: Must match existing student
- module_code: Module identifier

Optional Fields:
- grade: Letter grade (A, B+, B, etc.)
- grade_point: Numeric grade point (0.0-4.0)
- percentage: Percentage score (0-100)
- semester: Fall, Spring, Summer
- academic_year: Format YYYY-YYYY

File Format:
- CSV or Excel (.xlsx)
- First row must contain column headers
- One grade record per row

Validation Rules:
- student_id must exist in system
- At least one of: grade, grade_point, or percentage required
- If provided, grade_point must be 0.0-4.0
- If provided, percentage must be 0-100
""",
            'module': """
MODULE ENROLLMENT TEMPLATE INSTRUCTIONS

Required Fields:
- student_id: Must match existing student
- module_type: Type of module (compulsory_module_1, optional_module_1, etc.)
- module_code: Module identifier

Optional Fields:
- module_name: Descriptive name of module

File Format:
- CSV or Excel (.xlsx)
- First row must contain column headers
- One enrollment per row

Valid Module Types:
- compulsory_module_1, compulsory_module_2
- optional_module_1, optional_module_2, optional_module_3, optional_module_4

Validation Rules:
- student_id must exist in system
- module_type must be valid
- module_code should match course requirements
"""
        }

        instruction_text = instructions.get(template_type,
                                           "No instructions available for this template type")

        if callback:
            callback(instruction_text)

        return instruction_text
