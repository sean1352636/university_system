"""Import handlers mixin - CSV/Excel imports, import processing, file I/O utilities."""

from education_system.university_system.modules.shared.gui.batch_operations.constants import (
    csv, datetime, json, logging,
    Path, Dict, List, Optional,
    pd,
    DATA_DIR, DEFAULT_DB_PATH,
    sqlite3,
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2, optional_module_3, optional_module_4,
    CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
    DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4,
    logger,
)

from education_system.university_system.modules.shared.gui.batch_operations.models import ImportResult


class ImportHandlersMixin:
    """Mixin providing CSV/Excel import, record processing, and file I/O methods."""

    def import_from_csv_file(self, file_path: str, progress_callback=None) -> ImportResult:
        """GUI-friendly CSV import with progress callback"""
        self.progress_callback = progress_callback

        try:
            # Create backup
            backup_path = self.create_database_backup(auto=True)

            # Read and validate file
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
                sample = csvfile.read(4096)
                csvfile.seek(0)

                # Detect delimiter with fallback
                try:
                    sniffer = csv.Sniffer()
                    delimiter = sniffer.sniff(sample).delimiter
                except csv.Error:
                    # Sniffer failed — try common delimiters by frequency in sample
                    for candidate in [',', '\t', ';', '|']:
                        if candidate in sample:
                            delimiter = candidate
                            break
                    else:
                        delimiter = ','  # default to comma

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
            data = pd.read_excel(file_path, sheet_name=sheet_name)

            # pd.read_excel returns a dict of DataFrames when sheet_name is None
            if isinstance(data, dict):
                # Use the first sheet
                first_key = next(iter(data))
                df = data[first_key]
            else:
                df = data

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
            # Disable FK checks so INSERT OR REPLACE doesn't fail
            # when updating existing students that have module records
            cursor.execute("PRAGMA foreign_keys = OFF")

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
                    # Use student_id from file, or generate one
                    student_id = record.get('student_id') or str(int(datetime.datetime.now().timestamp() * 1000000 + i) % 10000000).zfill(7)

                    # Create email if not provided (check both column name variants)
                    email_address = record.get('email_address') or record.get('email') or f"C{student_id}@tees.ac.uk"

                    # Gender and title — optional
                    gender = (record.get('gender') or '').lower() or None
                    title = {'male': 'Mr', 'female': 'Miss'}.get(gender or '', '')

                    # DOB and age — optional
                    dob_value = record.get('dob') or record.get('date_of_birth')
                    dob_str = None
                    age = None
                    if dob_value and str(dob_value).strip().lower() not in ('none', '', 'nat'):
                        try:
                            dob = datetime.datetime.strptime(str(dob_value).strip()[:10], "%Y-%m-%d")
                            now = datetime.datetime.now()
                            age = now.year - dob.year - ((now.month, now.day) < (dob.month, dob.day))
                            dob_str = str(dob_value).strip()[:10]
                        except ValueError:
                            pass  # unparseable date — leave as None

                    # Registration date — use file value or now
                    registration_datetime = record.get('registration_date') or record.get('registration_datetime') or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Insert student
                    cursor.execute('''
                    INSERT OR REPLACE INTO students
                    (student_id, email_address, title, first_name, middle_name, last_name, gender, dob, age, course, registration_datetime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        student_id,
                        email_address,
                        title,
                        record['first_name'],
                        record.get('middle_name', ''),
                        record['last_name'],
                        gender,
                        dob_str,
                        age,
                        record['course'].upper(),
                        registration_datetime
                    ))

                    # Insert modules — use file columns if present, else default set
                    module_codes = []
                    for key, value in record.items():
                        if key.startswith('module_') and value:
                            # Handle "CODE - name" format or bare codes
                            code = str(value).split(' - ')[0].strip()
                            if code:
                                module_codes.append(code)

                    if module_codes:
                        module_data = [(student_id, code) for code in module_codes]
                    else:
                        # Fallback to default module set
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
                    INSERT OR IGNORE INTO student_modules (student_id, module_code)
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
            try:
                conn.execute("PRAGMA foreign_keys = ON")
            except Exception:
                pass
            conn.close()
            result.end_time = datetime.datetime.now()

        return result

    def import_valid_records(self, records: List[Dict]) -> ImportResult:
        """Import only valid records after filtering - wrapper for GUI compatibility"""
        return self.import_valid_records_with_progress(records, start_progress=0)

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
        """Interactive menu to fix validation errors - GUI version"""
        fixed_records = []

        if not resolution_callback:
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
        """Fix individual record interactively - GUI version"""
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
