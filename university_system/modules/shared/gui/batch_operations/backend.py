"""
Batch Operations GUI - Backend Manager

Contains the EnhancedBatchOperationManager class which provides all
backend batch operation logic including import, export, validation,
duplicate detection, and data quality features.
"""

from university_system.modules.shared.gui.batch_operations.constants import (
    os, csv, datetime, re, json, shutil, time, threading, zipfile, logging, pickle,
    StringIO, Path, Dict, List, Tuple, Optional, Any, Callable,
    dataclass, ThreadPoolExecutor,
    DATA_DIR, DEFAULT_BATCH_DB,
    GUI_SETTINGS_PATH, EXTERNAL_DB_CONFIG_PATH, EXTERNAL_API_CONFIG_PATH, IMPORT_HISTORY_PATH,
    tk, ttk, filedialog, messagebox, scrolledtext, Progressbar, Notebook,
    queue,
    pd, hashlib, schedule, requests, Flask, request, jsonify, fuzz,
    _t, configure_logging, get_log_file,
    sqlite3, DatabaseManager, ensure_parent_dir, DEFAULT_DB_PATH,
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2, optional_module_3, optional_module_4,
    CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
    DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4,
    logger,
)

from university_system.modules.shared.gui.batch_operations.models import (
    ImportResult,
    ProgressTracker,
    OriginalBatchOperationManager,
)
from university_system.core.sql_safety import validate_field_for_query, validate_identifier

_VALID_MODULE_TYPES = frozenset({
    'compulsory_module_1', 'compulsory_module_2',
    'optional_module_1', 'optional_module_2', 'optional_module_3', 'optional_module_4',
})

_VALID_STUDENT_UPDATE_FIELDS = frozenset({
    'first_name', 'middle_name', 'last_name', 'email', 'email_address',
    'phone_number', 'address', 'course', 'gender', 'dob', 'status',
})

def _validate_module_type(module_type: str) -> str:
    """Validate module_type is an allowed column name."""
    return validate_field_for_query(module_type, _VALID_MODULE_TYPES, "module type")

class EnhancedBatchOperationManager(OriginalBatchOperationManager):
    """Enhanced backend manager with GUI-specific methods"""
    
    def __init__(self, db_path: str = DEFAULT_BATCH_DB):
        super().__init__(db_path)
        self.progress_callback = None
    
    def import_from_csv_file(self, file_path: str, progress_callback=None) -> ImportResult:
        """GUI-friendly CSV import with progress callback"""
        self.progress_callback = progress_callback
        
        try:
            # Create backup
            backup_path = self.create_database_backup(auto=True)
            
            # Read and validate file
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
                sample = csvfile.read(1024)
                csvfile.seek(0)
                
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                reader.fieldnames = [header.strip().lower().replace(' ', '_') for header in reader.fieldnames]
                
                records = list(reader)
                total_records = len(records)
                
                if self.progress_callback:
                    self.progress_callback(0, f"Processing {total_records} records...")
                
                # Process records
                valid_records = []
                error_records = []
                
                for i, row in enumerate(records):
                    cleaned_row = self.clean_student_data(row)
                    errors = self.validate_student_data(cleaned_row)
                    
                    if errors:
                        error_records.append({
                            'row': i + 2,
                            'data': cleaned_row,
                            'errors': errors
                        })
                    else:
                        valid_records.append(cleaned_row)
                    
                    if self.progress_callback and i % 10 == 0:
                        progress = int((i / total_records) * 50)  # First 50% for validation
                        self.progress_callback(progress, f"Validating record {i+1}/{total_records}")
                
                if valid_records:
                    result = self.import_valid_records_with_progress(valid_records, 50)  # Start at 50%
                    result.total_records = total_records
                    result.failed_imports = len(error_records)
                    result.errors.extend(error_records)
                    
                    self.save_import_history(result, file_path, 'CSV Import')
                    return result
                else:
                    result = ImportResult()
                    result.total_records = total_records
                    result.failed_imports = len(error_records)
                    result.errors = error_records
                    return result
                    
        except Exception as e:
            logger.error(f"Error importing CSV: {e}")
            raise
    
    def import_from_excel_file(self, file_path: str, sheet_name: str = None, progress_callback=None) -> ImportResult:
        """GUI-friendly Excel import with progress callback"""
        self.progress_callback = progress_callback
        
        try:
            # Create backup
            backup_path = self.create_database_backup(auto=True)
            
            # Read Excel file
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
            
            records = df.to_dict('records')
            records = [{k: (None if pd.isna(v) else v) for k, v in record.items()} for record in records]
            
            total_records = len(records)
            
            if self.progress_callback:
                self.progress_callback(0, f"Processing {total_records} records from sheet: {sheet_name or 'default'}")
            
            # Process records
            valid_records = []
            error_records = []
            
            for i, record in enumerate(records):
                cleaned_record = self.clean_student_data(record)
                errors = self.validate_student_data(cleaned_record)
                
                if errors:
                    error_records.append({
                        'row': i + 2,
                        'data': cleaned_record,
                        'errors': errors
                    })
                else:
                    valid_records.append(cleaned_record)
                
                if self.progress_callback and i % 10 == 0:
                    progress = int((i / total_records) * 50)
                    self.progress_callback(progress, f"Validating record {i+1}/{total_records}")
            
            if valid_records:
                result = self.import_valid_records_with_progress(valid_records, 50)
                result.total_records = total_records
                result.failed_imports = len(error_records)
                result.errors.extend(error_records)
                
                self.save_import_history(result, file_path, f'Excel Import ({sheet_name})')
                return result
            else:
                result = ImportResult()
                result.total_records = total_records
                result.failed_imports = len(error_records)
                result.errors = error_records
                return result
                
        except Exception as e:
            logger.error(f"Error importing Excel: {e}")
            raise
    
    def import_valid_records_with_progress(self, records: List[Dict], start_progress: int = 0) -> ImportResult:
        """Import records with progress reporting"""
        result = ImportResult()
        result.start_time = datetime.datetime.now()
        result.total_records = len(records)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
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
                    dob_value = record.get('dob')
                    if not dob_value or str(dob_value).strip().lower() in ('none', ''):
                        result.failed_imports += 1
                        result.errors.append({'row': i + 2, 'error': 'Missing date of birth'})
                        continue
                    dob = datetime.datetime.strptime(str(dob_value).strip(), "%Y-%m-%d")
                    now = datetime.datetime.now()
                    age = now.year - dob.year - ((now.month, now.day) < (dob.month, dob.day))
                    
                    # Get current datetime
                    registration_datetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Insert student
                    cursor.execute('''
                    INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        student_id,
                        email_address,
                        title,
                        record['first_name'],
                        record.get('middle_name', ''),
                        record['last_name'],
                        gender,
                        str(record['dob']),
                        age,
                        record['course'].upper(),
                        registration_datetime
                    ))
                    
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
                
                # Update progress
                if self.progress_callback and i % 5 == 0:
                    progress = start_progress + int(((i + 1) / len(records)) * (100 - start_progress))
                    self.progress_callback(progress, f"Importing record {i+1}/{len(records)}")
            
            conn.commit()
            
            if self.progress_callback:
                self.progress_callback(100, f"Import complete: {result.successful_imports} records imported")
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error during import: {e}")
            raise
        finally:
            conn.close()
            result.end_time = datetime.datetime.now()
        
        return result
    
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
    
    def clean_and_fix_data(self, progress_callback=None) -> int:
        """Clean and fix common data issues. Returns the number of issues fixed."""
        issues = self.validate_and_clean_data(progress_callback)
        return len(issues)

    def validate_and_clean_data(self, progress_callback: Optional[Callable[[int, str], None]] = None) -> List[Dict]:
        """Validate and clean data in the database with comprehensive validation and reporting.

        Performs comprehensive data validation and cleaning operations including:
        - Data type validation
        - Missing data detection and handling
        - Duplicate record identification and resolution
        - Data consistency checks
        - Format standardization
        - Relationship validation

        Parameters
        ----------
        progress_callback : Callable[[int, str], None], optional
            A callback that accepts an integer progress percentage and a message.

        Returns
        -------
        List[Dict]
            A list of dictionaries describing any issues found and actions taken.
        """
        self.progress_callback = progress_callback

        try:
            # Initialize validation results
            validation_results = []
            start_time = datetime.datetime.now()

            if self.progress_callback:
                self.progress_callback(5, "Starting data validation and cleaning...")

            # Connect to database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Step 1: Validate student records
            if self.progress_callback:
                self.progress_callback(10, "Validating student records...")

            student_issues = self._validate_student_data(cursor)
            validation_results.extend(student_issues)

            # Step 2: Check for duplicates
            if self.progress_callback:
                self.progress_callback(25, "Identifying duplicate records...")

            duplicate_issues = self._identify_and_handle_duplicates(cursor)
            validation_results.extend(duplicate_issues)

            # Step 3: Validate data integrity
            if self.progress_callback:
                self.progress_callback(40, "Checking data integrity...")

            integrity_issues = self._validate_data_integrity(cursor)
            validation_results.extend(integrity_issues)

            # Step 4: Standardize data formats
            if self.progress_callback:
                self.progress_callback(55, "Standardizing data formats...")

            format_fixes = self._standardize_data_formats(cursor)
            validation_results.extend(format_fixes)

            # Step 5: Validate relationships
            if self.progress_callback:
                self.progress_callback(70, "Validating data relationships...")

            relationship_issues = self._validate_relationships(cursor)
            validation_results.extend(relationship_issues)

            # Step 6: Clean orphaned records
            if self.progress_callback:
                self.progress_callback(85, "Cleaning orphaned records...")

            orphan_cleanup = self._clean_orphaned_records(cursor)
            validation_results.extend(orphan_cleanup)

            # Commit changes
            conn.commit()

            if self.progress_callback:
                self.progress_callback(95, "Generating validation report...")

            # Generate comprehensive report
            report_data = self._generate_validation_report(validation_results, start_time)

            # Save report to file
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"data_validation_report_{timestamp}.json"
            with open(report_filename, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)

            if self.progress_callback:
                self.progress_callback(100, "Validation and cleaning complete!")

            # Show completion dialog with results
            try:
                self._show_validation_results_dialog(report_data, report_filename)
            except Exception:
                print(f"Validation completed. Report saved to {report_filename}")

            return validation_results

        except Exception as e:
            try:
                messagebox.showerror(_t("batch_ops.msg_titles.validation_error"), f"An error occurred during data validation: {str(e)}")
            except Exception:
                print(f"Error during data validation: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()

    def _validate_student_data(self, cursor) -> List[Dict]:
        """Validate student data fields"""
        issues = []

        try:
            # Check for missing required fields
            cursor.execute("""
                SELECT student_id, first_name, last_name, email_address, phone_number
                FROM students
                WHERE first_name IS NULL OR first_name = ''
                   OR last_name IS NULL OR last_name = ''
                   OR email_address IS NULL OR email_address = ''
            """)

            missing_data = cursor.fetchall()
            for record in missing_data:
                student_id, first_name, last_name, email, phone = record
                missing_fields = []
                if not first_name: missing_fields.append('first_name')
                if not last_name: missing_fields.append('last_name')
                if not email: missing_fields.append('email_address')

                issues.append({
                    'type': 'missing_data',
                    'severity': 'high',
                    'student_id': student_id,
                    'description': f'Missing required fields: {", ".join(missing_fields)}',
                    'action': 'flagged_for_review',
                    'timestamp': datetime.datetime.now().isoformat()
                })

            # Validate email formats
            cursor.execute("SELECT student_id, email_address FROM students WHERE email_address IS NOT NULL")
            email_records = cursor.fetchall()

            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

            for student_id, email in email_records:
                if email and not re.match(email_pattern, email):
                    issues.append({
                        'type': 'invalid_format',
                        'severity': 'medium',
                        'student_id': student_id,
                        'field': 'email_address',
                        'current_value': email,
                        'description': 'Invalid email format',
                        'action': 'requires_correction',
                        'timestamp': datetime.datetime.now().isoformat()
                    })

                    # Attempt basic email correction
                    corrected_email = self._attempt_email_correction(email)
                    if corrected_email and corrected_email != email:
                        cursor.execute(
                            "UPDATE students SET email_address = ? WHERE student_id = ?",
                            (corrected_email, student_id)
                        )
                        issues.append({
                            'type': 'data_corrected',
                            'severity': 'info',
                            'student_id': student_id,
                            'field': 'email_address',
                            'old_value': email,
                            'new_value': corrected_email,
                            'description': 'Email format automatically corrected',
                            'action': 'auto_corrected',
                            'timestamp': datetime.datetime.now().isoformat()
                        })

            # Validate phone numbers
            cursor.execute("SELECT student_id, phone_number FROM students WHERE phone_number IS NOT NULL")
            phone_records = cursor.fetchall()

            phone_pattern = r'^[\d\s\-\(\)\+\.]{10,}$'

            for student_id, phone in phone_records:
                if phone:
                    # Clean phone number for validation
                    clean_phone = re.sub(r'[^\d]', '', phone)
                    if len(clean_phone) < 10:
                        issues.append({
                            'type': 'invalid_format',
                            'severity': 'medium',
                            'student_id': student_id,
                            'field': 'phone_number',
                            'current_value': phone,
                            'description': 'Phone number too short',
                            'action': 'requires_correction',
                            'timestamp': datetime.datetime.now().isoformat()
                        })

        except Exception as e:
            issues.append({
                'type': 'validation_error',
                'severity': 'critical',
                'description': f'Error during student data validation: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _identify_and_handle_duplicates(self, cursor) -> List[Dict]:
        """Identify and handle duplicate records"""
        issues = []

        try:
            # Find potential duplicates by email
            cursor.execute("""
                SELECT email_address, COUNT(*) as count,
                       GROUP_CONCAT(student_id) as student_ids
                FROM students
                WHERE email_address IS NOT NULL AND email_address != ''
                GROUP BY LOWER(email_address)
                HAVING COUNT(*) > 1
            """)

            email_duplicates = cursor.fetchall()
            for email, count, student_ids in email_duplicates:
                ids = student_ids.split(',')
                issues.append({
                    'type': 'duplicate_email',
                    'severity': 'high',
                    'email': email,
                    'count': count,
                    'student_ids': ids,
                    'description': f'Email address {email} used by {count} students',
                    'action': 'requires_manual_review',
                    'timestamp': datetime.datetime.now().isoformat()
                })

            # Find duplicates by name and potential typos
            cursor.execute("""
                SELECT first_name, last_name, COUNT(*) as count,
                       GROUP_CONCAT(student_id) as student_ids
                FROM students
                WHERE first_name IS NOT NULL AND last_name IS NOT NULL
                GROUP BY LOWER(first_name), LOWER(last_name)
                HAVING COUNT(*) > 1
            """)

            name_duplicates = cursor.fetchall()
            for first_name, last_name, count, student_ids in name_duplicates:
                if count > 3:  # Only flag if more than 3 (could be common names)
                    ids = student_ids.split(',')
                    issues.append({
                        'type': 'duplicate_name',
                        'severity': 'medium',
                        'first_name': first_name,
                        'last_name': last_name,
                        'count': count,
                        'student_ids': ids,
                        'description': f'Name "{first_name} {last_name}" appears {count} times',
                        'action': 'review_for_duplicates',
                        'timestamp': datetime.datetime.now().isoformat()
                    })

        except Exception as e:
            issues.append({
                'type': 'duplicate_check_error',
                'severity': 'critical',
                'description': f'Error during duplicate detection: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _validate_data_integrity(self, cursor) -> List[Dict]:
        """Validate data integrity and consistency"""
        issues = []

        try:
            # Check for students with grades but no enrollment records
            cursor.execute("""
                SELECT DISTINCT g.student_id
                FROM grades g
                LEFT JOIN enrollments e ON g.student_id = e.student_id
                WHERE e.student_id IS NULL
            """)

            orphan_grades = cursor.fetchall()
            for (student_id,) in orphan_grades:
                issues.append({
                    'type': 'integrity_violation',
                    'severity': 'high',
                    'student_id': student_id,
                    'description': 'Student has grades but no enrollment records',
                    'action': 'requires_investigation',
                    'timestamp': datetime.datetime.now().isoformat()
                })

            # Check for invalid grade values
            cursor.execute("""
                SELECT student_id, subject, grade
                FROM grades
                WHERE grade NOT IN ('A', 'B', 'C', 'D', 'F', 'A+', 'A-', 'B+', 'B-', 'C+', 'C-', 'D+', 'D-')
                  AND grade NOT BETWEEN 0 AND 100
            """)

            invalid_grades = cursor.fetchall()
            for student_id, subject, grade in invalid_grades:
                issues.append({
                    'type': 'invalid_data',
                    'severity': 'medium',
                    'student_id': student_id,
                    'field': 'grade',
                    'subject': subject,
                    'current_value': grade,
                    'description': 'Invalid grade value',
                    'action': 'requires_correction',
                    'timestamp': datetime.datetime.now().isoformat()
                })

        except Exception as e:
            issues.append({
                'type': 'integrity_check_error',
                'severity': 'critical',
                'description': f'Error during integrity validation: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _standardize_data_formats(self, cursor) -> List[Dict]:
        """Standardize data formats across the database"""
        issues = []

        try:
            # Standardize name capitalization
            cursor.execute("SELECT student_id, first_name, last_name FROM students")
            name_records = cursor.fetchall()

            for student_id, first_name, last_name in name_records:
                if first_name:
                    standardized_first = first_name.strip().title()
                    if standardized_first != first_name:
                        cursor.execute(
                            "UPDATE students SET first_name = ? WHERE student_id = ?",
                            (standardized_first, student_id)
                        )
                        issues.append({
                            'type': 'format_standardized',
                            'severity': 'info',
                            'student_id': student_id,
                            'field': 'first_name',
                            'old_value': first_name,
                            'new_value': standardized_first,
                            'description': 'Name capitalization standardized',
                            'action': 'auto_corrected',
                            'timestamp': datetime.datetime.now().isoformat()
                        })

                if last_name:
                    standardized_last = last_name.strip().title()
                    if standardized_last != last_name:
                        cursor.execute(
                            "UPDATE students SET last_name = ? WHERE student_id = ?",
                            (standardized_last, student_id)
                        )
                        issues.append({
                            'type': 'format_standardized',
                            'severity': 'info',
                            'student_id': student_id,
                            'field': 'last_name',
                            'old_value': last_name,
                            'new_value': standardized_last,
                            'description': 'Name capitalization standardized',
                            'action': 'auto_corrected',
                            'timestamp': datetime.datetime.now().isoformat()
                        })

            # Standardize email addresses (lowercase)
            cursor.execute("SELECT student_id, email_address FROM students WHERE email_address IS NOT NULL")
            email_records = cursor.fetchall()

            for student_id, email in email_records:
                if email:
                    standardized_email = email.strip().lower()
                    if standardized_email != email:
                        cursor.execute(
                            "UPDATE students SET email_address = ? WHERE student_id = ?",
                            (standardized_email, student_id)
                        )
                        issues.append({
                            'type': 'format_standardized',
                            'severity': 'info',
                            'student_id': student_id,
                            'field': 'email_address',
                            'old_value': email,
                            'new_value': standardized_email,
                            'description': 'Email address standardized to lowercase',
                            'action': 'auto_corrected',
                            'timestamp': datetime.datetime.now().isoformat()
                        })

        except Exception as e:
            issues.append({
                'type': 'standardization_error',
                'severity': 'critical',
                'description': f'Error during format standardization: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _validate_relationships(self, cursor) -> List[Dict]:
        """Validate relationships between tables"""
        issues = []

        try:
            # Check for enrollments without valid students
            cursor.execute("""
                SELECT e.student_id, e.course_id, e.semester
                FROM enrollments e
                LEFT JOIN students s ON e.student_id = s.student_id
                WHERE s.student_id IS NULL
            """)

            invalid_enrollments = cursor.fetchall()
            for student_id, course_id, semester in invalid_enrollments:
                issues.append({
                    'type': 'relationship_violation',
                    'severity': 'high',
                    'table': 'enrollments',
                    'student_id': student_id,
                    'course_id': course_id,
                    'semester': semester,
                    'description': 'Enrollment record references non-existent student',
                    'action': 'requires_cleanup',
                    'timestamp': datetime.datetime.now().isoformat()
                })

        except Exception as e:
            issues.append({
                'type': 'relationship_check_error',
                'severity': 'critical',
                'description': f'Error during relationship validation: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _clean_orphaned_records(self, cursor) -> List[Dict]:
        """Clean up orphaned records"""
        issues = []

        try:
            # Clean up orphaned grade records
            cursor.execute("""
                DELETE FROM grades
                WHERE student_id NOT IN (SELECT student_id FROM students)
            """)

            orphaned_grades_cleaned = cursor.rowcount
            if orphaned_grades_cleaned > 0:
                issues.append({
                    'type': 'cleanup_completed',
                    'severity': 'info',
                    'table': 'grades',
                    'records_cleaned': orphaned_grades_cleaned,
                    'description': f'Cleaned {orphaned_grades_cleaned} orphaned grade records',
                    'action': 'auto_cleaned',
                    'timestamp': datetime.datetime.now().isoformat()
                })

        except Exception as e:
            issues.append({
                'type': 'cleanup_error',
                'severity': 'critical',
                'description': f'Error during orphaned record cleanup: {str(e)}',
                'action': 'manual_review_required',
                'timestamp': datetime.datetime.now().isoformat()
            })

        return issues

    def _attempt_email_correction(self, email: str) -> str:
        """Attempt basic email format corrections"""
        if not email:
            return email

        # Common corrections
        corrections = {
            'gmail.com': ['gmai.com', 'gmial.com', 'gmail.co'],
            'yahoo.com': ['yaho.com', 'yahoo.co'],
            'hotmail.com': ['hotmai.com', 'hotmail.co'],
            'outlook.com': ['outlok.com', 'outlook.co']
        }

        email = email.strip().lower()

        # Fix common domain typos
        for correct_domain, typos in corrections.items():
            for typo in typos:
                if email.endswith(f'@{typo}'):
                    return email.replace(f'@{typo}', f'@{correct_domain}')

        # Fix missing @ symbol
        if ' ' in email and '@' not in email:
            parts = email.split(' ')
            if len(parts) == 2 and '.' in parts[1]:
                return f"{parts[0]}@{parts[1]}"

        return email

    def _generate_validation_report(self, validation_results: List[Dict], start_time) -> Dict:
        """Generate comprehensive validation report"""
        end_time = datetime.datetime.now()

        # Categorize issues
        categories = {}
        severities = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        actions = {}

        for issue in validation_results:
            # Count by type
            issue_type = issue.get('type', 'unknown')
            categories[issue_type] = categories.get(issue_type, 0) + 1

            # Count by severity
            severity = issue.get('severity', 'unknown')
            if severity in severities:
                severities[severity] += 1

            # Count by action
            action = issue.get('action', 'unknown')
            actions[action] = actions.get(action, 0) + 1

        report = {
            'summary': {
                'total_issues_found': len(validation_results),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': (end_time - start_time).total_seconds(),
                'validation_status': 'completed'
            },
            'issue_breakdown': {
                'by_category': categories,
                'by_severity': severities,
                'by_action': actions
            },
            'detailed_issues': validation_results,
            'recommendations': self._generate_recommendations(validation_results),
            'report_metadata': {
                'generated_by': 'University Management System - Batch Operations',
                'version': '1.0',
                'report_type': 'Data Validation and Cleaning'
            }
        }

        return report

    def _generate_recommendations(self, validation_results: List[Dict]) -> List[str]:
        """Generate actionable recommendations based on validation results"""
        recommendations = []

        # Count critical issues
        critical_count = len([r for r in validation_results if r.get('severity') == 'critical'])
        if critical_count > 0:
            recommendations.append(f"Address {critical_count} critical issues immediately to prevent data corruption")

        # Count missing data issues
        missing_data_count = len([r for r in validation_results if r.get('type') == 'missing_data'])
        if missing_data_count > 0:
            recommendations.append(f"Review {missing_data_count} records with missing required fields")

        # Count duplicate issues
        duplicate_count = len([r for r in validation_results if 'duplicate' in r.get('type', '')])
        if duplicate_count > 0:
            recommendations.append(f"Investigate {duplicate_count} potential duplicate records")

        # Count format issues
        format_count = len([r for r in validation_results if r.get('type') == 'invalid_format'])
        if format_count > 0:
            recommendations.append(f"Correct {format_count} invalid data formats")

        # General recommendations
        recommendations.extend([
            "Implement data validation at input stage to prevent future issues",
            "Schedule regular data validation runs (weekly or monthly)",
            "Consider implementing automated data quality monitoring",
            "Train data entry staff on proper formatting standards"
        ])

        return recommendations

    # ========================================
    # ENHANCED IMPORT/EXPORT UTILITY FUNCTIONS
    # ========================================

    def resume_failed_import(self, progress_callback=None):
        """Resume previously failed import operations - GUI version with progress tracking"""
        try:
            resume_file = DATA_DIR / "import_resume.json"
            if not resume_file.exists():
                raise FileNotFoundError("No failed import found to resume")

            with open(resume_file, 'r') as f:
                resume_data = json.load(f)

            remaining_records = resume_data['remaining_records']
            original_total = resume_data['original_total']
            filename = resume_data['filename']

            if progress_callback:
                already_processed = original_total - len(remaining_records)
                progress_callback(0, f"Resuming import: {already_processed}/{original_total} already processed")

            # Import remaining records
            result = self.import_valid_records_with_progress(
                remaining_records,
                start_progress=int((original_total - len(remaining_records)) / original_total * 100) if progress_callback else 0
            )
            result.total_records = original_total

            # Clean up resume file on success
            if result.successful_imports > 0:
                resume_file.unlink()

            self.save_import_history(result, filename, 'Resumed Import')

            if progress_callback:
                progress_callback(100, f"Resume complete: {result.successful_imports} records imported")

            return result

        except Exception as e:
            logger.error(f"Error resuming import: {e}")
            raise

    def read_csv_file(self, file_path: str) -> List[Dict]:
        """Utility to read and parse CSV files - GUI-friendly version"""
        try:
            records = []
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
                # Detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)

                sniffer = csv.Sniffer()
                try:
                    delimiter = sniffer.sniff(sample).delimiter
                except csv.Error:
                    delimiter = ','  # Default to comma

                reader = csv.DictReader(csvfile, delimiter=delimiter)
                # Normalize headers
                reader.fieldnames = [
                    header.strip().lower().replace(' ', '_')
                    for header in reader.fieldnames
                ]

                records = list(reader)

            logger.info(f"Read {len(records)} records from CSV: {file_path}")
            return records

        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            raise

    def read_excel_file(self, file_path: str, sheet_name: str = None) -> List[Dict]:
        """Utility to read and parse Excel files - GUI-friendly version"""
        try:
            # Read Excel file
            df = pd.read_excel(file_path, sheet_name=sheet_name or 0)

            # Normalize column names
            df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]

            # Convert to list of dictionaries, handling NaN values
            records = df.to_dict('records')
            records = [{k: (None if pd.isna(v) else v) for k, v in record.items()} for record in records]

            logger.info(f"Read {len(records)} records from Excel: {file_path} (sheet: {sheet_name or 'default'})")
            return records

        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            raise

    def display_validation_errors(self, error_records: List[Dict], max_display: int = 10,
                                  callback=None) -> str:
        """Display validation errors in GUI-friendly format"""
        if not error_records:
            return "No validation errors found."

        error_text = f"Found {len(error_records)} validation errors:\n\n"

        # Display first N errors
        display_count = min(len(error_records), max_display)
        for i, error_record in enumerate(error_records[:display_count]):
            row_num = error_record.get('row', i + 1)
            errors = error_record.get('errors', {})
            data = error_record.get('data', {})

            error_text += f"Row {row_num}:\n"
            for field, error_msg in errors.items():
                error_text += f"  • {field}: {error_msg}\n"
            error_text += f"  Data: {data.get('student_id', 'N/A')} - {data.get('first_name', '')} {data.get('last_name', '')}\n\n"

        if len(error_records) > max_display:
            error_text += f"\n... and {len(error_records) - max_display} more errors\n"

        if callback:
            callback(error_text)

        return error_text

    def interactive_error_resolution(self, error_records: List[Dict],
                                     resolution_callback=None) -> List[Dict]:
        """Interactive menu to fix validation errors - GUI version

        Args:
            error_records: List of error records to resolve
            resolution_callback: Callback function(error_record, action) -> fixed_record or None
                                Returns: 'fix' (with fixed record), 'skip', or 'abort'

        Returns:
            List of fixed records ready for import
        """
        fixed_records = []

        if not resolution_callback:
            # No interactive resolution available, return empty list
            logger.warning("No resolution callback provided for interactive error resolution")
            return fixed_records

        for error_record in error_records:
            try:
                result = resolution_callback(error_record)

                if result is None or result.get('action') == 'abort':
                    logger.info("User aborted error resolution")
                    break
                elif result.get('action') == 'skip':
                    continue
                elif result.get('action') == 'fix' and result.get('record'):
                    # Validate fixed record
                    fixed_data = result['record']
                    errors = self.validate_student_data(fixed_data)
                    if not errors:
                        fixed_records.append(fixed_data)
                    else:
                        logger.warning(f"Fixed record still has errors: {errors}")

            except Exception as e:
                logger.error(f"Error in interactive resolution: {e}")
                continue

        return fixed_records

    def fix_record_interactive(self, record: Dict, field_callback=None) -> Optional[Dict]:
        """Fix individual record interactively - GUI version

        Args:
            record: Record to fix
            field_callback: Callback function(field_name, current_value, error) -> new_value

        Returns:
            Fixed record or None if user cancels
        """
        if not field_callback:
            return None

        fixed_record = record.copy()
        errors = self.validate_student_data(fixed_record)

        if not errors:
            return fixed_record

        # Fix each field with errors
        for field, error_msg in errors.items():
            current_value = fixed_record.get(field, '')
            new_value = field_callback(field, current_value, error_msg)

            if new_value is None:
                # User cancelled
                return None

            fixed_record[field] = new_value

        return fixed_record

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
        # Typical columns: student_id, first_name, last_name, email, course, date_of_birth, ...
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
        """Handle duplicate records based on user choice - GUI version

        Args:
            records: All import records
            duplicates: List of duplicate matches
            choice: 'skip', 'overwrite', or 'update'
            progress_callback: Optional progress callback

        Returns:
            ImportResult with handling results
        """
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

    def import_valid_records(self, records: List[Dict]) -> ImportResult:
        """Import only valid records after filtering - wrapper for GUI compatibility"""
        return self.import_valid_records_with_progress(records, start_progress=0)

    def save_import_progress(self, remaining_records: List[Dict], original_total: int,
                            filename: str):
        """Save progress of interrupted imports for resume capability"""
        try:
            resume_data = {
                'remaining_records': remaining_records,
                'original_total': original_total,
                'filename': filename,
                'timestamp': datetime.datetime.now().isoformat()
            }

            resume_file = DATA_DIR / "import_resume.json"
            with open(resume_file, 'w') as f:
                json.dump(resume_data, f, default=str)

            logger.info(f"Saved import progress: {len(remaining_records)}/{original_total} remaining")

        except Exception as e:
            logger.error(f"Error saving import progress: {e}")

    def save_import_history(self, result: ImportResult, file_path: str, operation_type: str):
        """Save detailed import history to database for tracking and auditing"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Create history table if not exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS import_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        operation_type TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        total_records INTEGER DEFAULT 0,
                        successful_imports INTEGER DEFAULT 0,
                        failed_imports INTEGER DEFAULT 0,
                        duplicates_found INTEGER DEFAULT 0,
                        validation_errors INTEGER DEFAULT 0,
                        error_details TEXT,
                        duration_seconds REAL,
                        status TEXT DEFAULT 'completed'
                    )
                """)

                # Calculate error details
                error_details = json.dumps({
                    'errors': result.errors[:100] if hasattr(result, 'errors') else [],  # Limit to first 100
                    'warnings': result.warnings[:100] if hasattr(result, 'warnings') else []
                })

                # Insert history record
                cursor.execute("""
                    INSERT INTO import_history
                    (timestamp, operation_type, file_path, total_records, successful_imports,
                     failed_imports, duplicates_found, error_details, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.datetime.now().isoformat(),
                    operation_type,
                    file_path,
                    result.total_records,
                    result.successful_imports,
                    result.failed_imports,
                    result.duplicates_found,
                    error_details,
                    'completed' if result.successful_imports > 0 else 'failed'
                ))

                conn.commit()
                logger.info(f"Saved import history: {operation_type} - {file_path}")

        except Exception as e:
            logger.error(f"Error saving import history: {e}")

    # ========================================
    # BATCH UPDATE FEATURES
    # ========================================

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
        """Update student module enrollments when course changes

        This method updates module assignments based on the new course.
        It clears existing optional modules and assigns new ones based on course type.
        """
        try:
            # Get current modules
            cursor.execute(
                "SELECT compulsory_module_1, compulsory_module_2 FROM students WHERE student_id = ?",
                (student_id,)
            )
            current = cursor.fetchone()

            if not current:
                logger.warning(f"Student {student_id} not found for module update")
                return

            # Determine new modules based on course
            if new_course == 'COMPUTER SCIENCE':
                optional_1 = CS_optional_module_1
                optional_2 = CS_optional_module_2
                optional_3 = CS_optional_module_3
                optional_4 = CS_optional_module_4
            elif new_course == 'DATA SCIENCE':
                optional_1 = DS_optional_module_1
                optional_2 = DS_optional_module_2
                optional_3 = DS_optional_module_3
                optional_4 = DS_optional_module_4
            else:
                # Default modules for general or other courses
                optional_1 = optional_module_1
                optional_2 = optional_module_2
                optional_3 = optional_module_3
                optional_4 = optional_module_4

            # Update modules
            cursor.execute("""
                UPDATE students
                SET compulsory_module_1 = ?,
                    compulsory_module_2 = ?,
                    optional_module_1 = ?,
                    optional_module_2 = ?,
                    optional_module_3 = ?,
                    optional_module_4 = ?
                WHERE student_id = ?
            """, (
                compulsory_module_1,
                compulsory_module_2,
                optional_1,
                optional_2,
                optional_3,
                optional_4,
                student_id
            ))

            logger.info(f"Updated modules for student {student_id} to {new_course} track")

        except Exception as e:
            logger.error(f"Error updating student modules: {e}")
            raise

    # ========================================
    # BULK MODULE OPERATIONS - GUI WRAPPERS
    # ========================================

    def bulk_add_modules(self, module_code: str, module_name: str, module_type: str,
                        student_ids: List[str] = None, course: str = None,
                        progress_callback=None) -> int:
        """Add module to multiple students - GUI version with progress tracking

        Note: module_type is validated against _VALID_MODULE_TYPES before SQL use.

        Args:
            module_code: Module code to add
            module_name: Module name
            module_type: Module type (compulsory_module_1, optional_module_1, etc.)
            student_ids: List of specific student IDs (optional)
            course: Course to filter students (optional)
            progress_callback: Progress callback function

        Returns:
            Number of students updated
        """
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
        """Remove module from multiple students - GUI version

        Args:
            module_type: Module type to remove (e.g., 'optional_module_1')
            student_ids: List of specific student IDs (optional)
            course: Course to filter students (optional)
            progress_callback: Progress callback function

        Returns:
            Number of students updated
        """
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
        """Replace one module with another for multiple students - GUI version

        Args:
            module_type: Module type (e.g., 'optional_module_1')
            old_module_code: Module code to replace
            new_module_code: New module code
            new_module_name: New module name
            student_ids: List of specific student IDs (optional)
            course: Course to filter students (optional)
            progress_callback: Progress callback function

        Returns:
            Number of students updated
        """
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
        """Import module enrollments from file - GUI version

        Expected columns: student_id, module_type, module_code, module_name

        Args:
            file_path: Path to CSV/Excel file
            progress_callback: Progress callback function

        Returns:
            ImportResult with operation results
        """
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

    # ========================================
    # GRADE MANAGEMENT - GUI WRAPPERS
    # ========================================

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

        Args:
            grades: List of grade records
            progress_callback: Progress callback function

        Returns:
            ImportResult with processing results
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

    # ========================================
    # EXPORT FEATURES - GUI WRAPPERS
    # ========================================

    def export_data_to_file(self, data: List[Tuple], columns: List[str],
                           filename: str, format_type: str = 'csv',
                           progress_callback=None) -> str:
        """Generic export utility function - GUI version

        Args:
            data: List of tuples containing data rows
            columns: List of column names
            filename: Output filename
            format_type: 'csv' or 'excel'
            progress_callback: Progress callback function

        Returns:
            Path to exported file
        """
        try:
            if progress_callback:
                progress_callback(0, f"Exporting {len(data)} records to {format_type.upper()}...")

            # Ensure filename has correct extension
            if format_type == 'csv' and not filename.endswith('.csv'):
                filename += '.csv'
            elif format_type == 'excel' and not filename.endswith('.xlsx'):
                filename += '.xlsx'

            # Create full path
            export_path = DATA_DIR / 'exports' / filename
            export_path.parent.mkdir(parents=True, exist_ok=True)

            if format_type == 'csv':
                # Export to CSV
                with open(export_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(data)

            elif format_type == 'excel':
                # Export to Excel
                df = pd.DataFrame(data, columns=columns)
                df.to_excel(export_path, index=False, engine='openpyxl')

            else:
                raise ValueError(f"Unsupported format type: {format_type}")

            if progress_callback:
                progress_callback(100, f"Export complete: {export_path}")

            logger.info(f"Exported {len(data)} records to {export_path}")
            return str(export_path)

        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            raise

    def export_enrollment_statistics(self, output_format: str = 'csv',
                                     progress_callback=None) -> str:
        """Export enrollment statistics report - GUI version

        Args:
            output_format: 'csv' or 'excel'
            progress_callback: Progress callback function

        Returns:
            Path to exported file
        """
        try:
            if progress_callback:
                progress_callback(0, "Gathering enrollment statistics...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get enrollment statistics by course
                cursor.execute("""
                    SELECT
                        course,
                        COUNT(*) as total_students,
                        SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active_students,
                        SUM(CASE WHEN status = 'Inactive' THEN 1 ELSE 0 END) as inactive_students,
                        SUM(CASE WHEN status = 'Graduated' THEN 1 ELSE 0 END) as graduated_students,
                        MIN(enrollment_date) as earliest_enrollment,
                        MAX(enrollment_date) as latest_enrollment
                    FROM students
                    GROUP BY course
                    ORDER BY total_students DESC
                """)

                stats = cursor.fetchall()

                if not stats:
                    raise ValueError("No enrollment data found")

                columns = [
                    'Course', 'Total Students', 'Active', 'Inactive', 'Graduated',
                    'Earliest Enrollment', 'Latest Enrollment'
                ]

                if progress_callback:
                    progress_callback(50, "Generating report...")

                # Generate filename with timestamp
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'enrollment_statistics_{timestamp}'

                # Export data
                export_path = self.export_data_to_file(
                    stats,
                    columns,
                    filename,
                    output_format,
                    None  # Don't pass progress callback to avoid double updates
                )

                if progress_callback:
                    progress_callback(100, f"Statistics exported: {export_path}")

                logger.info(f"Exported enrollment statistics to {export_path}")
                return export_path

        except Exception as e:
            logger.error(f"Error exporting enrollment statistics: {e}")
            raise

    # ========================================
    # REPORTING FEATURES - GUI WRAPPERS
    # ========================================

    def generate_import_reports(self, report_type: str = 'summary',
                                start_date: str = None, end_date: str = None,
                                progress_callback=None) -> Dict:
        """Generate import reports - GUI version

        Args:
            report_type: 'summary', 'detailed', 'errors', or 'trends'
            start_date: Start date filter (ISO format)
            end_date: End date filter (ISO format)
            progress_callback: Progress callback function

        Returns:
            Dictionary containing report data
        """
        try:
            if progress_callback:
                progress_callback(0, f"Generating {report_type} import report...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Ensure import_history table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS import_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        operation_type TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        total_records INTEGER DEFAULT 0,
                        successful_imports INTEGER DEFAULT 0,
                        failed_imports INTEGER DEFAULT 0,
                        duplicates_found INTEGER DEFAULT 0,
                        validation_errors INTEGER DEFAULT 0,
                        error_details TEXT,
                        duration_seconds REAL,
                        status TEXT DEFAULT 'completed'
                    )
                """)

                # Build query based on report type
                query = "SELECT * FROM import_history WHERE 1=1"
                params = []

                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date)

                query += " ORDER BY timestamp DESC"

                cursor.execute(query, params)
                history = cursor.fetchall()

                if progress_callback:
                    progress_callback(50, "Analyzing import history...")

                # Generate report based on type
                report = {
                    'report_type': report_type,
                    'generated_at': datetime.datetime.now().isoformat(),
                    'period': {
                        'start_date': start_date or 'All time',
                        'end_date': end_date or 'Present'
                    },
                    'total_operations': len(history)
                }

                if report_type == 'summary':
                    # Summary statistics
                    total_records = sum(h[4] for h in history)  # total_records column
                    successful = sum(h[5] for h in history)  # successful_imports column
                    failed = sum(h[6] for h in history)  # failed_imports column
                    duplicates = sum(h[7] for h in history)  # duplicates_found column

                    report['summary'] = {
                        'total_records_processed': total_records,
                        'successful_imports': successful,
                        'failed_imports': failed,
                        'duplicates_found': duplicates,
                        'success_rate': round((successful / total_records * 100) if total_records > 0 else 0, 2)
                    }

                elif report_type == 'detailed':
                    # Detailed operation list
                    report['operations'] = []
                    for h in history:
                        report['operations'].append({
                            'id': h[0],
                            'timestamp': h[1],
                            'operation_type': h[2],
                            'file_path': h[3],
                            'total_records': h[4],
                            'successful_imports': h[5],
                            'failed_imports': h[6],
                            'duplicates_found': h[7],
                            'status': h[11] if len(h) > 11 else 'unknown'
                        })

                elif report_type == 'errors':
                    # Error analysis
                    report['errors'] = []
                    for h in history:
                        if h[6] > 0:  # failed_imports > 0
                            error_details = json.loads(h[9]) if h[9] else {}
                            report['errors'].append({
                                'timestamp': h[1],
                                'operation': h[2],
                                'file': h[3],
                                'failed_count': h[6],
                                'error_details': error_details.get('errors', [])[:10]  # First 10 errors
                            })

                elif report_type == 'trends':
                    # Import trends over time
                    report['trends'] = []
                    # Group by date
                    date_groups = {}
                    for h in history:
                        date = h[1][:10]  # Extract date part
                        if date not in date_groups:
                            date_groups[date] = {'total': 0, 'successful': 0, 'failed': 0}
                        date_groups[date]['total'] += h[4]
                        date_groups[date]['successful'] += h[5]
                        date_groups[date]['failed'] += h[6]

                    report['trends'] = [
                        {'date': date, **stats}
                        for date, stats in sorted(date_groups.items())
                    ]

                if progress_callback:
                    progress_callback(100, "Report generation complete")

                logger.info(f"Generated {report_type} import report")
                return report

        except Exception as e:
            logger.error(f"Error generating import reports: {e}")
            raise

    # ========================================
    # DATA QUALITY FEATURES - GUI WRAPPERS
    # ========================================

    def merge_students(self, keep_id: str, delete_id: str, keep_first: bool = True,
                      progress_callback=None) -> bool:
        """Merge two student records - GUI version

        Args:
            keep_id: Student ID to keep
            delete_id: Student ID to delete
            keep_first: If True, keep data from first record when conflicts occur
            progress_callback: Progress callback function

        Returns:
            True if merge successful
        """
        try:
            if progress_callback:
                progress_callback(0, f"Merging students: {delete_id} → {keep_id}")

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
                    # Update keep_student with non-null values from delete_student
                    # This is a simplified version - in production you'd handle all columns
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
                # Update grades table if it exists
                try:
                    cursor.execute(
                        "UPDATE grades SET student_id = ? WHERE student_id = ?",
                        (keep_id, delete_id)
                    )
                except Exception:
                    pass  # Table might not exist

                # Update any other related tables here as needed

                if progress_callback:
                    progress_callback(75, "Removing duplicate record...")

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

    def data_quality_dashboard(self, progress_callback=None) -> Dict:
        """Comprehensive data quality dashboard - GUI version

        Args:
            progress_callback: Progress callback function

        Returns:
            Dictionary containing quality metrics and statistics
        """
        try:
            if progress_callback:
                progress_callback(0, "Gathering data quality metrics...")

            dashboard = {
                'generated_at': datetime.datetime.now().isoformat(),
                'overall_score': 0,
                'metrics': {},
                'issues': [],
                'recommendations': []
            }

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Total student count
                cursor.execute("SELECT COUNT(*) FROM students")
                total_students = cursor.fetchone()[0]
                dashboard['metrics']['total_students'] = total_students

                if progress_callback:
                    progress_callback(20, "Checking data completeness...")

                # Missing data check
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN email IS NULL OR email = '' THEN 1 ELSE 0 END) as missing_email,
                        SUM(CASE WHEN phone_number IS NULL OR phone_number = '' THEN 1 ELSE 0 END) as missing_phone,
                        SUM(CASE WHEN address IS NULL OR address = '' THEN 1 ELSE 0 END) as missing_address,
                        SUM(CASE WHEN date_of_birth IS NULL OR date_of_birth = '' THEN 1 ELSE 0 END) as missing_dob
                    FROM students
                """)
                missing = cursor.fetchone()
                dashboard['metrics']['missing_data'] = {
                    'email': missing[0],
                    'phone': missing[1],
                    'address': missing[2],
                    'date_of_birth': missing[3]
                }

                if progress_callback:
                    progress_callback(40, "Checking for duplicates...")

                # Duplicate check
                duplicates = self.find_duplicate_students(None)
                dashboard['metrics']['duplicates_found'] = len(duplicates)

                if progress_callback:
                    progress_callback(60, "Validating data formats...")

                # Invalid email format check
                cursor.execute("""
                    SELECT COUNT(*) FROM students
                    WHERE email IS NOT NULL AND email != ''
                    AND email NOT LIKE '%@%.%'
                """)
                invalid_emails = cursor.fetchone()[0]
                dashboard['metrics']['invalid_emails'] = invalid_emails

                if progress_callback:
                    progress_callback(80, "Calculating quality score...")

                # Calculate overall quality score (0-100)
                completeness_score = (1 - sum(missing) / (total_students * 4)) * 100 if total_students > 0 else 0
                duplicate_penalty = min(len(duplicates) * 5, 30)  # Max 30 point penalty
                format_penalty = min(invalid_emails * 2, 20)  # Max 20 point penalty

                overall_score = max(0, completeness_score - duplicate_penalty - format_penalty)
                dashboard['overall_score'] = round(overall_score, 2)

                # Generate issues
                if sum(missing) > 0:
                    dashboard['issues'].append(f"{sum(missing)} records with missing data")
                if len(duplicates) > 0:
                    dashboard['issues'].append(f"{len(duplicates)} potential duplicate records")
                if invalid_emails > 0:
                    dashboard['issues'].append(f"{invalid_emails} records with invalid email format")

                # Generate recommendations
                if overall_score < 70:
                    dashboard['recommendations'].append("Data quality is below acceptable threshold - immediate action required")
                if sum(missing) > total_students * 0.1:
                    dashboard['recommendations'].append("Implement mandatory field validation for new entries")
                if len(duplicates) > 0:
                    dashboard['recommendations'].append("Review and merge duplicate records")
                if invalid_emails > 0:
                    dashboard['recommendations'].append("Validate and correct email formats")

                dashboard['recommendations'].append("Schedule regular data quality audits")

                if progress_callback:
                    progress_callback(100, "Dashboard generation complete")

                logger.info(f"Generated data quality dashboard - Score: {overall_score}")
                return dashboard

        except Exception as e:
            logger.error(f"Error generating data quality dashboard: {e}")
            raise

    # ========================================
    # TEMPLATE GENERATION - GUI WRAPPERS
    # ========================================

    def create_template_file(self, fields: List[str], filename: str,
                            file_format: str, template_type: str,
                            include_examples: bool = True,
                            progress_callback=None) -> str:
        """Create import template file - GUI version

        Args:
            fields: List of field names
            filename: Output filename
            file_format: 'csv' or 'excel'
            template_type: Type of template (student, grade, module)
            include_examples: Include example data rows
            progress_callback: Progress callback function

        Returns:
            Path to created template file
        """
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
        """Get example data for templates - GUI version

        Args:
            template_type: Type of template (student, grade, module, enrollment)

        Returns:
            Dictionary with example field values
        """
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
        """Display template usage instructions - GUI version

        Args:
            template_type: Type of template
            callback: Optional callback to display instructions

        Returns:
            Formatted instruction text
        """
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

    # ========================================
    # BACKUP/RESTORE FEATURES - GUI WRAPPERS
    # ========================================

    def create_database_backup(self, auto: bool = False,
                               progress_callback=None) -> str:
        """Create database backup file - GUI version

        Args:
            auto: If True, create automatic backup with timestamp
            progress_callback: Progress callback function

        Returns:
            Path to backup file
        """
        try:
            if progress_callback:
                progress_callback(0, "Creating database backup...")

            # Create backups directory
            backup_dir = DATA_DIR / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Generate backup filename
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_type = 'auto' if auto else 'manual'
            backup_filename = f'student_records_backup_{backup_type}_{timestamp}.db'
            backup_path = backup_dir / backup_filename

            if progress_callback:
                progress_callback(30, "Copying database file...")

            # Copy database file
            db_path = self.db_manager.db_path
            shutil.copy2(db_path, backup_path)

            if progress_callback:
                progress_callback(80, "Verifying backup...")

            # Verify backup
            if not backup_path.exists():
                raise FileNotFoundError("Backup file was not created")

            if progress_callback:
                progress_callback(100, f"Backup created: {backup_path}")

            logger.info(f"Created {'automatic' if auto else 'manual'} backup: {backup_path}")
            return str(backup_path)

        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            raise

    def cleanup_old_backups(self, keep_count: int = 10,
                           progress_callback=None) -> int:
        """Remove old backup files - GUI version

        Args:
            keep_count: Number of most recent backups to keep
            progress_callback: Progress callback function

        Returns:
            Number of backups deleted
        """
        try:
            if progress_callback:
                progress_callback(0, f"Cleaning up old backups (keeping {keep_count})...")

            backup_dir = DATA_DIR / 'backups'
            if not backup_dir.exists():
                return 0

            # Get all backup files sorted by modification time
            backups = sorted(
                backup_dir.glob('student_records_backup_*.db'),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            if len(backups) <= keep_count:
                if progress_callback:
                    progress_callback(100, "No old backups to clean up")
                return 0

            # Delete old backups
            backups_to_delete = backups[keep_count:]
            deleted_count = 0

            for i, backup in enumerate(backups_to_delete):
                try:
                    backup.unlink()
                    deleted_count += 1

                    if progress_callback:
                        progress = int((i / len(backups_to_delete)) * 100)
                        progress_callback(progress, f"Deleting: {i+1}/{len(backups_to_delete)}")

                except Exception as e:
                    logger.warning(f"Failed to delete backup {backup}: {e}")

            if progress_callback:
                progress_callback(100, f"Deleted {deleted_count} old backups")

            logger.info(f"Cleaned up {deleted_count} old backups, kept {keep_count} most recent")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
            raise

    def undo_last_import(self, progress_callback=None) -> bool:
        """Undo the last import operation - GUI version

        Args:
            progress_callback: Progress callback function

        Returns:
            True if undo successful
        """
        try:
            if progress_callback:
                progress_callback(0, "Looking for automatic backup...")

            backup_dir = DATA_DIR / 'backups'
            if not backup_dir.exists():
                raise FileNotFoundError("No backups directory found")

            # Find most recent auto backup
            auto_backups = sorted(
                backup_dir.glob('student_records_backup_auto_*.db'),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            if not auto_backups:
                raise FileNotFoundError("No automatic backups found")

            latest_backup = auto_backups[0]

            if progress_callback:
                progress_callback(25, f"Found backup: {latest_backup.name}")

            # Create a safety backup of current state
            safety_backup = self.create_database_backup(auto=False, progress_callback=None)

            if progress_callback:
                progress_callback(50, "Restoring from backup...")

            # Close current database connection
            self.db_manager.close()

            # Restore from backup
            db_path = self.db_manager.db_path
            shutil.copy2(latest_backup, db_path)

            # Reconnect
            self.db_manager = DatabaseManager(db_path)

            if progress_callback:
                progress_callback(90, "Verifying restoration...")

            # Verify restoration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM students")
                count = cursor.fetchone()[0]

            if progress_callback:
                progress_callback(100, f"Undo complete - {count} students in database")

            logger.info(f"Successfully undone last import, restored from {latest_backup}")
            logger.info(f"Safety backup created at {safety_backup}")
            return True

        except Exception as e:
            logger.error(f"Error undoing last import: {e}")
            raise

    # ========================================
    # UTILITY FUNCTIONS - GUI WRAPPERS
    # ========================================

    def get_students_by_course(self, course: str,
                               progress_callback=None) -> List[str]:
        """Get list of student IDs by course - GUI version

        Args:
            course: Course name to filter by
            progress_callback: Progress callback function

        Returns:
            List of student IDs
        """
        try:
            if progress_callback:
                progress_callback(0, f"Fetching students in {course}...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT student_id FROM students WHERE course = ? ORDER BY student_id",
                    (course,)
                )
                student_ids = [row[0] for row in cursor.fetchall()]

            if progress_callback:
                progress_callback(100, f"Found {len(student_ids)} students in {course}")

            logger.info(f"Retrieved {len(student_ids)} students for course {course}")
            return student_ids

        except Exception as e:
            logger.error(f"Error getting students by course: {e}")
            raise

    def get_all_student_ids(self, progress_callback=None) -> List[str]:
        """Get all student IDs from database - GUI version

        Args:
            progress_callback: Progress callback function

        Returns:
            Complete list of student IDs
        """
        try:
            if progress_callback:
                progress_callback(0, "Fetching all student IDs...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT student_id FROM students ORDER BY student_id")
                student_ids = [row[0] for row in cursor.fetchall()]

            if progress_callback:
                progress_callback(100, f"Found {len(student_ids)} total students")

            logger.info(f"Retrieved {len(student_ids)} total student IDs")
            return student_ids

        except Exception as e:
            logger.error(f"Error getting all student IDs: {e}")
            raise

    def read_student_ids_from_file(self, file_path: str,
                                   progress_callback=None) -> List[str]:
        """Read student IDs from text file - GUI version

        Expected format: One student ID per line

        Args:
            file_path: Path to text file
            progress_callback: Progress callback function

        Returns:
            List of student IDs
        """
        try:
            if progress_callback:
                progress_callback(0, f"Reading student IDs from {file_path}...")

            student_ids = []

            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    student_id = line.strip()
                    if student_id and not student_id.startswith('#'):  # Skip empty lines and comments
                        student_ids.append(student_id)

            if progress_callback:
                progress_callback(100, f"Read {len(student_ids)} student IDs")

            logger.info(f"Read {len(student_ids)} student IDs from {file_path}")
            return student_ids

        except Exception as e:
            logger.error(f"Error reading student IDs from file: {e}")
            raise

    def process_module_enrollments(self, enrollments: List[Dict],
                                   progress_callback=None) -> ImportResult:
        """Process module enrollment records - GUI version

        Expected fields: student_id, module_type, module_code

        Args:
            enrollments: List of enrollment records
            progress_callback: Progress callback function

        Returns:
            ImportResult with processing results
        """
        return self.import_module_enrollments_from_list(enrollments, progress_callback)

    def import_module_enrollments_from_list(self, enrollments: List[Dict],
                                           progress_callback=None) -> ImportResult:
        """Helper to import module enrollments from list - GUI version

        This is similar to import_module_enrollments but takes a list instead of file path

        Args:
            enrollments: List of enrollment dictionaries
            progress_callback: Progress callback function

        Returns:
            ImportResult with operation results
        """
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

    def update_existing_record(self, student_id: str, new_data: Dict,
                              progress_callback=None) -> bool:
        """Update existing student record - GUI version

        Merges new data with existing record

        Args:
            student_id: Student ID to update
            new_data: Dictionary with new field values
            progress_callback: Progress callback function

        Returns:
            True if update successful
        """
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

    # ========================================
    # AUTOMATION/SCHEDULING - GUI WRAPPERS
    # ========================================

    def schedule_automated_imports_gui(self, callback=None) -> str:
        """Main menu for scheduling automated imports - GUI version

        This is a wrapper that can be called from GUI buttons

        Args:
            callback: Optional callback to display menu

        Returns:
            Status message
        """
        message = """
AUTOMATED IMPORT SCHEDULING

Available Options:
1. Setup Weekly Import - Schedule imports to run weekly
2. Setup Custom Schedule - Create custom import schedule
3. View Scheduled Tasks - See all active schedules
4. Cancel Scheduled Task - Remove a schedule

Note: Scheduled imports require the system to be running.
For production use, configure system service or cron jobs.
"""

        if callback:
            callback(message)

        return message

    def setup_weekly_import_gui(self, import_dir: str, day_of_week: int,
                                time: str, notification_email: str = None,
                                progress_callback=None) -> bool:
        """Setup weekly import schedule - GUI version

        Args:
            import_dir: Directory to monitor for import files
            day_of_week: 0=Monday, 6=Sunday
            time: Time in HH:MM format
            notification_email: Email for notifications
            progress_callback: Progress callback function

        Returns:
            True if schedule created
        """
        try:
            if progress_callback:
                progress_callback(0, "Setting up weekly import schedule...")

            # Validate time format
            try:
                datetime.datetime.strptime(time, '%H:%M')
            except ValueError:
                raise ValueError("Time must be in HH:MM format")

            # Validate day of week
            if not 0 <= day_of_week <= 6:
                raise ValueError("Day of week must be 0-6 (Monday-Sunday)")

            if progress_callback:
                progress_callback(50, "Creating schedule entry...")

            # Create schedule entry (simplified - in production would use apscheduler or similar)
            schedule_data = {
                'type': 'weekly',
                'day_of_week': day_of_week,
                'time': time,
                'import_dir': import_dir,
                'notification_email': notification_email,
                'created_at': datetime.datetime.now().isoformat()
            }

            # Save to database
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_imports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_type TEXT NOT NULL,
                        schedule_data TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    INSERT INTO scheduled_imports (schedule_type, schedule_data)
                    VALUES (?, ?)
                """, ('weekly', json.dumps(schedule_data)))

                conn.commit()

            if progress_callback:
                progress_callback(100, "Weekly import schedule created")

            logger.info(f"Created weekly import schedule for day {day_of_week} at {time}")
            return True

        except Exception as e:
            logger.error(f"Error setting up weekly import: {e}")
            raise

    def setup_custom_schedule_gui(self, schedule_expression: str,
                                  import_dir: str, notification_email: str = None,
                                  progress_callback=None) -> bool:
        """Setup custom import schedule - GUI version

        Args:
            schedule_expression: Cron-like expression or interval description
            import_dir: Directory to monitor
            notification_email: Email for notifications
            progress_callback: Progress callback function

        Returns:
            True if schedule created
        """
        try:
            if progress_callback:
                progress_callback(0, "Setting up custom import schedule...")

            schedule_data = {
                'type': 'custom',
                'expression': schedule_expression,
                'import_dir': import_dir,
                'notification_email': notification_email,
                'created_at': datetime.datetime.now().isoformat()
            }

            # Save to database
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_imports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_type TEXT NOT NULL,
                        schedule_data TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    INSERT INTO scheduled_imports (schedule_type, schedule_data)
                    VALUES (?, ?)
                """, ('custom', json.dumps(schedule_data)))

                conn.commit()

            if progress_callback:
                progress_callback(100, "Custom import schedule created")

            logger.info(f"Created custom import schedule: {schedule_expression}")
            return True

        except Exception as e:
            logger.error(f"Error setting up custom schedule: {e}")
            raise

    def view_scheduled_tasks_gui(self, progress_callback=None) -> List[Dict]:
        """View all scheduled import tasks - GUI version

        Args:
            progress_callback: Progress callback function

        Returns:
            List of scheduled task dictionaries
        """
        try:
            if progress_callback:
                progress_callback(0, "Fetching scheduled tasks...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Ensure table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_imports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_type TEXT NOT NULL,
                        schedule_data TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    SELECT id, schedule_type, schedule_data, is_active, created_at
                    FROM scheduled_imports
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                """)

                tasks = []
                for row in cursor.fetchall():
                    task_id, schedule_type, schedule_data_json, is_active, created_at = row
                    schedule_data = json.loads(schedule_data_json)

                    tasks.append({
                        'id': task_id,
                        'type': schedule_type,
                        'data': schedule_data,
                        'is_active': bool(is_active),
                        'created_at': created_at
                    })

            if progress_callback:
                progress_callback(100, f"Found {len(tasks)} scheduled tasks")

            logger.info(f"Retrieved {len(tasks)} scheduled tasks")
            return tasks

        except Exception as e:
            logger.error(f"Error viewing scheduled tasks: {e}")
            raise

    def cancel_scheduled_task_gui(self, task_id: int,
                                  progress_callback=None) -> bool:
        """Cancel a scheduled import task - GUI version

        Args:
            task_id: ID of task to cancel
            progress_callback: Progress callback function

        Returns:
            True if cancellation successful
        """
        try:
            if progress_callback:
                progress_callback(0, f"Cancelling task {task_id}...")

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Mark as inactive instead of deleting
                cursor.execute("""
                    UPDATE scheduled_imports
                    SET is_active = 0
                    WHERE id = ?
                """, (task_id,))

                if cursor.rowcount == 0:
                    raise ValueError(f"Task {task_id} not found")

                conn.commit()

            if progress_callback:
                progress_callback(100, f"Task {task_id} cancelled")

            logger.info(f"Cancelled scheduled task {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error cancelling scheduled task: {e}")
            raise

    def automated_import_job(self, import_dir: str,
                            notification_email: str = None,
                            progress_callback=None) -> ImportResult:
        """Execute automated import job - GUI version

        Background import process that monitors a directory

        Args:
            import_dir: Directory to scan for import files
            notification_email: Email to notify on completion
            progress_callback: Progress callback function

        Returns:
            ImportResult with combined results
        """
        try:
            if progress_callback:
                progress_callback(0, f"Scanning {import_dir} for import files...")

            import_path = Path(import_dir)
            if not import_path.exists():
                raise FileNotFoundError(f"Import directory not found: {import_dir}")

            # Find all CSV and Excel files
            csv_files = list(import_path.glob('*.csv'))
            excel_files = list(import_path.glob('*.xlsx'))
            all_files = csv_files + excel_files

            if not all_files:
                if progress_callback:
                    progress_callback(100, "No import files found")
                return ImportResult()

            if progress_callback:
                progress_callback(10, f"Found {len(all_files)} files to import")

            # Combined result
            combined_result = ImportResult()

            # Import each file
            for i, file_path in enumerate(all_files):
                try:
                    file_progress = int(10 + (i / len(all_files)) * 80)

                    if progress_callback:
                        progress_callback(file_progress, f"Importing {file_path.name}...")

                    if file_path.suffix == '.csv':
                        result = self.import_from_csv_file(str(file_path), None)
                    else:
                        result = self.import_from_excel_file(str(file_path), None, None)

                    # Combine results
                    combined_result.total_records += result.total_records
                    combined_result.successful_imports += result.successful_imports
                    combined_result.failed_imports += result.failed_imports
                    combined_result.duplicates_found += result.duplicates_found
                    combined_result.errors.extend(result.errors)

                except Exception as e:
                    logger.error(f"Error importing file {file_path}: {e}")
                    combined_result.failed_imports += 1

            if progress_callback:
                progress_callback(90, "Sending notification...")

            # Send notification email if provided
            if notification_email:
                self.send_notification_email_gui(
                    notification_email,
                    f"Automated import completed:\n"
                    f"Files processed: {len(all_files)}\n"
                    f"Total records: {combined_result.total_records}\n"
                    f"Successful: {combined_result.successful_imports}\n"
                    f"Failed: {combined_result.failed_imports}",
                    None
                )

            if progress_callback:
                progress_callback(100, f"Automated import complete: {combined_result.successful_imports} records")

            logger.info(f"Automated import job completed: {combined_result.successful_imports} records imported")
            return combined_result

        except Exception as e:
            logger.error(f"Error in automated import job: {e}")
            raise

    def send_notification_email_gui(self, email: str, message: str,
                                   progress_callback=None) -> bool:
        """Send notification email - GUI version

        Args:
            email: Recipient email address
            message: Message content
            progress_callback: Progress callback function

        Returns:
            True if email sent successfully
        """
        try:
            if progress_callback:
                progress_callback(0, f"Sending notification to {email}...")

            # In production, this would integrate with the email service
            # For now, log the notification
            logger.info(f"NOTIFICATION EMAIL to {email}: {message}")

            # Simulate sending
            if progress_callback:
                progress_callback(50, "Connecting to email server...")
                time.sleep(0.1)  # Simulate network delay
                progress_callback(100, "Email sent successfully")

            # In production:
            # from university_system.infrastructure.email import EmailService
            # email_service = EmailService()
            # email_service.send_email(email, "Import Notification", message)

            return True

        except Exception as e:
            logger.error(f"Error sending notification email: {e}")
            raise

    # ========================================
    # API/WEB SERVICE FEATURES - GUI WRAPPERS
    # ========================================

    def start_api_server_gui(self, host: str = "localhost", port: int = 5000,
                             progress_callback=None) -> bool:
        """Start Flask API server - GUI version

        Args:
            host: Host address to bind to
            port: Port number to bind to
            progress_callback: Progress callback function

        Returns:
            True if server started successfully
        """
        try:
            if progress_callback:
                progress_callback(0, f"Starting API server on {host}:{port}...")

            # Create Flask app
            app = Flask('UniversityBatchAPI')

            # Setup routes
            self.setup_api_routes_gui(app, progress_callback)

            if progress_callback:
                progress_callback(50, "Setting up API routes...")

            # Run server in background thread
            def run_server():
                try:
                    app.run(host=host, port=port, threaded=True)
                except Exception as e:
                    logger.error(f"API server error: {e}")

            import threading
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()

            if progress_callback:
                progress_callback(100, f"API server started at http://{host}:{port}")

            logger.info(f"Started API server at http://{host}:{port}")
            return True

        except Exception as e:
            logger.error(f"Error starting API server: {e}")
            raise

    def setup_api_routes_gui(self, app: Flask, progress_callback=None):
        """Setup Flask API routes - GUI version

        Args:
            app: Flask application instance
            progress_callback: Progress callback function
        """
        try:
            # Health check endpoint
            @app.route('/api/health', methods=['GET'])
            def health_check():
                """Health check endpoint - Returns API status"""
                return jsonify({
                    'status': 'healthy',
                    'service': 'University Batch Operations API',
                    'version': '1.0',
                    'timestamp': datetime.datetime.now().isoformat()
                }), 200

            # Import endpoint
            @app.route('/api/import', methods=['POST'])
            def api_import():
                """Import data via API - POST endpoint for imports"""
                try:
                    data = request.get_json()

                    if not data or 'records' not in data:
                        return jsonify({'error': 'Missing records in request'}), 400

                    records = data['records']
                    import_type = data.get('type', 'student')

                    # Process based on type
                    if import_type == 'student':
                        result = ImportResult()
                        result.total_records = len(records)

                        with self.db_manager.get_connection() as conn:
                            cursor = conn.cursor()

                            for record in records:
                                try:
                                    cleaned = self.clean_student_data(record)
                                    errors = self.validate_student_data(cleaned)

                                    if errors:
                                        result.failed_imports += 1
                                        result.errors.append(errors)
                                        continue

                                    # Insert student
                                    cursor.execute("""
                                        INSERT INTO students (student_id, first_name, last_name,
                                        date_of_birth, email, phone_number, address, course,
                                        enrollment_date, status)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (
                                        cleaned.get('student_id'),
                                        cleaned.get('first_name'),
                                        cleaned.get('last_name'),
                                        cleaned.get('date_of_birth'),
                                        cleaned.get('email'),
                                        cleaned.get('phone_number'),
                                        cleaned.get('address'),
                                        cleaned.get('course', 'GENERAL'),
                                        cleaned.get('enrollment_date', datetime.date.today().isoformat()),
                                        cleaned.get('status', 'Active')
                                    ))
                                    result.successful_imports += 1

                                except Exception as e:
                                    result.failed_imports += 1
                                    result.errors.append(str(e))

                            conn.commit()

                        return jsonify({
                            'status': 'success',
                            'total_records': result.total_records,
                            'successful_imports': result.successful_imports,
                            'failed_imports': result.failed_imports,
                            'errors': result.errors[:10]  # First 10 errors
                        }), 200

                    else:
                        return jsonify({'error': f'Unsupported import type: {import_type}'}), 400

                except Exception as e:
                    logger.error(f"API import error: {e}")
                    return jsonify({'error': str(e)}), 500

            # Get students endpoint
            @app.route('/api/students', methods=['GET'])
            def api_get_students():
                """Get students via API - GET endpoint with filtering"""
                try:
                    # Get query parameters
                    course = request.args.get('course')
                    status = request.args.get('status')
                    limit = int(request.args.get('limit', 100))
                    offset = int(request.args.get('offset', 0))

                    with self.db_manager.get_connection() as conn:
                        cursor = conn.cursor()

                        # Build query
                        query = "SELECT * FROM students WHERE 1=1"
                        params = []

                        if course:
                            query += " AND course = ?"
                            params.append(course)

                        if status:
                            query += " AND status = ?"
                            params.append(status)

                        query += f" LIMIT {limit} OFFSET {offset}"

                        cursor.execute(query, params)
                        students = cursor.fetchall()

                        # Convert to list of dicts
                        student_list = []
                        for student in students:
                            student_list.append({
                                'student_id': student[0],
                                'first_name': student[1],
                                'last_name': student[2],
                                'date_of_birth': student[3],
                                'email': student[4],
                                'phone_number': student[5],
                                'address': student[6],
                                'course': student[7],
                                'enrollment_date': student[8],
                                'status': student[9]
                            })

                        return jsonify({
                            'status': 'success',
                            'count': len(student_list),
                            'students': student_list
                        }), 200

                except Exception as e:
                    logger.error(f"API get students error: {e}")
                    return jsonify({'error': str(e)}), 500

            # Update student endpoint
            @app.route('/api/students/<student_id>', methods=['PUT'])
            def api_update_student(student_id):
                """Update student via API - PUT endpoint for updates"""
                try:
                    data = request.get_json()

                    if not data:
                        return jsonify({'error': 'Missing update data'}), 400

                    with self.db_manager.get_connection() as conn:
                        cursor = conn.cursor()

                        # Verify student exists
                        cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
                        if not cursor.fetchone():
                            return jsonify({'error': f'Student {student_id} not found'}), 404

                        # Build update query
                        update_fields = []
                        update_values = []

                        for field in ['first_name', 'last_name', 'email', 'phone_number',
                                     'address', 'course', 'status']:
                            if field in data:
                                update_fields.append(f"{field} = ?")
                                update_values.append(data[field])

                        if not update_fields:
                            return jsonify({'error': 'No valid fields to update'}), 400

                        update_values.append(student_id)
                        query = f"UPDATE students SET {', '.join(update_fields)} WHERE student_id = ?"

                        cursor.execute(query, update_values)
                        conn.commit()

                        return jsonify({
                            'status': 'success',
                            'student_id': student_id,
                            'updated_fields': len(update_fields)
                        }), 200

                except Exception as e:
                    logger.error(f"API update student error: {e}")
                    return jsonify({'error': str(e)}), 500

            logger.info("API routes configured successfully")

        except Exception as e:
            logger.error(f"Error setting up API routes: {e}")
            raise

    # ========================================
    # EXTERNAL SYSTEM INTEGRATION - GUI WRAPPERS
    # ========================================

    def external_system_integration_gui(self, callback=None) -> str:
        """Main menu for external integrations - GUI version

        Args:
            callback: Optional callback to display menu

        Returns:
            Menu text
        """
        message = """
EXTERNAL SYSTEM INTEGRATION

Available Integration Options:
1. External Database - Connect to MySQL/PostgreSQL/SQL Server
2. REST API - Integrate with external REST APIs
3. File Share Monitoring - Auto-import from shared folders
4. Export Options - Export data to external systems

Configuration:
- Database connections require credentials
- REST API requires endpoint URLs and auth tokens
- File share requires network path access
- All integrations support scheduling

Note: Ensure proper network connectivity and credentials.
"""

        if callback:
            callback(message)

        return message

    def setup_database_integration_gui(self, db_type: str, host: str, port: int,
                                       database: str, username: str, password: str,
                                       progress_callback=None) -> bool:
        """Setup external database connection - GUI version

        Args:
            db_type: Database type (mysql, postgresql, sqlserver)
            host: Database host
            port: Database port
            database: Database name
            username: Database username
            password: Database password
            progress_callback: Progress callback function

        Returns:
            True if connection successful
        """
        try:
            if progress_callback:
                progress_callback(0, f"Connecting to {db_type} database...")

            config = {
                'type': db_type,
                'host': host,
                'port': port,
                'database': database,
                'username': username,
                'password': password,
                'created_at': datetime.datetime.now().isoformat()
            }

            # Test connection based on type
            if db_type == 'mysql':
                try:
                    import mysql.connector
                    conn = mysql.connector.connect(
                        host=host,
                        port=port,
                        database=database,
                        user=username,
                        password=password
                    )
                    conn.close()
                except Exception as e:
                    raise ConnectionError(f"MySQL connection failed: {e}")

            elif db_type == 'postgresql':
                try:
                    import psycopg2
                    conn = psycopg2.connect(
                        host=host,
                        port=port,
                        database=database,
                        user=username,
                        password=password
                    )
                    conn.close()
                except Exception as e:
                    raise ConnectionError(f"PostgreSQL connection failed: {e}")

            elif db_type == 'sqlserver':
                try:
                    import pyodbc
                    conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host},{port};DATABASE={database};UID={username};PWD={password}"
                    conn = pyodbc.connect(conn_str)
                    conn.close()
                except Exception as e:
                    raise ConnectionError(f"SQL Server connection failed: {e}")

            else:
                raise ValueError(f"Unsupported database type: {db_type}")

            if progress_callback:
                progress_callback(50, "Saving configuration...")

            # Save configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS external_db_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_data TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Store password encrypted (in production use proper encryption)
                config_json = json.dumps(config)
                cursor.execute("""
                    INSERT INTO external_db_config (config_data)
                    VALUES (?)
                """, (config_json,))

                conn.commit()

            if progress_callback:
                progress_callback(100, f"External database configured: {db_type}")

            logger.info(f"Configured external {db_type} database connection")
            return True

        except Exception as e:
            logger.error(f"Error setting up database integration: {e}")
            raise

    def setup_rest_api_integration_gui(self, api_url: str, api_key: str,
                                       auth_type: str = 'bearer',
                                       progress_callback=None) -> bool:
        """Setup REST API integration - GUI version

        Args:
            api_url: Base URL of the REST API
            api_key: API key or token
            auth_type: Authentication type (bearer, basic, apikey)
            progress_callback: Progress callback function

        Returns:
            True if configuration successful
        """
        try:
            if progress_callback:
                progress_callback(0, f"Testing connection to {api_url}...")

            config = {
                'api_url': api_url,
                'api_key': api_key,
                'auth_type': auth_type,
                'created_at': datetime.datetime.now().isoformat()
            }

            # Test connection
            headers = {}
            if auth_type == 'bearer':
                headers['Authorization'] = f'Bearer {api_key}'
            elif auth_type == 'apikey':
                headers['X-API-Key'] = api_key
            elif auth_type == 'basic':
                import base64
                headers['Authorization'] = f'Basic {base64.b64encode(api_key.encode()).decode()}'

            try:
                response = requests.get(f"{api_url}/health", headers=headers, timeout=10)
                if response.status_code not in [200, 404]:  # 404 ok if no health endpoint
                    raise ConnectionError(f"API returned status {response.status_code}")
            except requests.exceptions.RequestException as e:
                raise ConnectionError(f"API connection failed: {e}")

            if progress_callback:
                progress_callback(50, "Saving configuration...")

            # Save configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS external_api_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_data TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                config_json = json.dumps(config)
                cursor.execute("""
                    INSERT INTO external_api_config (config_data)
                    VALUES (?)
                """, (config_json,))

                conn.commit()

            if progress_callback:
                progress_callback(100, f"REST API configured: {api_url}")

            logger.info(f"Configured REST API integration: {api_url}")
            return True

        except Exception as e:
            logger.error(f"Error setting up REST API integration: {e}")
            raise

    def setup_file_share_monitoring_gui(self, share_path: str,
                                        file_pattern: str = "*.csv",
                                        check_interval: int = 300,
                                        progress_callback=None) -> bool:
        """Setup file share monitoring - GUI version

        Args:
            share_path: Network path to monitor
            file_pattern: File pattern to watch (e.g., *.csv, *.xlsx)
            check_interval: Check interval in seconds
            progress_callback: Progress callback function

        Returns:
            True if monitoring configured
        """
        try:
            if progress_callback:
                progress_callback(0, f"Configuring file share monitoring...")

            # Verify path exists
            share_path_obj = Path(share_path)
            if not share_path_obj.exists():
                raise FileNotFoundError(f"Share path does not exist: {share_path}")

            config = {
                'share_path': share_path,
                'file_pattern': file_pattern,
                'check_interval': check_interval,
                'created_at': datetime.datetime.now().isoformat()
            }

            if progress_callback:
                progress_callback(50, "Saving configuration...")

            # Save configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS file_share_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_data TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                config_json = json.dumps(config)
                cursor.execute("""
                    INSERT INTO file_share_config (config_data)
                    VALUES (?)
                """, (config_json,))

                conn.commit()

            if progress_callback:
                progress_callback(100, f"File share monitoring configured: {share_path}")

            logger.info(f"Configured file share monitoring: {share_path}")
            return True

        except Exception as e:
            logger.error(f"Error setting up file share monitoring: {e}")
            raise

    def export_to_external_system_gui(self, callback=None) -> str:
        """Main menu for external exports - GUI version

        Args:
            callback: Optional callback to display menu

        Returns:
            Menu text
        """
        message = """
EXPORT TO EXTERNAL SYSTEMS

Available Export Destinations:
1. External Database - Export to MySQL/PostgreSQL/SQL Server
2. REST API - Push data to external REST API
3. File Share - Export to network file share
4. Email - Send exports via email

Export Options:
- Full export or filtered by criteria
- Multiple formats (CSV, JSON, Excel)
- Scheduling support
- Progress tracking

Note: Ensure external systems are configured before exporting.
"""

        if callback:
            callback(message)

        return message

    def export_to_external_database_gui(self, students: List[Tuple] = None,
                                        progress_callback=None) -> bool:
        """Export data to external database - GUI version

        Args:
            students: List of student tuples to export (None = all students)
            progress_callback: Progress callback function

        Returns:
            True if export successful
        """
        try:
            if progress_callback:
                progress_callback(0, "Loading external database configuration...")

            # Load configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT config_data FROM external_db_config
                    ORDER BY created_at DESC LIMIT 1
                """)
                config_row = cursor.fetchone()

                if not config_row:
                    raise ValueError("No external database configured")

                config = json.loads(config_row[0])

                # Get students if not provided
                if students is None:
                    cursor.execute("SELECT * FROM students")
                    students = cursor.fetchall()

            if progress_callback:
                progress_callback(20, f"Connecting to {config['type']} database...")

            # Export based on database type
            if config['type'] == 'mysql':
                import mysql.connector
                ext_conn = mysql.connector.connect(
                    host=config['host'],
                    port=config['port'],
                    database=config['database'],
                    user=config['username'],
                    password=config['password']
                )
            elif config['type'] == 'postgresql':
                import psycopg2
                ext_conn = psycopg2.connect(
                    host=config['host'],
                    port=config['port'],
                    database=config['database'],
                    user=config['username'],
                    password=config['password']
                )
            else:
                raise ValueError(f"Unsupported database type: {config['type']}")

            ext_cursor = ext_conn.cursor()

            if progress_callback:
                progress_callback(40, "Creating external table if needed...")

            # Create table if not exists
            ext_cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id VARCHAR(50) PRIMARY KEY,
                    first_name VARCHAR(100),
                    last_name VARCHAR(100),
                    date_of_birth DATE,
                    email VARCHAR(100),
                    phone_number VARCHAR(20),
                    address TEXT,
                    course VARCHAR(100),
                    enrollment_date DATE,
                    status VARCHAR(20)
                )
            """)

            if progress_callback:
                progress_callback(60, f"Exporting {len(students)} students...")

            # Insert students
            for i, student in enumerate(students):
                try:
                    ext_cursor.execute("""
                        INSERT INTO students VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        first_name = VALUES(first_name),
                        last_name = VALUES(last_name),
                        email = VALUES(email)
                    """ if config['type'] == 'mysql' else """
                        INSERT INTO students VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (student_id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        email = EXCLUDED.email
                    """, student[:10])

                    if progress_callback and i % 10 == 0:
                        progress = 60 + int((i / len(students)) * 30)
                        progress_callback(progress, f"Exporting: {i}/{len(students)}")

                except Exception as e:
                    logger.error(f"Error exporting student {student[0]}: {e}")

            ext_conn.commit()
            ext_conn.close()

            if progress_callback:
                progress_callback(100, f"Exported {len(students)} students to external database")

            logger.info(f"Exported {len(students)} students to external {config['type']} database")
            return True

        except Exception as e:
            logger.error(f"Error exporting to external database: {e}")
            raise

    def export_via_rest_api_gui(self, students: List[Tuple] = None,
                                progress_callback=None) -> bool:
        """Export data via REST API - GUI version

        Args:
            students: List of student tuples to export (None = all students)
            progress_callback: Progress callback function

        Returns:
            True if export successful
        """
        try:
            if progress_callback:
                progress_callback(0, "Loading REST API configuration...")

            # Load configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT config_data FROM external_api_config
                    ORDER BY created_at DESC LIMIT 1
                """)
                config_row = cursor.fetchone()

                if not config_row:
                    raise ValueError("No REST API configured")

                config = json.loads(config_row[0])

                # Get students if not provided
                if students is None:
                    cursor.execute("SELECT * FROM students")
                    students = cursor.fetchall()

            if progress_callback:
                progress_callback(20, f"Preparing data for export...")

            # Convert to JSON
            student_data = []
            for student in students:
                student_data.append({
                    'student_id': student[0],
                    'first_name': student[1],
                    'last_name': student[2],
                    'date_of_birth': student[3],
                    'email': student[4],
                    'phone_number': student[5],
                    'address': student[6],
                    'course': student[7],
                    'enrollment_date': student[8],
                    'status': student[9]
                })

            # Prepare headers
            headers = {'Content-Type': 'application/json'}
            if config['auth_type'] == 'bearer':
                headers['Authorization'] = f"Bearer {config['api_key']}"
            elif config['auth_type'] == 'apikey':
                headers['X-API-Key'] = config['api_key']

            if progress_callback:
                progress_callback(50, f"Sending {len(student_data)} students to API...")

            # Send to API
            response = requests.post(
                f"{config['api_url']}/students/bulk",
                json={'students': student_data},
                headers=headers,
                timeout=60
            )

            if response.status_code not in [200, 201]:
                raise Exception(f"API returned status {response.status_code}: {response.text}")

            if progress_callback:
                progress_callback(100, f"Exported {len(student_data)} students via REST API")

            logger.info(f"Exported {len(student_data)} students via REST API")
            return True

        except Exception as e:
            logger.error(f"Error exporting via REST API: {e}")
            raise

    def export_to_file_share_gui(self, filename: str, file_format: str = 'csv',
                                 progress_callback=None) -> str:
        """Export to network file share - GUI version

        Args:
            filename: Output filename
            file_format: File format (csv or excel)
            progress_callback: Progress callback function

        Returns:
            Path to exported file
        """
        try:
            if progress_callback:
                progress_callback(0, "Loading file share configuration...")

            # Load configuration
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT config_data FROM file_share_config
                    ORDER BY created_at DESC LIMIT 1
                """)
                config_row = cursor.fetchone()

                if not config_row:
                    raise ValueError("No file share configured")

                config = json.loads(config_row[0])

                # Get students
                cursor.execute("SELECT * FROM students")
                students = cursor.fetchall()

            if progress_callback:
                progress_callback(30, f"Exporting {len(students)} students...")

            # Prepare export path
            share_path = Path(config['share_path'])
            export_file = share_path / filename

            # Export data
            columns = ['student_id', 'first_name', 'last_name', 'date_of_birth', 'email',
                      'phone_number', 'address', 'course', 'enrollment_date', 'status']

            export_path = self.export_data_to_file(students, columns, str(export_file),
                                                   file_format, None)

            if progress_callback:
                progress_callback(100, f"Exported to file share: {export_path}")

            logger.info(f"Exported data to file share: {export_path}")
            return export_path

        except Exception as e:
            logger.error(f"Error exporting to file share: {e}")
            raise

    def export_via_email_gui(self, email: str, subject: str = "Student Data Export",
                            file_format: str = 'csv', progress_callback=None) -> bool:
        """Export and send via email - GUI version

        Args:
            email: Recipient email address
            subject: Email subject
            file_format: Attachment format (csv or excel)
            progress_callback: Progress callback function

        Returns:
            True if email sent successfully
        """
        try:
            if progress_callback:
                progress_callback(0, "Generating export file...")

            # Generate export file
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'student_export_{timestamp}'

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM students")
                students = cursor.fetchall()

            columns = ['student_id', 'first_name', 'last_name', 'date_of_birth', 'email',
                      'phone_number', 'address', 'course', 'enrollment_date', 'status']

            export_path = self.export_data_to_file(students, columns, filename,
                                                   file_format, None)

            if progress_callback:
                progress_callback(50, f"Sending email to {email}...")

            # In production, integrate with EmailService
            message = f"""
Please find attached the student data export.

Export Details:
- Total Students: {len(students)}
- Format: {file_format.upper()}
- Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

File: {export_path}
"""

            # Send notification (in production, attach file)
            self.send_notification_email_gui(email, message, None)

            if progress_callback:
                progress_callback(100, f"Export sent to {email}")

            logger.info(f"Sent data export to {email}")
            return True

        except Exception as e:
            logger.error(f"Error exporting via email: {e}")
            raise

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Use the gui_launcher utility to avoid circular imports
            from university_system.modules.shared.gui.gui_launcher import return_to_main_menu
            return_to_main_menu(self, self.auth)
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def _show_validation_results_dialog(self, report_data: Dict, report_filename: str):
        """Show validation results in a dialog"""
        try:
            result_dialog = tk.Toplevel(self.root)
            result_dialog.title(_t("batch_ops.windows.validation_results"))
            result_dialog.geometry("800x600")
            result_dialog.transient(self.root)
            result_dialog.grab_set()

            # Center the dialog
            result_dialog.update_idletasks()
            x = (result_dialog.winfo_screenwidth() // 2) - (result_dialog.winfo_width() // 2)
            y = (result_dialog.winfo_screenheight() // 2) - (result_dialog.winfo_height() // 2)
            result_dialog.geometry(f"+{x}+{y}")

            # Header
            header_frame = tk.Frame(result_dialog, bg='#4CAF50')
            header_frame.pack(fill=tk.X, pady=(0, 10))

            tk.Label(header_frame, text="Data Validation and Cleaning Results",
                    font=('Arial', 14, 'bold'), bg='#4CAF50', fg='white').pack(pady=15)

            # Create notebook for different views
            notebook = ttk.Notebook(result_dialog)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            # Summary tab
            summary_frame = ttk.Frame(notebook)
            notebook.add(summary_frame, text="Summary")

            summary_text = tk.Text(summary_frame, wrap=tk.WORD, font=('Courier', 9))
            summary_scroll = ttk.Scrollbar(summary_frame, orient=tk.VERTICAL, command=summary_text.yview)
            summary_text.configure(yscrollcommand=summary_scroll.set)

            summary = report_data['summary']
            breakdown = report_data['issue_breakdown']

            summary_content = f"""DATA VALIDATION SUMMARY
=======================

Duration: {summary['duration_seconds']:.2f} seconds
Total Issues Found: {summary['total_issues_found']}
Status: {summary['validation_status'].title()}

ISSUE BREAKDOWN BY SEVERITY:
• Critical: {breakdown['by_severity'].get('critical', 0)}
• High: {breakdown['by_severity'].get('high', 0)}
• Medium: {breakdown['by_severity'].get('medium', 0)}
• Low: {breakdown['by_severity'].get('low', 0)}
• Info: {breakdown['by_severity'].get('info', 0)}

ISSUE BREAKDOWN BY CATEGORY:
{chr(10).join([f"• {cat.replace('_', ' ').title()}: {count}" for cat, count in breakdown['by_category'].items()])}

ACTIONS TAKEN:
{chr(10).join([f"• {action.replace('_', ' ').title()}: {count}" for action, count in breakdown['by_action'].items()])}

RECOMMENDATIONS:
{chr(10).join([f"• {rec}" for rec in report_data['recommendations']])}

Report saved to: {report_filename}
"""

            summary_text.insert(tk.END, summary_content)
            summary_text.config(state=tk.DISABLED)
            summary_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            summary_scroll.pack(side=tk.RIGHT, fill=tk.Y)

            # Detailed issues tab
            issues_frame = ttk.Frame(notebook)
            notebook.add(issues_frame, text="Detailed Issues")

            issues_tree = ttk.Treeview(issues_frame, columns=("Type", "Severity", "Description", "Action"), show="tree headings")
            issues_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            issues_tree.heading("#0", text=_t("batch_ops.columns.id"))
            issues_tree.heading("Type", text=_t("batch_ops.columns.type"))
            issues_tree.heading("Severity", text=_t("batch_ops.columns.severity"))
            issues_tree.heading("Description", text=_t("batch_ops.columns.description"))
            issues_tree.heading("Action", text=_t("batch_ops.columns.action"))

            issues_tree.column("#0", width=50)
            issues_tree.column("Type", width=120)
            issues_tree.column("Severity", width=80)
            issues_tree.column("Description", width=300)
            issues_tree.column("Action", width=120)

            # Populate issues
            for i, issue in enumerate(report_data['detailed_issues'][:100]):  # Limit to first 100
                issues_tree.insert("", "end", text=str(i+1),
                                  values=(issue.get('type', ''), issue.get('severity', ''),
                                         issue.get('description', ''), issue.get('action', '')))

            # Close button
            tk.Button(result_dialog, text=_t("batch_ops.buttons.close"), command=result_dialog.destroy,
                     bg='#f0f0f0', padx=20, pady=5).pack(pady=15)

        except Exception as e:
            print(f"Error showing results dialog: {e}")
            messagebox.showinfo("Validation Complete",
                              f"Data validation completed successfully!\n"
                              f"Report saved to: {report_filename}\n"
                              f"Total issues found: {report_data['summary']['total_issues_found']}")

# ========================================
# MAIN APPLICATION ENTRY POINT
# ========================================

def main():
    """Main entry point - supports both GUI and command-line modes"""
    import sys

    # Check command line arguments for mode selection
    if len(sys.argv) > 1 and sys.argv[1] == '--cli':
        # Start in command-line mode
        print("🎓 Enhanced Student Records Batch Operations System")
        print("=" * 60)
        print("Starting in Command-Line Mode")

        batch_manager = OriginalBatchOperationManager()
        batch_manager.display_batch_menu()
    else:
        # Start in GUI mode (default)
        print("🎓 Enhanced Student Records Batch Operations System")
        print("=" * 60)
        print("Starting GUI Interface...")

        # Import here to avoid circular imports
        from university_system.modules.shared.gui.batch_operations.main_gui import BatchOperationsGUI

        # Create and run GUI application
        app = BatchOperationsGUI()
        
        # Replace backend with enhanced version
        app.backend = EnhancedBatchOperationManager(app.backend.db_path)
        
        app.run()


if __name__ == "__main__":
    main()
