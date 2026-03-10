"""Bulk module operations mixin."""

from education_system.university_system.modules.shared.gui.batch_operations.constants import (
    logging,
    Dict, List,
    logger,
)

from education_system.university_system.modules.shared.gui.batch_operations.models import ImportResult
from education_system.university_system.core.sql_safety import validate_field_for_query

_VALID_MODULE_TYPES = frozenset({
    'compulsory_module_1', 'compulsory_module_2',
    'optional_module_1', 'optional_module_2', 'optional_module_3', 'optional_module_4',
})


def _validate_module_type(module_type: str) -> str:
    """Validate module_type is an allowed column name."""
    return validate_field_for_query(module_type, _VALID_MODULE_TYPES, "module type")


class ModuleOperationsMixin:
    """Mixin providing bulk module add/remove/replace and enrollment import methods."""

    def bulk_add_modules(self, module_code: str, module_name: str, module_type: str,
                        student_ids: List[str] = None, course: str = None,
                        progress_callback=None) -> int:
        """Add module to multiple students - GUI version with progress tracking"""
        _validate_module_type(module_type)
        try:
            updated_count = 0

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get student list
                if student_ids:
                    placeholders = ','.join('?' * len(student_ids))
                    cursor.execute(
                        f"SELECT student_id FROM students WHERE student_id IN ({placeholders})",
                        student_ids
                    )
                elif course:
                    cursor.execute("SELECT student_id FROM students WHERE course = ?", (course,))
                else:
                    cursor.execute("SELECT student_id FROM students")

                students = cursor.fetchall()
                total = len(students)

                if progress_callback:
                    progress_callback(0, f"Adding module to {total} students...")

                # Update each student
                for i, (student_id,) in enumerate(students):
                    try:
                        cursor.execute(
                            f"UPDATE students SET {module_type} = ? WHERE student_id = ?",
                            (module_code, student_id)
                        )
                        updated_count += 1

                        if progress_callback and i % 10 == 0:
                            progress = int((i / total) * 100)
                            progress_callback(progress, f"Updating: {i}/{total}")

                    except Exception as e:
                        logger.error(f"Error adding module to student {student_id}: {e}")

                conn.commit()

                if progress_callback:
                    progress_callback(100, f"Complete: {updated_count} students updated")

                logger.info(f"Bulk added module {module_code} to {updated_count} students")
                return updated_count

        except Exception as e:
            logger.error(f"Error in bulk_add_modules: {e}")
            raise

    def bulk_remove_modules(self, module_type: str, student_ids: List[str] = None,
                           course: str = None, progress_callback=None) -> int:
        """Remove module from multiple students - GUI version"""
        _validate_module_type(module_type)
        try:
            updated_count = 0

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get student list
                if student_ids:
                    placeholders = ','.join('?' * len(student_ids))
                    cursor.execute(
                        f"SELECT student_id FROM students WHERE student_id IN ({placeholders})",
                        student_ids
                    )
                elif course:
                    cursor.execute("SELECT student_id FROM students WHERE course = ?", (course,))
                else:
                    cursor.execute("SELECT student_id FROM students")

                students = cursor.fetchall()
                total = len(students)

                if progress_callback:
                    progress_callback(0, f"Removing module from {total} students...")

                # Update each student
                for i, (student_id,) in enumerate(students):
                    try:
                        cursor.execute(
                            f"UPDATE students SET {module_type} = NULL WHERE student_id = ?",
                            (student_id,)
                        )
                        updated_count += 1

                        if progress_callback and i % 10 == 0:
                            progress = int((i / total) * 100)
                            progress_callback(progress, f"Updating: {i}/{total}")

                    except Exception as e:
                        logger.error(f"Error removing module from student {student_id}: {e}")

                conn.commit()

                if progress_callback:
                    progress_callback(100, f"Complete: {updated_count} students updated")

                logger.info(f"Bulk removed {module_type} from {updated_count} students")
                return updated_count

        except Exception as e:
            logger.error(f"Error in bulk_remove_modules: {e}")
            raise

    def bulk_replace_modules(self, module_type: str, old_module_code: str,
                            new_module_code: str, new_module_name: str,
                            student_ids: List[str] = None, course: str = None,
                            progress_callback=None) -> int:
        """Replace one module with another for multiple students - GUI version"""
        _validate_module_type(module_type)
        try:
            updated_count = 0

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get students with the old module
                if student_ids:
                    placeholders = ','.join('?' * len(student_ids))
                    cursor.execute(
                        f"SELECT student_id FROM students WHERE {module_type} = ? AND student_id IN ({placeholders})",
                        [old_module_code] + student_ids
                    )
                elif course:
                    cursor.execute(
                        f"SELECT student_id FROM students WHERE {module_type} = ? AND course = ?",
                        (old_module_code, course)
                    )
                else:
                    cursor.execute(
                        f"SELECT student_id FROM students WHERE {module_type} = ?",
                        (old_module_code,)
                    )

                students = cursor.fetchall()
                total = len(students)

                if progress_callback:
                    progress_callback(0, f"Replacing module for {total} students...")

                # Update each student
                for i, (student_id,) in enumerate(students):
                    try:
                        cursor.execute(
                            f"UPDATE students SET {module_type} = ? WHERE student_id = ?",
                            (new_module_code, student_id)
                        )
                        updated_count += 1

                        if progress_callback and i % 10 == 0:
                            progress = int((i / total) * 100)
                            progress_callback(progress, f"Updating: {i}/{total}")

                    except Exception as e:
                        logger.error(f"Error replacing module for student {student_id}: {e}")

                conn.commit()

                if progress_callback:
                    progress_callback(100, f"Complete: {updated_count} students updated")

                logger.info(f"Bulk replaced {old_module_code} with {new_module_code} for {updated_count} students")
                return updated_count

        except Exception as e:
            logger.error(f"Error in bulk_replace_modules: {e}")
            raise

    def import_module_enrollments(self, file_path: str, progress_callback=None) -> ImportResult:
        """Import module enrollments from file - GUI version"""
        try:
            result = ImportResult()

            # Read file
            if file_path.endswith('.csv'):
                records = self.read_csv_file(file_path)
            else:
                records = self.read_excel_file(file_path)

            result.total_records = len(records)

            if progress_callback:
                progress_callback(0, f"Processing {len(records)} module enrollments...")

            # Validate and process records
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                for i, record in enumerate(records):
                    student_id = record.get('student_id')
                    module_type = record.get('module_type')
                    module_code = record.get('module_code')

                    # Validate required fields
                    if not student_id or not module_type or not module_code:
                        result.failed_imports += 1
                        result.errors.append({
                            'row': i + 2,
                            'error': 'Missing required fields',
                            'data': record
                        })
                        continue

                    # Check if student exists
                    cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,))
                    if not cursor.fetchone():
                        result.failed_imports += 1
                        result.errors.append({
                            'row': i + 2,
                            'error': f'Student {student_id} not found',
                            'data': record
                        })
                        continue

                    try:
                        # Validate module_type from CSV input
                        _validate_module_type(module_type)
                        # Update module enrollment
                        cursor.execute(
                            f"UPDATE students SET {module_type} = ? WHERE student_id = ?",
                            (module_code, student_id)
                        )
                        result.successful_imports += 1

                    except Exception as e:
                        result.failed_imports += 1
                        result.errors.append({
                            'row': i + 2,
                            'error': str(e),
                            'data': record
                        })

                    if progress_callback and i % 10 == 0:
                        progress = int((i / len(records)) * 100)
                        progress_callback(progress, f"Processing: {i}/{len(records)}")

                conn.commit()

            if progress_callback:
                progress_callback(100, f"Complete: {result.successful_imports} enrollments imported")

            self.save_import_history(result, file_path, 'Module Enrollment Import')
            logger.info(f"Imported {result.successful_imports} module enrollments from {file_path}")

            return result

        except Exception as e:
            logger.error(f"Error importing module enrollments: {e}")
            raise

    def process_module_enrollments(self, enrollments: List[Dict],
                                   progress_callback=None) -> ImportResult:
        """Process module enrollment records - GUI version"""
        return self.import_module_enrollments_from_list(enrollments, progress_callback)

    def import_module_enrollments_from_list(self, enrollments: List[Dict],
                                           progress_callback=None) -> ImportResult:
        """Helper to import module enrollments from list - GUI version"""
        try:
            result = ImportResult()
            result.total_records = len(enrollments)

            if progress_callback:
                progress_callback(0, f"Processing {len(enrollments)} enrollments...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                for i, enrollment in enumerate(enrollments):
                    student_id = enrollment.get('student_id')
                    module_type = enrollment.get('module_type')
                    module_code = enrollment.get('module_code')

                    # Validate required fields
                    if not all([student_id, module_type, module_code]):
                        result.failed_imports += 1
                        result.errors.append({
                            'row': i + 1,
                            'error': 'Missing required fields',
                            'data': enrollment
                        })
                        continue

                    # Verify student exists
                    cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,))
                    if not cursor.fetchone():
                        result.failed_imports += 1
                        result.errors.append({
                            'row': i + 1,
                            'error': f'Student {student_id} not found',
                            'data': enrollment
                        })
                        continue

                    try:
                        # Validate module_type before SQL use
                        _validate_module_type(module_type)
                        # Update enrollment
                        cursor.execute(
                            f"UPDATE students SET {module_type} = ? WHERE student_id = ?",
                            (module_code, student_id)
                        )
                        result.successful_imports += 1

                    except Exception as e:
                        result.failed_imports += 1
                        result.errors.append({
                            'row': i + 1,
                            'error': str(e),
                            'data': enrollment
                        })

                    if progress_callback and i % 10 == 0:
                        progress = int((i / len(enrollments)) * 100)
                        progress_callback(progress, f"Processing: {i}/{len(enrollments)}")

                conn.commit()

            if progress_callback:
                progress_callback(100, f"Complete: {result.successful_imports} enrollments processed")

            logger.info(f"Processed {result.successful_imports} module enrollments")
            return result

        except Exception as e:
            logger.error(f"Error processing module enrollments: {e}")
            raise
