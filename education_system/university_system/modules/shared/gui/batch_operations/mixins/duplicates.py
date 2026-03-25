"""Duplicate detection and handling mixin."""

from education_system.university_system.modules.shared.gui.batch_operations.constants import (
    datetime, logging,
    Dict, List, Tuple,
    DEFAULT_DB_PATH,
    sqlite3, fuzz,
    logger,
)

from education_system.university_system.modules.shared.gui.batch_operations.models import ImportResult


class DuplicatesMixin:
    """Mixin providing duplicate detection, confidence scoring, and merge methods."""

    def find_duplicate_students(self, progress_callback=None) -> List[Dict]:
        """Find duplicates with progress reporting"""
        self.progress_callback = progress_callback

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM students ORDER BY last_name, first_name")
            students = cursor.fetchall()

            duplicates = []
            total_comparisons = len(students) * (len(students) - 1) // 2
            comparison_count = 0

            for i, student1 in enumerate(students):
                for j, student2 in enumerate(students[i+1:], i+1):
                    comparison_count += 1

                    # Update progress
                    if self.progress_callback and comparison_count % 100 == 0:
                        progress = int((comparison_count / total_comparisons) * 100)
                        self.progress_callback(progress, f"Comparing records... {comparison_count}/{total_comparisons}")

                    # Create fake import record for comparison
                    fake_record = {
                        'first_name': student2[3],
                        'last_name': student2[5],
                        'email_address': student2[1],
                        'dob': student2[7]
                    }

                    confidence = self.calculate_duplicate_confidence(fake_record, student1)

                    if confidence > 0.7:
                        duplicates.append({
                            'student1': {
                                'id': student1[0],
                                'name': f"{student1[3]} {student1[5]}",
                                'email': student1[1],
                                'dob': student1[7]
                            },
                            'student2': {
                                'id': student2[0],
                                'name': f"{student2[3]} {student2[5]}",
                                'email': student2[1],
                                'dob': student2[7]
                            },
                            'confidence': confidence
                        })

            if self.progress_callback:
                self.progress_callback(100, f"Duplicate detection complete: {len(duplicates)} potential duplicates found")

            conn.close()
            return duplicates

        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")
            raise

    def find_duplicates_in_import(self, records: List[Dict], progress_callback=None) -> List[Dict]:
        """Find potential duplicates in import data - GUI version with progress"""
        duplicates = []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                total = len(records)
                for i, record in enumerate(records):
                    if progress_callback and i % 10 == 0:
                        progress = int((i / total) * 100)
                        progress_callback(progress, f"Checking for duplicates: {i}/{total}")

                    # Check for existing student with same student_id or email
                    student_id = record.get('student_id', '')
                    email = record.get('email', '')

                    if student_id:
                        cursor.execute(
                            "SELECT * FROM students WHERE student_id = ?",
                            (student_id,)
                        )
                        existing = cursor.fetchone()
                        if existing:
                            confidence = self.calculate_duplicate_confidence(record, existing)
                            duplicates.append({
                                'import_record': record,
                                'existing_record': existing,
                                'confidence': confidence,
                                'match_type': 'student_id'
                            })
                            continue

                    if email:
                        cursor.execute(
                            "SELECT * FROM students WHERE email = ?",
                            (email,)
                        )
                        existing = cursor.fetchone()
                        if existing:
                            confidence = self.calculate_duplicate_confidence(record, existing)
                            duplicates.append({
                                'import_record': record,
                                'existing_record': existing,
                                'confidence': confidence,
                                'match_type': 'email'
                            })

                if progress_callback:
                    progress_callback(100, f"Found {len(duplicates)} potential duplicates")

                logger.info(f"Found {len(duplicates)} potential duplicates in import data")
                return duplicates

        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")
            raise

    def calculate_duplicate_confidence(self, import_record: Dict, existing_record: Tuple) -> float:
        """Calculate confidence score for duplicate matches using weighted scoring"""
        score = 0.0
        max_score = 0.0

        # Field weights (higher = more important for matching)
        weights = {
            'student_id': 40.0,
            'email': 30.0,
            'first_name': 10.0,
            'last_name': 10.0,
            'date_of_birth': 10.0
        }

        # Get column names from existing record (assuming it's from SELECT *)
        existing_dict = {
            'student_id': existing_record[0] if len(existing_record) > 0 else None,
            'first_name': existing_record[1] if len(existing_record) > 1 else None,
            'last_name': existing_record[2] if len(existing_record) > 2 else None,
            'date_of_birth': existing_record[3] if len(existing_record) > 3 else None,
            'email': existing_record[4] if len(existing_record) > 4 else None,
            'course': existing_record[5] if len(existing_record) > 5 else None,
        }

        # Compare each field
        for field, weight in weights.items():
            max_score += weight

            import_value = str(import_record.get(field, '')).lower().strip()
            existing_value = str(existing_dict.get(field, '')).lower().strip()

            if not import_value or not existing_value:
                continue

            # Exact match
            if import_value == existing_value:
                score += weight
            # Fuzzy match for names
            elif field in ['first_name', 'last_name']:
                similarity = fuzz.ratio(import_value, existing_value)
                score += (similarity / 100.0) * weight

        # Calculate percentage confidence
        confidence = (score / max_score * 100) if max_score > 0 else 0
        return round(confidence, 2)

    def handle_duplicates(self, records: List[Dict], duplicates: List[Dict],
                         choice: str, progress_callback=None) -> ImportResult:
        """Handle duplicate records based on user choice - GUI version"""
        result = ImportResult()
        result.total_records = len(records)

        # Build set of duplicate import records
        duplicate_ids = {dup['import_record'].get('student_id') for dup in duplicates}

        # Separate unique and duplicate records
        unique_records = [r for r in records if r.get('student_id') not in duplicate_ids]
        duplicate_records = [r for r in records if r.get('student_id') in duplicate_ids]

        try:
            # Import unique records first
            if unique_records:
                if progress_callback:
                    progress_callback(0, f"Importing {len(unique_records)} unique records...")
                unique_result = self.import_valid_records_with_progress(unique_records, 0)
                result.successful_imports += unique_result.successful_imports
                result.failed_imports += unique_result.failed_imports
                result.errors.extend(unique_result.errors)

            # Handle duplicates based on choice
            if choice == 'skip':
                result.duplicates_found = len(duplicate_records)
                if progress_callback:
                    progress_callback(100, f"Skipped {len(duplicate_records)} duplicates")

            elif choice in ['overwrite', 'update']:
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()

                    for i, dup in enumerate(duplicates):
                        if progress_callback and i % 5 == 0:
                            progress = 50 + int((i / len(duplicates)) * 50)
                            progress_callback(progress, f"Handling duplicates: {i}/{len(duplicates)}")

                        import_rec = dup['import_record']
                        student_id = import_rec.get('student_id')

                        try:
                            if choice == 'overwrite':
                                # Delete and re-insert
                                cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
                                cursor.execute(
                                    """INSERT INTO students (student_id, first_name, last_name, date_of_birth,
                                       email, phone_number, address, course, enrollment_date, status)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                    (
                                        student_id,
                                        import_rec.get('first_name'),
                                        import_rec.get('last_name'),
                                        import_rec.get('date_of_birth'),
                                        import_rec.get('email'),
                                        import_rec.get('phone_number'),
                                        import_rec.get('address'),
                                        import_rec.get('course', 'GENERAL'),
                                        import_rec.get('enrollment_date', datetime.date.today().isoformat()),
                                        import_rec.get('status', 'Active')
                                    )
                                )
                                result.successful_imports += 1

                            elif choice == 'update':
                                # Update only non-empty fields
                                update_fields = []
                                update_values = []
                                for field in ['first_name', 'last_name', 'email', 'phone_number', 'address', 'course']:
                                    if import_rec.get(field):
                                        update_fields.append(f"{field} = ?")
                                        update_values.append(import_rec[field])

                                if update_fields:
                                    update_values.append(student_id)
                                    cursor.execute(
                                        f"UPDATE students SET {', '.join(update_fields)} WHERE student_id = ?",
                                        update_values
                                    )
                                    result.successful_imports += 1

                        except Exception as e:
                            logger.error(f"Error handling duplicate {student_id}: {e}")
                            result.failed_imports += 1
                            result.errors.append({
                                'student_id': student_id,
                                'error': str(e)
                            })

                    conn.commit()
                    result.duplicates_found = len(duplicates)

                    if progress_callback:
                        progress_callback(100, f"Handled {len(duplicates)} duplicates")

            return result

        except Exception as e:
            logger.error(f"Error handling duplicates: {e}")
            raise

    def merge_students(self, keep_id: str, delete_id: str, keep_first: bool = True,
                      progress_callback=None) -> bool:
        """Merge two student records - GUI version"""
        try:
            if progress_callback:
                progress_callback(0, f"Merging students: {delete_id} \u2192 {keep_id}")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Verify both students exist
                cursor.execute("SELECT * FROM students WHERE student_id = ?", (keep_id,))
                keep_student = cursor.fetchone()

                cursor.execute("SELECT * FROM students WHERE student_id = ?", (delete_id,))
                delete_student = cursor.fetchone()

                if not keep_student or not delete_student:
                    raise ValueError("One or both student IDs not found")

                if progress_callback:
                    progress_callback(25, "Merging student data...")

                # Merge non-null fields if keep_first is False
                if not keep_first:
                    cursor.execute("""
                        UPDATE students
                        SET
                            email = COALESCE(email, ?),
                            phone_number = COALESCE(phone_number, ?),
                            address = COALESCE(address, ?)
                        WHERE student_id = ?
                    """, (
                        delete_student[4],  # email
                        delete_student[5],  # phone_number
                        delete_student[6],  # address
                        keep_id
                    ))

                if progress_callback:
                    progress_callback(50, "Updating related records...")

                # Update related records (grades, enrollments, etc.)
                related_tables = [
                    ('grades', 'student_id'),
                    ('student_modules', 'student_id'),
                    ('attendance', 'student_id'),
                    ('enrollments', 'student_id'),
                ]
                for table, col in related_tables:
                    try:
                        cursor.execute(
                            f"UPDATE {table} SET {col} = ? WHERE {col} = ?",
                            (keep_id, delete_id)
                        )
                    except Exception:
                        pass  # Table might not exist

                if progress_callback:
                    progress_callback(75, "Removing duplicate record...")

                # Delete any remaining FK references before deleting the student
                for table, col in related_tables:
                    try:
                        cursor.execute(f"DELETE FROM {table} WHERE {col} = ?", (delete_id,))
                    except Exception:
                        pass

                # Delete the duplicate student
                cursor.execute("DELETE FROM students WHERE student_id = ?", (delete_id,))

                conn.commit()

                if progress_callback:
                    progress_callback(100, f"Merge complete: {delete_id} merged into {keep_id}")

                logger.info(f"Successfully merged student {delete_id} into {keep_id}")
                return True

        except Exception as e:
            logger.error(f"Error merging students: {e}")
            raise
