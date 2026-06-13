import os
import csv
import json
import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.core.i18n import get_text as _t
from education_system.university_system.modules.domain.academics.services.modules import (
    compulsory_module_1, compulsory_module_2,
    optional_module_1, optional_module_2,
    CS_optional_module_1, CS_optional_module_2,
    DS_optional_module_1, DS_optional_module_2,
)
from education_system.university_system.modules.shared.utils.batch_operations.models import ProgressTracker

logger = configure_logging(name=__name__)


class ImportOpsMixin:
    """Mixin providing file import operations."""

    def import_from_csv(self):
        """Enhanced CSV import with progress tracking"""
        print("\n" + _t("shared.utils.batch_operations.title_import_csv"))
        file_path = self.get_import_file_path('CSV')
        if not file_path:
            return

        # Create backup before import
        backup_path = self.create_database_backup(auto=True)
        print(_t("shared.utils.batch_operations.backup_created", path=backup_path))

        try:
            # Read and validate file
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
                sample = csvfile.read(1024)
                csvfile.seek(0)

                # Detect delimiter
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter

                reader = csv.DictReader(csvfile, delimiter=delimiter)
                if not reader.fieldnames:
                    print(_t("shared.utils.batch_operations.error_no_headers"))
                    return

                # Clean headers
                reader.fieldnames = [header.strip().lower().replace(' ', '_') for header in reader.fieldnames]

                # Check required headers
                required_headers = ['first_name', 'last_name', 'gender', 'dob', 'course']
                missing_headers = [h for h in required_headers if h not in reader.fieldnames]
                if missing_headers:
                    print(_t("shared.utils.batch_operations.error_missing_headers", headers=', '.join(missing_headers)))
                    return

                # Count total records first
                records = list(reader)
                total_records = len(records)
                print(_t("shared.utils.batch_operations.found_records", count=total_records))

                # Initialize progress tracker
                progress = ProgressTracker(total_records, "Validating records")

                # Process records with progress tracking
                valid_records = []
                error_records = []

                for i, row in enumerate(records):
                    # Clean data
                    cleaned_row = self.clean_student_data(row)

                    # Validate
                    errors = self.validate_student_data(cleaned_row)

                    if errors:
                        error_records.append({
                            'row': i + 2,  # +2 for header and 0-based index
                            'data': cleaned_row,
                            'errors': errors
                        })
                    else:
                        valid_records.append(cleaned_row)

                    progress.update()

                # Report validation results
                print("\n" + _t("shared.utils.batch_operations.validation_complete", valid=len(valid_records), errors=len(error_records)))

                if error_records:
                    self.display_validation_errors(error_records)

                    choice = input("\n" + _t("shared.utils.batch_operations.prompt_error_action"))

                    if choice == '2':
                        valid_records.extend(self.interactive_error_resolution(error_records))
                    elif choice != '1':
                        print(_t("shared.utils.batch_operations.import_cancelled"))
                        return

                if not valid_records:
                    print(_t("shared.utils.batch_operations.no_valid_records"))
                    return

                # Import valid records
                result = self.import_valid_records(valid_records)
                self.save_import_history(result, file_path, 'CSV Import')

        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            print(_t("shared.utils.batch_operations.error_reading_csv", error=str(e)))

    def import_from_excel(self):
        """Enhanced Excel import with sheet selection"""
        print("\n" + _t("shared.utils.batch_operations.title_import_excel"))
        file_path = self.get_import_file_path('Excel')
        if not file_path:
            return

        try:
            # Check available sheets
            xl_file = pd.ExcelFile(file_path)
            if len(xl_file.sheet_names) > 1:
                print("\n" + _t("shared.utils.batch_operations.available_sheets"))
                for i, sheet in enumerate(xl_file.sheet_names, 1):
                    print(f"{i}. {sheet}")

                while True:
                    try:
                        sheet_choice = int(input(_t("shared.utils.batch_operations.prompt_select_sheet"))) - 1
                        if 0 <= sheet_choice < len(xl_file.sheet_names):
                            sheet_name = xl_file.sheet_names[sheet_choice]
                            break
                        else:
                            print(_t("shared.utils.batch_operations.invalid_sheet_number"))
                    except ValueError:
                        print(_t("shared.utils.batch_operations.enter_valid_number"))
            else:
                sheet_name = xl_file.sheet_names[0]

            # Create backup
            backup_path = self.create_database_backup(auto=True)
            print(_t("shared.utils.batch_operations.backup_created", path=backup_path))

            # Read the Excel file
            df = pd.read_excel(file_path, sheet_name=sheet_name)

            if df.empty:
                print(_t("shared.utils.batch_operations.error_no_data"))
                return

            # Clean column names
            df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]

            # Check required columns
            required_columns = ['first_name', 'last_name', 'gender', 'dob', 'course']
            missing_columns = [c for c in required_columns if c not in df.columns]
            if missing_columns:
                print(_t("shared.utils.batch_operations.error_missing_columns", columns=', '.join(missing_columns)))
                return

            # Convert to records and process
            records = df.to_dict('records')
            total_records = len(records)
            print(_t("shared.utils.batch_operations.found_records_sheet", count=total_records, sheet=sheet_name))

            # Process with progress tracking
            progress = ProgressTracker(total_records, "Processing Excel records")
            valid_records = []
            error_records = []

            for i, record in enumerate(records):
                # Convert NaN to None and clean data
                record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
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

                progress.update()

            # Handle results similar to CSV import
            print("\n" + _t("shared.utils.batch_operations.validation_complete", valid=len(valid_records), errors=len(error_records)))

            if error_records:
                self.display_validation_errors(error_records)

                choice = input("\n" + _t("shared.utils.batch_operations.prompt_error_action"))

                if choice == '2':
                    valid_records.extend(self.interactive_error_resolution(error_records))
                elif choice != '1':
                    print(_t("shared.utils.batch_operations.import_cancelled"))
                    return

            if valid_records:
                result = self.import_valid_records(valid_records)
                self.save_import_history(result, file_path, f'Excel Import ({sheet_name})')

        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            print(_t("shared.utils.batch_operations.error_reading_excel", error=str(e)))

    def multi_file_import(self):
        """Import from multiple files in a directory"""
        print("\n" + _t("shared.utils.batch_operations.title_multi_file"))

        directory = input(_t("shared.utils.batch_operations.prompt_directory"))
        if not os.path.exists(directory):
            print(_t("shared.utils.batch_operations.error_directory_not_found"))
            return

        # Find supported files
        supported_extensions = ['.csv', '.xlsx', '.xls']
        files = []

        for ext in supported_extensions:
            files.extend(Path(directory).glob(f"*{ext}"))

        if not files:
            print(_t("shared.utils.batch_operations.error_no_supported_files"))
            return

        print("\n" + _t("shared.utils.batch_operations.found_files", count=len(files)))
        for i, file in enumerate(files, 1):
            print(f"{i}. {file.name}")

        confirm = input("\n" + _t("shared.utils.batch_operations.prompt_process_all", count=len(files)))
        if confirm.lower() != 'y':
            return

        # Create backup
        backup_path = self.create_database_backup(auto=True)
        print(_t("shared.utils.batch_operations.backup_created", path=backup_path))

        # Process each file
        total_imported = 0
        total_errors = 0

        for file_path in files:
            print("\n" + _t("shared.utils.batch_operations.processing_file", filename=file_path.name))

            try:
                if file_path.suffix.lower() == '.csv':
                    records = self.read_csv_file(str(file_path))
                else:
                    records = self.read_excel_file(str(file_path))

                if records:
                    result = self.import_valid_records(records)
                    total_imported += result.successful_imports
                    total_errors += result.failed_imports
                    print(_t("shared.utils.batch_operations.records_imported_from", count=result.successful_imports, filename=file_path.name))

            except Exception as e:
                print(_t("shared.utils.batch_operations.error_processing_file", filename=file_path.name, error=str(e)))
                total_errors += 1

        print("\n" + _t("shared.utils.batch_operations.multi_file_complete"))
        print(_t("shared.utils.batch_operations.total_imported", count=total_imported))
        print(_t("shared.utils.batch_operations.total_errors", count=total_errors))

    def import_with_duplicate_detection(self):
        """Import with intelligent duplicate detection"""
        print("\n" + _t("shared.utils.batch_operations.title_duplicate_detection"))

        file_path = self.get_import_file_path('CSV or Excel')
        if not file_path:
            return

        # Read file
        if file_path.lower().endswith('.csv'):
            records = self.read_csv_file(file_path)
        else:
            records = self.read_excel_file(file_path)

        if not records:
            return

        print("\n" + _t("shared.utils.batch_operations.processing_duplicates", count=len(records)))

        # Create backup
        backup_path = self.create_database_backup(auto=True)
        print(_t("shared.utils.batch_operations.backup_created", path=backup_path))

        # Check for duplicates
        duplicates = self.find_duplicates_in_import(records)

        if duplicates:
            print("\n" + _t("shared.utils.batch_operations.found_duplicates", count=len(duplicates)))

            for i, dup in enumerate(duplicates[:5], 1):  # Show first 5
                print(f"{i}. {dup['import_record']['first_name']} {dup['import_record']['last_name']} "
                      f"matches existing student {dup['existing_record'][3]} {dup['existing_record'][5]} "
                      f"(ID: {dup['existing_record'][0]}) - Confidence: {dup['confidence']:.0%}")

            if len(duplicates) > 5:
                print(_t("shared.utils.batch_operations.and_more", count=len(duplicates) - 5))

            print("\n" + _t("shared.utils.batch_operations.duplicate_options"))
            print(_t("shared.utils.batch_operations.option_skip_duplicates"))
            print(_t("shared.utils.batch_operations.option_update_existing"))
            print(_t("shared.utils.batch_operations.option_handle_individually"))
            print(_t("shared.utils.batch_operations.option_import_anyway"))

            choice = input(_t("shared.utils.batch_operations.prompt_choose_option"))

            result = self.handle_duplicates(records, duplicates, choice)
            self.save_import_history(result, file_path, 'Import with Duplicate Detection')
        else:
            print(_t("shared.utils.batch_operations.no_duplicates_found"))
            result = self.import_valid_records(records)
            self.save_import_history(result, file_path, 'Import with Duplicate Detection')

    def preview_import(self):
        """Preview import changes without committing"""
        print("\n" + _t("shared.utils.batch_operations.title_preview_import"))

        file_path = self.get_import_file_path('CSV or Excel')
        if not file_path:
            return

        # Read file
        if file_path.lower().endswith('.csv'):
            records = self.read_csv_file(file_path)
        else:
            records = self.read_excel_file(file_path)

        if not records:
            return

        print("\n" + _t("shared.utils.batch_operations.preview_of_records", count=len(records)))
        print("-" * 80)

        # Show first few records
        for i, record in enumerate(records[:5], 1):
            print(f"{i}. {record.get('first_name', 'N/A')} {record.get('last_name', 'N/A')} "
                  f"({record.get('course', 'N/A')}) - {record.get('email_address', 'Auto-generated')}")

        if len(records) > 5:
            print(_t("shared.utils.batch_operations.and_more_records", count=len(records) - 5))

        # Check for duplicates
        duplicates = self.find_duplicates_in_import(records)
        if duplicates:
            print("\n" + _t("shared.utils.batch_operations.duplicates_detected", count=len(duplicates)))

        # Show what modules would be assigned
        sample_record = records[0]
        course = sample_record.get('course', 'CS')
        print("\n" + _t("shared.utils.batch_operations.modules_assigned", course=course))
        print(f"- {compulsory_module_1['name']} (Compulsory)")
        print(f"- {compulsory_module_2['name']} (Compulsory)")
        print(f"- {optional_module_1['name']} (Optional)")
        print(f"- {optional_module_2['name']} (Optional)")

        if course == 'CS':
            print(f"- {CS_optional_module_1['name']} (CS Optional)")
            print(f"- {CS_optional_module_2['name']} (CS Optional)")
        else:
            print(f"- {DS_optional_module_1['name']} (DS Optional)")
            print(f"- {DS_optional_module_2['name']} (DS Optional)")

        print("\n" + _t("shared.utils.batch_operations.preview_complete"))

        proceed = input("\n" + _t("shared.utils.batch_operations.prompt_proceed_import"))
        if proceed.lower() == 'y':
            result = self.import_valid_records(records)
            self.save_import_history(result, file_path, 'Import after Preview')

    def resume_failed_import(self):
        """Resume a previously failed import operation"""
        print("\n" + _t("shared.utils.batch_operations.title_resume_import"))

        # Check for saved import state
        resume_files = list(Path('.').glob('import_resume_*.json'))

        if not resume_files:
            print(_t("shared.utils.batch_operations.no_failed_imports"))
            return

        print("\n" + _t("shared.utils.batch_operations.available_imports"))
        for i, file in enumerate(resume_files, 1):
            # Extract timestamp from filename
            timestamp = file.stem.replace('import_resume_', '')
            print(f"{i}. {_t('shared.utils.batch_operations.import_from', timestamp=timestamp)}")

        try:
            choice = int(input(_t("shared.utils.batch_operations.prompt_select_import"))) - 1
            if 0 <= choice < len(resume_files):
                resume_file = resume_files[choice]

                # Load saved state
                with open(resume_file, 'r') as f:
                    saved_state = json.load(f)

                remaining_records = saved_state['remaining_records']
                original_total = saved_state['original_total']
                processed_count = original_total - len(remaining_records)

                print("\n" + _t("shared.utils.batch_operations.resuming_import", processed=processed_count, total=original_total))
                print(_t("shared.utils.batch_operations.records_remaining", count=len(remaining_records)))

                confirm = input(_t("shared.utils.batch_operations.prompt_continue_remaining"))
                if confirm.lower() == 'y':
                    result = self.import_valid_records(remaining_records)

                    # Clean up resume file
                    os.remove(resume_file)
                    print(_t("shared.utils.batch_operations.resume_file_cleaned"))

                    self.save_import_history(result, saved_state['original_file'], 'Resumed Import')
            else:
                print(_t("shared.utils.batch_operations.invalid_selection"))

        except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
            print(_t("shared.utils.batch_operations.error_resuming", error=str(e)))

    def read_csv_file(self, file_path: str) -> List[Dict]:
        """Read and validate CSV file, return cleaned records"""
        try:
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
                sample = csvfile.read(1024)
                csvfile.seek(0)

                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter

                reader = csv.DictReader(csvfile, delimiter=delimiter)
                reader.fieldnames = [header.strip().lower().replace(' ', '_') for header in reader.fieldnames]

                records = []
                for row in reader:
                    cleaned = self.clean_student_data(row)
                    errors = self.validate_student_data(cleaned)
                    if not errors:
                        records.append(cleaned)

                return records
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return []

    def read_excel_file(self, file_path: str) -> List[Dict]:
        """Read and validate Excel file, return cleaned records"""
        try:
            df = pd.read_excel(file_path)
            df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]

            records = []
            for record in df.to_dict('records'):
                record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
                cleaned = self.clean_student_data(record)
                errors = self.validate_student_data(cleaned)
                if not errors:
                    records.append(cleaned)

            return records
        except Exception as e:
            logger.error(f"Error reading Excel: {e}")
            return []
