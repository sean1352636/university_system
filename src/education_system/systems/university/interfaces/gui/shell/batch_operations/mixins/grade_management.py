"""Grade management mixin."""

from education_system.systems.university.interfaces.gui.shell.batch_operations.constants import (
    csv, logging,
    Dict, List,
    logger,
)

from education_system.systems.university.interfaces.gui.shell.batch_operations.models import ImportResult


class GradeManagementMixin:
    """Mixin providing grade import and processing methods."""

    def import_grade_data_from_file(self, file_path: str, progress_callback=None) -> ImportResult:
        """Import grade data from a CSV file and process it."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                grades = list(reader)
            return self.process_grade_data(grades, progress_callback)
        except Exception as e:
            result = ImportResult()
            result.errors.append({'error': str(e)})
            return result

    def process_grade_data(self, grades: List[Dict], progress_callback=None) -> ImportResult:
        """Process and validate grade data - GUI version with progress tracking

        Expected fields: student_id, module_code, grade, grade_point, percentage
        """
        try:
            result = ImportResult()
            result.total_records = len(grades)

            if progress_callback:
                progress_callback(0, f"Processing {len(grades)} grade records...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Ensure grades table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS grades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        module_code TEXT NOT NULL,
                        grade TEXT,
                        grade_point REAL,
                        percentage REAL,
                        semester TEXT,
                        academic_year TEXT,
                        recorded_date TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(student_id)
                    )
                """)

                for i, grade_record in enumerate(grades):
                    student_id = grade_record.get('student_id')
                    module_code = grade_record.get('module_code')
                    grade = grade_record.get('grade')
                    grade_point = grade_record.get('grade_point')
                    percentage = grade_record.get('percentage')

                    # Validate required fields
                    if not student_id or not module_code:
                        result.failed_imports += 1
                        result.errors.append({
                            'row': i + 2,
                            'error': 'Missing student_id or module_code',
                            'data': grade_record
                        })
                        continue

                    # Verify student exists
                    cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,))
                    if not cursor.fetchone():
                        result.failed_imports += 1
                        result.errors.append({
                            'row': i + 2,
                            'error': f'Student {student_id} not found',
                            'data': grade_record
                        })
                        continue

                    try:
                        # Insert or update grade
                        cursor.execute("""
                            INSERT OR REPLACE INTO grades
                            (student_id, module_code, grade, grade_point, percentage, semester, academic_year)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            student_id,
                            module_code,
                            grade,
                            grade_point,
                            percentage,
                            grade_record.get('semester'),
                            grade_record.get('academic_year')
                        ))
                        result.successful_imports += 1

                    except Exception as e:
                        result.failed_imports += 1
                        result.errors.append({
                            'row': i + 2,
                            'error': str(e),
                            'data': grade_record
                        })

                    if progress_callback and i % 10 == 0:
                        progress = int((i / len(grades)) * 100)
                        progress_callback(progress, f"Processing: {i}/{len(grades)}")

                conn.commit()

            if progress_callback:
                progress_callback(100, f"Complete: {result.successful_imports} grades processed")

            logger.info(f"Processed {result.successful_imports} grade records")
            return result

        except Exception as e:
            logger.error(f"Error processing grade data: {e}")
            raise
