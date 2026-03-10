import os
import re
import datetime
from typing import Dict, List, Optional

from education_system.university_system.utils.logging.log_config import configure_logging
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = configure_logging(name=__name__)


class ValidationMixin:
    """Mixin providing validation and data cleaning methods."""

    def get_import_file_path(self, file_type: str) -> Optional[str]:
        """Get the file path for import with validation"""
        while True:
            file_path = input(_t("shared.utils.batch_operations.prompt_file_path", file_type=file_type))

            if not os.path.exists(file_path):
                print(_t("shared.utils.batch_operations.error_file_not_found", path=file_path))
                retry = input(_t("shared.utils.batch_operations.prompt_try_again"))
                if retry.lower() != 'y':
                    return None
            else:
                return file_path

    def validate_student_data(self, student_data: Dict, is_update: bool = False) -> List[str]:
        """Enhanced validation with more comprehensive checks"""
        errors = []

        # If this is an update, student_id is required
        if is_update and (not student_data.get('student_id') or not student_data['student_id']):
            errors.append(_t("batch_ops.validation.student_id_required"))
            return errors

        # Only validate fields that are present and not empty
        if not is_update:
            # For new records, check required fields
            required_fields = ['first_name', 'last_name', 'gender', 'dob', 'course']
            for field in required_fields:
                if field not in student_data or not student_data[field]:
                    errors.append(f"Required field '{field}' is missing or empty")

        # Enhanced validation rules

        # Name validation
        if student_data.get('first_name'):
            if len(str(student_data['first_name']).strip()) < 2:
                errors.append(_t("batch_ops.validation.first_name_too_short"))
            if not re.match(r"^[a-zA-Z\s\-']+$", str(student_data['first_name'])):
                errors.append(_t("batch_ops.validation.first_name_invalid_chars"))

        if student_data.get('last_name'):
            if len(str(student_data['last_name']).strip()) < 2:
                errors.append(_t("batch_ops.validation.last_name_too_short"))
            if not re.match(r"^[a-zA-Z\s\-']+$", str(student_data['last_name'])):
                errors.append(_t("batch_ops.validation.last_name_invalid_chars"))

        # Gender validation
        if student_data.get('gender') and student_data['gender']:
            if str(student_data['gender']).lower() not in ['male', 'female', 'other', 'm', 'f', 'o']:
                errors.append(_t("batch_ops.validation.gender_invalid"))

        # DOB validation
        if student_data.get('dob') and student_data['dob']:
            try:
                dob = datetime.datetime.strptime(str(student_data['dob']), "%Y-%m-%d")
                today = datetime.datetime.now()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

                if age < 16 or age > 100:
                    errors.append(_t("batch_ops.validation.age_out_of_range"))
                if dob > today:
                    errors.append(_t("batch_ops.validation.dob_in_future"))
            except ValueError:
                errors.append(_t("batch_ops.validation.dob_format_invalid"))

        # Course validation
        if student_data.get('course') and student_data['course']:
            if str(student_data['course']).upper() not in ['CS', 'DS']:
                errors.append(_t("batch_ops.validation.course_invalid"))

        # Email validation
        if student_data.get('email_address') and student_data['email_address']:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, str(student_data['email_address'])):
                errors.append(_t("batch_ops.validation.email_invalid"))

        # Phone validation (if present)
        if student_data.get('phone_number') and student_data['phone_number']:
            phone = re.sub(r'[^\d+]', '', str(student_data['phone_number']))
            if len(phone) < 10 or len(phone) > 15:
                errors.append(_t("batch_ops.validation.phone_invalid"))

        return errors

    def clean_student_data(self, student_data: Dict) -> Dict:
        """Clean and standardize student data"""
        cleaned = {}

        for key, value in student_data.items():
            if value is None or value == '':
                cleaned[key] = value
                continue

            str_value = str(value).strip()

            # Clean names
            if key in ['first_name', 'middle_name', 'last_name']:
                cleaned[key] = ' '.join(word.capitalize() for word in str_value.split())

            # Clean gender
            elif key == 'gender':
                gender_map = {'m': 'male', 'f': 'female', 'o': 'other'}
                cleaned[key] = gender_map.get(str_value.lower(), str_value.lower())

            # Clean course
            elif key == 'course':
                cleaned[key] = str_value.upper()

            # Clean email
            elif key == 'email_address':
                cleaned[key] = str_value.lower()

            # Clean phone
            elif key == 'phone_number':
                # Remove all non-digit characters except +
                cleaned[key] = re.sub(r'[^\d+]', '', str_value)

            else:
                cleaned[key] = str_value

        return cleaned

    def display_validation_errors(self, error_records: List[Dict], max_display: int = 10):
        """Display validation errors in a formatted way"""
        print("\n" + _t("shared.utils.batch_operations.records_with_errors", count=min(len(error_records), max_display)))
        print("-" * 80)

        for i, record in enumerate(error_records[:max_display], 1):
            print(f"\n{i}. {_t('shared.utils.batch_operations.row')}: {record['row']}")
            print(f"   {_t('shared.utils.batch_operations.name')}: {record['data'].get('first_name', 'N/A')} {record['data'].get('last_name', 'N/A')}")
            print(f"   {_t('shared.utils.batch_operations.errors')}: {'; '.join(record['errors'])}")

        if len(error_records) > max_display:
            print("\n" + _t("shared.utils.batch_operations.and_more_errors", count=len(error_records) - max_display))

    def validate_and_clean_data(self):
        """Validate and clean existing data in database"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        print("\n" + _t("shared.utils.batch_operations.title_validate_clean"))

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all students
            cursor.execute("SELECT * FROM students")
            students = cursor.fetchall()

            print(_t("shared.utils.batch_operations.analyzing_students", count=len(students)))

            issues = []
            fixed_count = 0

            from .models import ProgressTracker
            progress = ProgressTracker(len(students), "Validating data")

            for student in students:
                student_issues = []

                # Check email format
                email = student[1]
                if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                    student_issues.append(_t("batch_ops.quality_validation.email_format"))

                # Check names
                first_name = student[3]
                last_name = student[5]
                if not first_name or len(first_name.strip()) < 2:
                    student_issues.append(_t("batch_ops.quality_validation.first_name_invalid"))
                if not last_name or len(last_name.strip()) < 2:
                    student_issues.append(_t("batch_ops.quality_validation.last_name_invalid"))

                # Check gender
                gender = student[6]
                if gender not in ['male', 'female', 'other']:
                    student_issues.append(_t("batch_ops.quality_validation.gender_invalid"))

                # Check DOB and age consistency
                dob_str = student[7]
                age = student[8]
                try:
                    dob = datetime.datetime.strptime(dob_str, "%Y-%m-%d")
                    calculated_age = datetime.datetime.now().year - dob.year
                    if abs(calculated_age - age) > 1:
                        student_issues.append(_t("batch_ops.quality_validation.age_dob_inconsistent"))

                        # Auto-fix age disabled - student updates centralized
                        student_issues.append(_t("batch_ops.quality_validation.age_update_skipped"))

                except ValueError:
                    student_issues.append(_t("batch_ops.quality_validation.dob_format_invalid"))

                # Check course
                course = student[9]
                if course not in ['CS', 'DS']:
                    student_issues.append(_t("batch_ops.quality_validation.course_invalid"))

                if student_issues:
                    issues.append({
                        'student_id': student[0],
                        'name': f"{first_name} {last_name}",
                        'issues': student_issues
                    })

                progress.update()

            conn.commit()

            print("\n" + _t("shared.utils.batch_operations.validation_complete_summary"))
            print(_t("shared.utils.batch_operations.records_with_issues", count=len(issues)))
            print(_t("shared.utils.batch_operations.auto_fixes_applied", count=fixed_count))

            if issues:
                print("\n" + _t("shared.utils.batch_operations.first_issues_found"))
                for i, issue in enumerate(issues[:10], 1):
                    print(f"{i}. {_t('shared.utils.batch_operations.student')} {issue['student_id']} ({issue['name']}): {', '.join(issue['issues'])}")

                if len(issues) > 10:
                    print(_t("shared.utils.batch_operations.and_more_issues", count=len(issues) - 10))

                # Export issues report
                import json
                filename = f"data_quality_issues_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    json.dump(issues, f, indent=2)
                print(_t("shared.utils.batch_operations.issues_report_saved", filename=filename))

        except sqlite3.Error as e:
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()
