import os
import csv
import json
import datetime
from typing import Dict, List

import pandas as pd

from education_system.university_system.utils.logging.log_config import configure_logging
from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.modules.domain.academics.services.modules import (
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2, optional_module_3, optional_module_4,
    CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
    DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4,
)
from education_system.university_system.modules.shared.utils.batch_operations.models import ImportResult, ProgressTracker

logger = configure_logging(name=__name__)


class DbOperationsMixin:
    """Mixin providing database import/update/module operations."""

    def import_valid_records(self, records: List[Dict]) -> ImportResult:
        """Import valid records with comprehensive tracking and error handling"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        result = ImportResult()
        result.start_time = datetime.datetime.now()
        result.total_records = len(records)

        if not records:
            result.end_time = datetime.datetime.now()
            return result

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get module information
            general_modules = {
                "1": optional_module_1,
                "2": optional_module_2,
                "3": optional_module_3,
                "4": optional_module_4,
            }

            cs_modules = {
                "1": CS_optional_module_1,
                "2": CS_optional_module_2,
                "3": CS_optional_module_3,
                "4": CS_optional_module_4,
            }

            ds_modules = {
                "1": DS_optional_module_1,
                "2": DS_optional_module_2,
                "3": DS_optional_module_3,
                "4": DS_optional_module_4,
            }

            # Progress tracking
            progress = ProgressTracker(len(records), "Importing records")

            for i, record in enumerate(records):
                try:
                    # Generate student ID
                    student_id = str(int(datetime.datetime.now().timestamp() * 1000000 + i) % 10000000).zfill(7)

                    # Create email if not provided
                    email_address = record.get('email_address') or f"C{student_id}@tees.ac.uk"

                    # Set title based on gender
                    gender = record['gender'].lower()
                    title = {'male': 'Mr', 'female': 'Miss'}.get(gender, '?')

                    # Calculate age
                    dob = datetime.datetime.strptime(str(record['dob']), "%Y-%m-%d")
                    now = datetime.datetime.now()
                    age = now.year - dob.year - ((now.month, now.day) < (dob.month, dob.day))

                    # Student creation has been centralized - raise error
                    raise ValueError("Student creation via batch operations has been disabled. "
                                   "Please use main GUI (Student Management menu) or CLI to create students. "
                                   "This ensures consistent student data across all modules.")

                    # Insert modules
                    course = record['course'].upper()
                    course_modules = cs_modules if course == 'CS' else ds_modules

                    module_data = [
                        (student_id, compulsory_module_1['code']),
                        (student_id, compulsory_module_2['code']),
                        (student_id, general_modules["1"]['code']),
                        (student_id, general_modules["2"]['code']),
                        (student_id, course_modules["1"]['code']),
                        (student_id, course_modules["2"]['code'])
                    ]

                    cursor.executemany('''
                    INSERT INTO student_modules (student_id, module_code)
                    VALUES (?, ?)
                    ''', module_data)

                    result.successful_imports += 1

                except Exception as e:
                    error_info = {
                        'record_index': i,
                        'student_data': record,
                        'error': str(e)
                    }
                    result.errors.append(error_info)
                    result.failed_imports += 1
                    logger.error(f"Error importing record {i}: {e}")

                progress.update()

                # Save progress periodically for resume capability
                if (i + 1) % 100 == 0:
                    remaining_records = records[i+1:]
                    self.save_import_progress(remaining_records, len(records), f"import_resume_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl")

            conn.commit()
            print("\n" + _t("shared.utils.batch_operations.import_success", count=result.successful_imports))

            if result.failed_imports > 0:
                print(_t("shared.utils.batch_operations.import_failed", count=result.failed_imports))

        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error during import: {e}")
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
            result.failed_imports = len(records)
        finally:
            conn.close()
            result.end_time = datetime.datetime.now()

        return result

    def save_import_progress(self, remaining_records: List[Dict], original_total: int, filename: str):
        """Save import progress for resume capability"""
        try:
            progress_data = {
                'remaining_records': remaining_records,
                'original_total': original_total,
                'timestamp': datetime.datetime.now().isoformat(),
                'original_file': getattr(self, 'current_import_file', 'unknown')
            }

            with open(filename, 'w') as f:
                json.dump(progress_data, f, default=str)

        except Exception as e:
            logger.error(f"Error saving import progress: {e}")

    def save_import_history(self, result: ImportResult, file_path: str, operation_type: str):
        """Save import operation to history"""
        history_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'operation_type': operation_type,
            'file_path': file_path,
            'total_records': result.total_records,
            'successful_imports': result.successful_imports,
            'failed_imports': result.failed_imports,
            'duplicates_found': result.duplicates_found,
            'duplicates_skipped': result.duplicates_skipped,
            'duplicates_updated': result.duplicates_updated,
            'duration_seconds': (result.end_time - result.start_time).total_seconds() if result.end_time and result.start_time else 0,
            'errors': result.errors[:10]  # Store only first 10 errors
        }

        self.import_history.append(history_entry)

        # Save to file
        try:
            with open('import_history.json', 'w') as f:
                json.dump(self.import_history[-100:], f, indent=2)  # Keep last 100 entries
        except Exception as e:
            logger.error(f"Error saving import history: {e}")

    def batch_update_records(self):
        """Enhanced batch update with better error handling"""
        print("\n" + _t("shared.utils.batch_operations.title_batch_update"))

        file_type = input(_t("shared.utils.batch_operations.prompt_file_type"))
        if file_type not in ['1', '2']:
            print(_t("shared.utils.batch_operations.invalid_choice"))
            return

        file_format = 'CSV' if file_type == '1' else 'Excel'
        file_path = self.get_import_file_path(file_format)
        if not file_path:
            return

        # Create backup before updates
        backup_path = self.create_database_backup(auto=True)
        print(_t("shared.utils.batch_operations.backup_created", path=backup_path))

        try:
            # Read file
            records = []
            if file_type == '1':  # CSV
                with open(file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
                    reader = csv.DictReader(csvfile)
                    reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames]

                    if 'student_id' not in reader.fieldnames:
                        print(_t("shared.utils.batch_operations.error_student_id_required"))
                        return

                    records = list(reader)
            else:  # Excel
                df = pd.read_excel(file_path)
                df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]

                if 'student_id' not in df.columns:
                    print(_t("shared.utils.batch_operations.error_student_id_required"))
                    return

                records = df.to_dict('records')
                records = [{k: (None if pd.isna(v) else v) for k, v in record.items()} for record in records]

            # Validate records
            valid_records = []
            error_records = []

            progress = ProgressTracker(len(records), "Validating update records")

            for i, record in enumerate(records):
                cleaned_record = self.clean_student_data(record)
                errors = self.validate_student_data(cleaned_record, is_update=True)

                if errors:
                    error_records.append({
                        'row': i + 2,
                        'data': cleaned_record,
                        'errors': errors
                    })
                else:
                    valid_records.append(cleaned_record)

                progress.update()

            print("\n" + _t("shared.utils.batch_operations.validation_stats", valid=len(valid_records), errors=len(error_records)))

            if error_records:
                self.display_validation_errors(error_records)

                proceed = input("\n" + _t("shared.utils.batch_operations.prompt_proceed_valid_only"))
                if proceed.lower() != 'y':
                    print(_t("shared.utils.batch_operations.update_cancelled"))
                    return

            if valid_records:
                result = self.update_batch_records(valid_records)
                self.save_import_history(result, file_path, 'Batch Update')
            else:
                print(_t("shared.utils.batch_operations.no_valid_records_update"))

        except Exception as e:
            logger.error(f"Error processing update file: {e}")
            print(_t("shared.utils.batch_operations.error_processing", error=str(e)))

    def update_batch_records(self, records: List[Dict]) -> ImportResult:
        """Enhanced batch update with comprehensive tracking"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        result = ImportResult()
        result.start_time = datetime.datetime.now()
        result.total_records = len(records)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            progress = ProgressTracker(len(records), "Updating records")

            for record in records:
                try:
                    student_id = record['student_id']

                    # Check if student exists
                    cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
                    existing_student = cursor.fetchone()

                    if not existing_student:
                        result.errors.append({
                            'student_id': student_id,
                            'error': 'Student not found'
                        })
                        result.failed_imports += 1
                        progress.update()
                        continue

                    # Build update query
                    update_fields = []
                    update_values = []

                    field_mapping = {
                        'email_address': 'email_address',
                        'first_name': 'first_name',
                        'middle_name': 'middle_name',
                        'last_name': 'last_name',
                        'gender': 'gender',
                        'dob': 'dob',
                        'course': 'course'
                    }

                    for file_field, db_field in field_mapping.items():
                        if file_field in record and record[file_field] is not None and str(record[file_field]).strip():
                            update_fields.append(f"{db_field} = ?")
                            update_values.append(record[file_field])

                    # Update title if gender changed
                    if 'gender' in record and record['gender']:
                        gender = str(record['gender']).lower()
                        title_map = {'male': 'Mr', 'female': 'Miss', 'other': '?'}
                        if gender in title_map:
                            update_fields.append("title = ?")
                            update_values.append(title_map[gender])

                    # Update age if DOB changed
                    if 'dob' in record and record['dob']:
                        dob = datetime.datetime.strptime(str(record['dob']), "%Y-%m-%d")
                        now = datetime.datetime.now()
                        age = now.year - dob.year - ((now.month, now.day) < (dob.month, dob.day))
                        update_fields.append("age = ?")
                        update_values.append(age)

                    if update_fields:
                        # Student updates have been centralized - raise error
                        raise ValueError("Student updates via batch operations have been disabled. "
                                       "Please use main GUI (Student Management menu) or CLI to update students. "
                                       "This ensures consistent student data across all modules.")

                except Exception as e:
                    result.errors.append({
                        'student_id': record.get('student_id', 'unknown'),
                        'error': str(e)
                    })
                    result.failed_imports += 1
                    logger.error(f"Error updating student {record.get('student_id', 'unknown')}: {e}")

                progress.update()

            conn.commit()
            print("\n" + _t("shared.utils.batch_operations.update_success", count=result.successful_imports))

            if result.failed_imports > 0:
                print(_t("shared.utils.batch_operations.update_failed", count=result.failed_imports))

        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error during batch update: {e}")
            print(_t("shared.utils.batch_operations.database_error_update", error=str(e)))
        finally:
            conn.close()
            result.end_time = datetime.datetime.now()

        return result

    def update_student_modules(self, cursor, student_id: str, new_course: str):
        """Update student modules when course changes"""
        try:
            # Delete old course-specific modules by their codes
            old_module_codes = [
                CS_optional_module_1['code'], CS_optional_module_2['code'],
                CS_optional_module_3['code'], CS_optional_module_4['code'],
                DS_optional_module_1['code'], DS_optional_module_2['code'],
                DS_optional_module_3['code'], DS_optional_module_4['code']
            ]
            placeholders = ','.join('?' * len(old_module_codes))
            assert all(c in '?,' for c in placeholders), "Invalid placeholder string"
            cursor.execute(f'''
            DELETE FROM student_modules
            WHERE student_id = ? AND module_code IN ({placeholders})
            ''', [student_id] + old_module_codes)

            # Insert new course modules
            if new_course == 'CS':
                module_data = [
                    (student_id, CS_optional_module_1['code']),
                    (student_id, CS_optional_module_2['code'])
                ]
            else:  # DS
                module_data = [
                    (student_id, DS_optional_module_1['code']),
                    (student_id, DS_optional_module_2['code'])
                ]

            cursor.executemany('''
            INSERT INTO student_modules (student_id, module_code)
            VALUES (?, ?)
            ''', module_data)

        except Exception as e:
            logger.error(f"Error updating modules for student {student_id}: {e}")

    def bulk_module_operations(self):
        """Bulk module assignment and management"""
        print("\n" + _t("shared.utils.batch_operations.title_bulk_module"))

        print("\n" + _t("shared.utils.batch_operations.options"))
        print(_t("shared.utils.batch_operations.option_add_module"))
        print(_t("shared.utils.batch_operations.option_remove_module"))
        print(_t("shared.utils.batch_operations.option_replace_module"))
        print(_t("shared.utils.batch_operations.option_import_enrollments"))

        choice = input(_t("shared.utils.batch_operations.prompt_choose_1_4"))

        if choice == '1':
            self.bulk_add_modules()
        elif choice == '2':
            self.bulk_remove_modules()
        elif choice == '3':
            self.bulk_replace_modules()
        elif choice == '4':
            self.import_module_enrollments()
        else:
            print(_t("shared.utils.batch_operations.invalid_choice"))

    def bulk_add_modules(self):
        """Add modules to multiple students"""
        print("\n" + _t("shared.utils.batch_operations.title_bulk_add"))

        # Get students to update
        filter_choice = input(_t("shared.utils.batch_operations.prompt_select_students"))

        student_ids = []
        if filter_choice == '1':
            course = input(_t("shared.utils.batch_operations.prompt_enter_course")).upper()
            if course in ['CS', 'DS']:
                student_ids = self.get_students_by_course(course)
            else:
                print(_t("shared.utils.batch_operations.invalid_course"))
                return
        elif filter_choice == '2':
            file_path = self.get_import_file_path('CSV or text file with student IDs')
            if file_path:
                student_ids = self.read_student_ids_from_file(file_path)
        elif filter_choice == '3':
            student_ids = self.get_all_student_ids()
        else:
            print(_t("shared.utils.batch_operations.invalid_choice"))
            return

        if not student_ids:
            print(_t("shared.utils.batch_operations.no_students_found"))
            return

        print(_t("shared.utils.batch_operations.found_students", count=len(student_ids)))

        # Get module to add
        module_code = input(_t("shared.utils.batch_operations.prompt_module_code"))
        module_name = input(_t("shared.utils.batch_operations.prompt_module_name"))
        module_type = input(_t("shared.utils.batch_operations.prompt_module_type"))

        # Confirm operation
        confirm = input(_t("shared.utils.batch_operations.confirm_add_module", code=module_code, count=len(student_ids)))
        if confirm.lower() != 'y':
            return

        # Execute bulk add
        self.execute_bulk_module_operation('add', student_ids, module_code, module_name, module_type)

    def bulk_remove_modules(self):
        """Remove modules from multiple students"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        print("\n" + _t("shared.utils.batch_operations.title_bulk_remove"))

        module_code = input(_t("shared.utils.batch_operations.prompt_module_code_remove"))

        # Find students with this module
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT DISTINCT student_id FROM student_modules
            WHERE module_code = ?
            ''', (module_code,))

            student_ids = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not student_ids:
                print(_t("shared.utils.batch_operations.no_students_with_module", code=module_code))
                return

            print(_t("shared.utils.batch_operations.students_with_module", count=len(student_ids), code=module_code))

            confirm = input(_t("shared.utils.batch_operations.confirm_remove_module", code=module_code, count=len(student_ids)))
            if confirm.lower() == 'y':
                self.execute_bulk_module_operation('remove', student_ids, module_code)

        except sqlite3.Error as e:
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))

    def bulk_replace_modules(self):
        """Replace one module with another for multiple students"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        print("\n" + _t("shared.utils.batch_operations.title_bulk_replace"))

        old_module = input(_t("shared.utils.batch_operations.prompt_module_code_replace"))
        new_module_code = input(_t("shared.utils.batch_operations.prompt_new_module_code"))
        new_module_name = input(_t("shared.utils.batch_operations.prompt_new_module_name"))
        new_module_type = input(_t("shared.utils.batch_operations.prompt_new_module_type"))

        # Find students with old module
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT DISTINCT student_id FROM student_modules
            WHERE module_code = ?
            ''', (old_module,))

            student_ids = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not student_ids:
                print(_t("shared.utils.batch_operations.no_students_with_module", code=old_module))
                return

            print(_t("shared.utils.batch_operations.students_with_module", count=len(student_ids), code=old_module))

            confirm = input(_t("shared.utils.batch_operations.confirm_replace_module", old=old_module, new=new_module_code, count=len(student_ids)))
            if confirm.lower() == 'y':
                # Remove old module
                self.execute_bulk_module_operation('remove', student_ids, old_module)
                # Add new module
                self.execute_bulk_module_operation('add', student_ids, new_module_code, new_module_name, new_module_type)

        except sqlite3.Error as e:
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))

    def import_module_enrollments(self):
        """Import module enrollments from file"""
        print("\n" + _t("shared.utils.batch_operations.title_import_enrollments"))

        file_path = self.get_import_file_path('CSV file (student_id, module_code, module_name, module_type)')
        if not file_path:
            return

        try:
            enrollments = []
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames]

                required_fields = ['student_id', 'module_code', 'module_name', 'module_type']
                missing_fields = [f for f in required_fields if f not in reader.fieldnames]

                if missing_fields:
                    print(_t("shared.utils.batch_operations.missing_required_fields", fields=', '.join(missing_fields)))
                    return

                enrollments = list(reader)

            print(_t("shared.utils.batch_operations.found_enrollment_records", count=len(enrollments)))

            confirm = input(_t("shared.utils.batch_operations.prompt_import_enrollments"))
            if confirm.lower() == 'y':
                self.process_module_enrollments(enrollments)

        except Exception as e:
            print(_t("shared.utils.batch_operations.error_reading_file", error=str(e)))

    def execute_bulk_module_operation(self, operation: str, student_ids: List[str], module_code: str, module_name: str = None, module_type: str = None):
        """Execute bulk module operations"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            progress = ProgressTracker(len(student_ids), f"{operation.title()}ing modules")

            success_count = 0

            for student_id in student_ids:
                try:
                    if operation == 'add':
                        cursor.execute('''
                        INSERT OR IGNORE INTO student_modules (student_id, module_code)
                        VALUES (?, ?)
                        ''', (student_id, module_code))

                    elif operation == 'remove':
                        cursor.execute('''
                        DELETE FROM student_modules
                        WHERE student_id = ? AND module_code = ?
                        ''', (student_id, module_code))

                    if cursor.rowcount > 0:
                        success_count += 1

                except sqlite3.Error as e:
                    logger.error(f"Error {operation}ing module for student {student_id}: {e}")

                progress.update()

            conn.commit()
            print("\n" + _t("shared.utils.batch_operations.module_operation_success", operation=operation, count=success_count))

        except sqlite3.Error as e:
            conn.rollback()
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()

    def import_grade_data(self):
        """Import student grades and academic records"""
        print("\n" + _t("shared.utils.batch_operations.title_import_grades"))

        file_path = self.get_import_file_path('CSV file (student_id, module_code, grade, semester, year)')
        if not file_path:
            return

        try:
            grades = []
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames]

                required_fields = ['student_id', 'module_code', 'grade']
                missing_fields = [f for f in required_fields if f not in reader.fieldnames]

                if missing_fields:
                    print(_t("shared.utils.batch_operations.missing_required_fields", fields=', '.join(missing_fields)))
                    return

                for row in reader:
                    # Validate grade
                    try:
                        grade_value = float(row['grade'])
                        if 0 <= grade_value <= 100:
                            grades.append(row)
                        else:
                            print(_t("shared.utils.batch_operations.invalid_grade_value", grade=grade_value, student_id=row['student_id']))
                    except ValueError:
                        print(_t("shared.utils.batch_operations.invalid_grade_format", grade=row['grade'], student_id=row['student_id']))

            print(_t("shared.utils.batch_operations.found_grade_records", count=len(grades)))

            if grades:
                confirm = input(_t("shared.utils.batch_operations.prompt_import_grades"))
                if confirm.lower() == 'y':
                    self.process_grade_data(grades)

        except Exception as e:
            print(_t("shared.utils.batch_operations.error_reading_grade_file", error=str(e)))

    def process_grade_data(self, grades: List[Dict]):
        """Process and import grade data"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create grades table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                module_code TEXT,
                grade REAL,
                semester TEXT,
                year TEXT,
                import_date TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')

            progress = ProgressTracker(len(grades), "Importing grades")
            success_count = 0

            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for grade_record in grades:
                try:
                    cursor.execute('''
                    INSERT INTO student_grades (student_id, module_code, grade, semester, year, import_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        grade_record['student_id'],
                        grade_record['module_code'],
                        float(grade_record['grade']),
                        grade_record.get('semester', ''),
                        grade_record.get('year', ''),
                        current_time
                    ))
                    success_count += 1

                except sqlite3.Error as e:
                    logger.error(f"Error importing grade for student {grade_record['student_id']}: {e}")

                progress.update()

            conn.commit()
            print("\n" + _t("shared.utils.batch_operations.grades_import_success", count=success_count))

        except sqlite3.Error as e:
            conn.rollback()
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()

    def get_students_by_course(self, course: str) -> List[str]:
        """Get student IDs by course"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT student_id FROM students WHERE course = ?", (course,))
            student_ids = [row[0] for row in cursor.fetchall()]

            conn.close()
            return student_ids

        except sqlite3.Error as e:
            logger.error(f"Error getting students by course: {e}")
            return []

    def get_all_student_ids(self) -> List[str]:
        """Get all student IDs"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT student_id FROM students")
            student_ids = [row[0] for row in cursor.fetchall()]

            conn.close()
            return student_ids

        except sqlite3.Error as e:
            logger.error(f"Error getting all student IDs: {e}")
            return []

    def read_student_ids_from_file(self, file_path: str) -> List[str]:
        """Read student IDs from a text or CSV file"""
        student_ids = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.lower().endswith('.csv'):
                    reader = csv.reader(f)
                    for row in reader:
                        if row:  # Skip empty rows
                            student_ids.append(row[0].strip())
                else:
                    # Treat as text file with one ID per line
                    for line in f:
                        student_id = line.strip()
                        if student_id:
                            student_ids.append(student_id)

            # Remove duplicates while preserving order
            seen = set()
            unique_ids = []
            for sid in student_ids:
                if sid not in seen:
                    seen.add(sid)
                    unique_ids.append(sid)

            return unique_ids

        except Exception as e:
            logger.error(f"Error reading student IDs from file: {e}")
            return []

    def process_module_enrollments(self, enrollments: List[Dict]):
        """Process module enrollment data"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            progress = ProgressTracker(len(enrollments), "Processing enrollments")
            success_count = 0
            error_count = 0

            for enrollment in enrollments:
                try:
                    # Check if student exists
                    cursor.execute("SELECT student_id FROM students WHERE student_id = ?",
                                 (enrollment['student_id'],))
                    if not cursor.fetchone():
                        error_count += 1
                        logger.warning(f"Student {enrollment['student_id']} not found")
                        continue

                    # Insert enrollment
                    cursor.execute('''
                    INSERT OR IGNORE INTO student_modules (student_id, module_code)
                    VALUES (?, ?)
                    ''', (
                        enrollment['student_id'],
                        enrollment['module_code']
                    ))

                    if cursor.rowcount > 0:
                        success_count += 1

                except sqlite3.Error as e:
                    error_count += 1
                    logger.error(f"Error enrolling student {enrollment['student_id']}: {e}")

                progress.update()

            conn.commit()
            print("\n" + _t("shared.utils.batch_operations.enrollments_processed", count=success_count))
            if error_count > 0:
                print(_t("shared.utils.batch_operations.enrollments_failed", count=error_count))

        except sqlite3.Error as e:
            conn.rollback()
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()

    def update_existing_record(self, student_id: str, new_data: Dict):
        """Update an existing student record"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build update query
            update_fields = []
            update_values = []

            field_mapping = {
                'email_address': 'email_address',
                'first_name': 'first_name',
                'middle_name': 'middle_name',
                'last_name': 'last_name',
                'gender': 'gender',
                'dob': 'dob',
                'course': 'course'
            }

            for file_field, db_field in field_mapping.items():
                if file_field in new_data and new_data[file_field] is not None:
                    update_fields.append(f"{db_field} = ?")
                    update_values.append(new_data[file_field])

            if update_fields:
                # Student updates have been centralized - raise error
                raise ValueError("Student updates have been disabled. "
                               "Please use main GUI or CLI for student management.")
                conn.commit()

                logger.info(f"Updated student {student_id}")

        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error updating student {student_id}: {e}")
        finally:
            conn.close()
