"""Batch update operations mixin."""

from education_system.university_system.modules.shared.gui.batch_operations.constants import (
    datetime, logging,
    Dict, List,
    DEFAULT_DB_PATH,
    sqlite3,
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2, optional_module_3, optional_module_4,
    CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
    DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4,
    logger,
)

from education_system.university_system.modules.shared.gui.batch_operations.models import ImportResult
from education_system.university_system.core.sql_safety import validate_field_for_query

_VALID_STUDENT_UPDATE_FIELDS = frozenset({
    'first_name', 'middle_name', 'last_name', 'email', 'email_address',
    'phone_number', 'address', 'course', 'gender', 'dob', 'status',
})


class BatchUpdatesMixin:
    """Mixin providing batch update operations."""

    def batch_update_from_file(self, file_path: str, progress_callback=None) -> ImportResult:
        """Batch update with progress reporting"""
        self.progress_callback = progress_callback

        try:
            # Create backup
            backup_path = self.create_database_backup(auto=True)

            # Read file
            if file_path.lower().endswith('.csv'):
                records = self.read_csv_file(file_path)
            else:
                records = self.read_excel_file(file_path)

            if not records:
                raise ValueError("No valid records found in file")

            # Validate all records have student_id
            for record in records:
                if 'student_id' not in record or not record['student_id']:
                    raise ValueError("All records must have student_id for updates")

            result = self.update_batch_records_with_progress(records)
            self.save_import_history(result, file_path, 'Batch Update')
            return result

        except Exception as e:
            logger.error(f"Error in batch update: {e}")
            raise

    def update_batch_records_with_progress(self, records: List[Dict]) -> ImportResult:
        """Update records with progress reporting"""
        result = ImportResult()
        result.start_time = datetime.datetime.now()
        result.total_records = len(records)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            for i, record in enumerate(records):
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

                    if update_fields:
                        update_query = f"UPDATE students SET {', '.join(update_fields)} WHERE student_id = ?"
                        update_values.append(student_id)
                        cursor.execute(update_query, update_values)

                        if 'course' in record and record['course']:
                            self.update_student_modules(cursor, student_id, record['course'].upper())

                        result.successful_imports += 1

                except Exception as e:
                    result.errors.append({
                        'student_id': record.get('student_id', 'unknown'),
                        'error': str(e)
                    })
                    result.failed_imports += 1
                    logger.error(f"Error updating student {record.get('student_id', 'unknown')}: {e}")

                # Update progress
                if self.progress_callback and i % 5 == 0:
                    progress = int(((i + 1) / len(records)) * 100)
                    self.progress_callback(progress, f"Updating record {i+1}/{len(records)}")

            conn.commit()

            if self.progress_callback:
                self.progress_callback(100, f"Update complete: {result.successful_imports} records updated")

        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error during batch update: {e}")
            raise
        finally:
            conn.close()
            result.end_time = datetime.datetime.now()

        return result

    def batch_update_records(self, file_path: str = None, progress_callback=None) -> ImportResult:
        """Batch update records from file - GUI-friendly version

        If file_path is not provided, this can be used as a menu entry point
        """
        if file_path:
            return self.batch_update_from_file(file_path, progress_callback)
        else:
            # This is a menu entry point - the GUI should handle file selection
            logger.info("Batch update menu accessed - awaiting file selection")
            return ImportResult()

    def update_batch_records(self, records: List[Dict], progress_callback=None) -> ImportResult:
        """Execute batch update - wrapper for GUI compatibility"""
        return self.update_batch_records_with_progress(records)

    def update_student_modules(self, cursor, student_id: str, new_course: str):
        """Update student module enrollments when course changes.

        Modules are stored in the student_modules table, not as columns
        on the students table.
        """
        try:
            # Determine new modules based on course
            if new_course == 'COMPUTER SCIENCE':
                optional_modules = [CS_optional_module_1, CS_optional_module_2,
                                    CS_optional_module_3, CS_optional_module_4]
            elif new_course == 'DATA SCIENCE':
                optional_modules = [DS_optional_module_1, DS_optional_module_2,
                                    DS_optional_module_3, DS_optional_module_4]
            else:
                optional_modules = [optional_module_1, optional_module_2,
                                    optional_module_3, optional_module_4]

            compulsory_modules = [compulsory_module_1, compulsory_module_2]

            # Capture currently-enrolled modules so finance can cancel
            # unpaid fees for any that aren't being re-enrolled.
            prior_modules = [
                row[0] for row in cursor.execute(
                    "SELECT module_code FROM student_modules "
                    "WHERE student_id = ?", (student_id,)
                ).fetchall()
            ]

            # Remove existing module enrollments for this student
            cursor.execute(
                "DELETE FROM student_modules WHERE student_id = ?",
                (student_id,)
            )

            # Insert compulsory modules
            for mod in compulsory_modules:
                cursor.execute(
                    """INSERT INTO student_modules
                       (student_id, module_code, module_name, module_type, status)
                       VALUES (?, ?, ?, 'compulsory', 'enrolled')""",
                    (student_id, mod['code'], mod['name'])
                )

            # Insert optional modules
            for mod in optional_modules:
                cursor.execute(
                    """INSERT INTO student_modules
                       (student_id, module_code, module_name, module_type, status)
                       VALUES (?, ?, ?, 'optional', 'enrolled')""",
                    (student_id, mod['code'], mod['name'])
                )

            # Sync finance: cancel unpaid fees for dropped modules,
            # assess new ones. Best-effort.
            new_codes = {m['code']
                         for m in compulsory_modules + optional_modules}
            try:
                from education_system.university_system.modules.domain.finance.services.enrolment_fees import (
                    assess_module_enrolment_fee,
                    cancel_module_enrolment_fee,
                )
                for code in prior_modules:
                    if code not in new_codes:
                        cancel_module_enrolment_fee(student_id, code)
                for code in new_codes:
                    assess_module_enrolment_fee(student_id, code)
            except Exception:
                pass

            # Sync library holds.
            try:
                from education_system.university_system.modules.domain.commerce.textbooks.services.library_holds import (
                    place_holds_for_enrolment,
                    release_holds_for_drop,
                )
                for code in prior_modules:
                    if code not in new_codes:
                        release_holds_for_drop(student_id, code)
                for code in new_codes:
                    place_holds_for_enrolment(student_id, code)
            except Exception:
                pass

            # Sync derived timetable views.
            try:
                from education_system.university_system.modules.domain.academics.services.course_management.timetable_sync import (
                    sync_for_student_enrolment, clear_for_student_drop,
                )
                for code in prior_modules:
                    if code not in new_codes:
                        clear_for_student_drop(student_id, code)
                for code in new_codes:
                    sync_for_student_enrolment(student_id, code)
            except Exception:
                pass

            logger.info(f"Updated modules for student {student_id} to {new_course} track")

        except Exception as e:
            logger.error(f"Error updating student modules: {e}")
            raise

    def update_existing_record(self, student_id: str, new_data: Dict,
                              progress_callback=None) -> bool:
        """Update existing student record - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Updating student {student_id}...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Verify student exists
                cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
                existing = cursor.fetchone()

                if not existing:
                    raise ValueError(f"Student {student_id} not found")

                if progress_callback:
                    progress_callback(30, "Merging new data...")

                # Build UPDATE query with only provided fields
                update_fields = []
                update_values = []

                for field, value in new_data.items():
                    if field != 'student_id' and value is not None:  # Don't update student_id
                        validate_field_for_query(field, _VALID_STUDENT_UPDATE_FIELDS, "student field")
                        update_fields.append(f"{field} = ?")
                        update_values.append(value)

                if not update_fields:
                    if progress_callback:
                        progress_callback(100, "No fields to update")
                    return False

                update_values.append(student_id)
                query = f"UPDATE students SET {', '.join(update_fields)} WHERE student_id = ?"

                if progress_callback:
                    progress_callback(60, "Executing update...")

                cursor.execute(query, update_values)
                conn.commit()

                if progress_callback:
                    progress_callback(100, f"Updated {len(update_fields)} fields for student {student_id}")

                logger.info(f"Updated student {student_id} with {len(update_fields)} fields")
                return True

        except Exception as e:
            logger.error(f"Error updating existing record: {e}")
            raise
