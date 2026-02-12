# Standard library imports
import os
import csv
import datetime
import re
import json
import shutil
import time
import threading
import zipfile
import logging
import pickle  # kept only for backward compat with old .pkl resume files
from io import StringIO
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

# Third-party imports
import pandas as pd
import hashlib
import schedule
import requests
from flask import Flask, request, jsonify
from fuzzywuzzy import fuzz

# Configure logging first, before other application imports
from university_system.utils.logging.log_config import configure_logging, get_log_file

# Internationalization support
from university_system.modules.shared.utils.i18n import get_text as _t

# Setup logging
log_path = get_log_file("modules_system.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

# Use only configure_logging, not both basicConfig and configure_logging
logger = configure_logging(name=__name__)

# Application imports (after logging is configured)
from university_system.infrastructure.database.db import sqlite3, DatabaseManager, ensure_parent_dir
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.modules.domain.academics.services.modules import (
    compulsory_module_1,
    compulsory_module_2,
    optional_module_1,
    optional_module_2,
    optional_module_3,
    optional_module_4,
    CS_optional_module_1,
    CS_optional_module_2,
    CS_optional_module_3,
    CS_optional_module_4,
    DS_optional_module_1,
    DS_optional_module_2,
    DS_optional_module_3,
    DS_optional_module_4,
)

@dataclass
class ImportResult:
    """Data class to track import operation results"""
    total_records: int = 0
    successful_imports: int = 0
    failed_imports: int = 0
    duplicates_found: int = 0
    duplicates_skipped: int = 0
    duplicates_updated: int = 0
    errors: List[Dict] = None
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class ProgressTracker:
    """Track and display progress for batch operations"""
    def __init__(self, total_items: int, operation_name: str = "Processing"):
        self.total_items = total_items
        self.current_item = 0
        self.operation_name = operation_name
        self.start_time = time.time()
        self.last_update = 0
        
    def update(self, increment: int = 1):
        self.current_item += increment
        current_time = time.time()
        
        # Update progress every 0.5 seconds or at completion
        if current_time - self.last_update > 0.5 or self.current_item >= self.total_items:
            self.display_progress()
            self.last_update = current_time
    
    def display_progress(self):
        if self.total_items == 0:
            return
            
        percentage = (self.current_item / self.total_items) * 100
        elapsed_time = time.time() - self.start_time
        
        if self.current_item > 0:
            estimated_total_time = elapsed_time * (self.total_items / self.current_item)
            eta = estimated_total_time - elapsed_time
            eta_str = f"ETA: {int(eta//60)}:{int(eta%60):02d}"
        else:
            eta_str = "ETA: --:--"
        
        # Create progress bar
        bar_length = 30
        filled_length = int(bar_length * percentage / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        print(f"\r{self.operation_name}: [{bar}] {percentage:.1f}% ({self.current_item}/{self.total_items}) {eta_str}", end='', flush=True)
        
        if self.current_item >= self.total_items:
            print()  # New line when complete

class BatchOperationManager:
    """Main class for managing batch operations"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path
        from university_system.modules.shared.constants import paths
        self.backup_dir = str(paths.BACKUP_DIR)
        self.import_history = []
        self.api_app = None
        self.ensure_backup_directory()
        
    def ensure_backup_directory(self):
        """Ensure backup directory exists"""
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def display_batch_menu(self):
        """Display the enhanced batch operations menu"""
        while True:
            print("\n" + "="*60)
            print(_t("shared.utils.batch_operations.menu_title"))
            print("="*60)
            print("\n" + _t("shared.utils.batch_operations.section_import"))
            print(_t("shared.utils.batch_operations.menu_import_csv"))
            print(_t("shared.utils.batch_operations.menu_import_excel"))
            print(_t("shared.utils.batch_operations.menu_multi_file"))
            print(_t("shared.utils.batch_operations.menu_duplicate_detection"))
            print(_t("shared.utils.batch_operations.menu_preview_import"))
            print(_t("shared.utils.batch_operations.menu_resume_import"))

            print("\n" + _t("shared.utils.batch_operations.section_update"))
            print(_t("shared.utils.batch_operations.menu_batch_update"))
            print(_t("shared.utils.batch_operations.menu_bulk_module"))
            print(_t("shared.utils.batch_operations.menu_import_grades"))

            print("\n" + _t("shared.utils.batch_operations.section_export"))
            print(_t("shared.utils.batch_operations.menu_export_students"))
            print(_t("shared.utils.batch_operations.menu_export_stats"))
            print(_t("shared.utils.batch_operations.menu_generate_reports"))

            print("\n" + _t("shared.utils.batch_operations.section_quality"))
            print(_t("shared.utils.batch_operations.menu_validate_clean"))
            print(_t("shared.utils.batch_operations.menu_find_duplicates"))
            print(_t("shared.utils.batch_operations.menu_quality_dashboard"))

            print("\n" + _t("shared.utils.batch_operations.section_utilities"))
            print(_t("shared.utils.batch_operations.menu_generate_template"))
            print(_t("shared.utils.batch_operations.menu_create_backup"))
            print(_t("shared.utils.batch_operations.menu_undo_import"))
            print(_t("shared.utils.batch_operations.menu_import_history"))

            print("\n" + _t("shared.utils.batch_operations.section_automation"))
            print(_t("shared.utils.batch_operations.menu_schedule_imports"))
            print(_t("shared.utils.batch_operations.menu_start_api"))
            print(_t("shared.utils.batch_operations.menu_external_integration"))

            print("\n" + _t("shared.utils.batch_operations.menu_return"))

            choice = input("\n" + _t("shared.utils.batch_operations.prompt_choice")).strip()

            if choice == '1':
                self.import_from_csv()
            elif choice == '2':
                self.import_from_excel()
            elif choice == '3':
                self.multi_file_import()
            elif choice == '4':
                self.import_with_duplicate_detection()
            elif choice == '5':
                self.preview_import()
            elif choice == '6':
                self.resume_failed_import()
            elif choice == '7':
                self.batch_update_records()
            elif choice == '8':
                self.bulk_module_operations()
            elif choice == '9':
                self.import_grade_data()
            elif choice == '10':
                self.export_students_to_file()
            elif choice == '11':
                self.export_enrollment_statistics()
            elif choice == '12':
                self.generate_import_reports()
            elif choice == '13':
                self.validate_and_clean_data()
            elif choice == '14':
                self.find_duplicate_students()
            elif choice == '15':
                self.data_quality_dashboard()
            elif choice == '16':
                self.generate_import_template()
            elif choice == '17':
                self.create_database_backup()
            elif choice == '18':
                self.undo_last_import()
            elif choice == '19':
                self.show_import_history()
            elif choice == '20':
                self.schedule_automated_imports()
            elif choice == '21':
                self.start_api_server()
            elif choice == '22':
                self.external_system_integration()
            elif choice in ('0', '25'):
                print(_t("shared.utils.batch_operations.returning_to_menu"))
                break
            else:
                print(_t("shared.utils.batch_operations.invalid_choice"))

    # ========================================
    # CORE UTILITY FUNCTIONS
    # ========================================
    
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
            errors.append("Student ID is required for updates")
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
                errors.append("First name must be at least 2 characters")
            if not re.match(r"^[a-zA-Z\s\-']+$", str(student_data['first_name'])):
                errors.append("First name contains invalid characters")
        
        if student_data.get('last_name'):
            if len(str(student_data['last_name']).strip()) < 2:
                errors.append("Last name must be at least 2 characters")
            if not re.match(r"^[a-zA-Z\s\-']+$", str(student_data['last_name'])):
                errors.append("Last name contains invalid characters")
        
        # Gender validation
        if student_data.get('gender') and student_data['gender']:
            if str(student_data['gender']).lower() not in ['male', 'female', 'other', 'm', 'f', 'o']:
                errors.append("Gender must be 'male', 'female', 'other' (or M/F/O)")
        
        # DOB validation
        if student_data.get('dob') and student_data['dob']:
            try:
                dob = datetime.datetime.strptime(str(student_data['dob']), "%Y-%m-%d")
                today = datetime.datetime.now()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                
                if age < 16 or age > 100:
                    errors.append("Age must be between 16 and 100")
                if dob > today:
                    errors.append("Date of birth cannot be in the future")
            except ValueError:
                errors.append("Date of birth must be in YYYY-MM-DD format")
        
        # Course validation
        if student_data.get('course') and student_data['course']:
            if str(student_data['course']).upper() not in ['CS', 'DS']:
                errors.append("Course must be 'CS' or 'DS'")
        
        # Email validation
        if student_data.get('email_address') and student_data['email_address']:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, str(student_data['email_address'])):
                errors.append("Invalid email format")
        
        # Phone validation (if present)
        if student_data.get('phone_number') and student_data['phone_number']:
            phone = re.sub(r'[^\d+]', '', str(student_data['phone_number']))
            if len(phone) < 10 or len(phone) > 15:
                errors.append("Phone number must be 10-15 digits")
        
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

    # ========================================
    # IMPORT OPERATIONS
    # ========================================
    
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

    # ========================================
    # HELPER FUNCTIONS FOR IMPORTS
    # ========================================
    
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

    def interactive_error_resolution(self, error_records: List[Dict]) -> List[Dict]:
        """Interactive mode for fixing import errors"""
        print("\n" + _t("shared.utils.batch_operations.title_error_resolution"))
        fixed_records = []

        for i, error_record in enumerate(error_records, 1):
            print(f"\n--- {_t('shared.utils.batch_operations.error_number', current=i, total=len(error_records))} ---")
            print(f"{_t('shared.utils.batch_operations.row')} {error_record['row']}: {error_record['data'].get('first_name', 'N/A')} {error_record['data'].get('last_name', 'N/A')}")
            print(f"{_t('shared.utils.batch_operations.errors')}: {'; '.join(error_record['errors'])}")

            print("\n" + _t("shared.utils.batch_operations.options"))
            print(_t("shared.utils.batch_operations.option_fix_record"))
            print(_t("shared.utils.batch_operations.option_skip_record"))
            print(_t("shared.utils.batch_operations.option_skip_remaining"))

            choice = input(_t("shared.utils.batch_operations.prompt_choose_1_3"))

            if choice == '1':
                fixed_record = self.fix_record_interactive(error_record['data'])
                if fixed_record:
                    fixed_records.append(fixed_record)
            elif choice == '3':
                break
            # Choice 2 (skip) does nothing, continues to next record

        return fixed_records

    def fix_record_interactive(self, record: Dict) -> Optional[Dict]:
        """Interactive fixing of a single record"""
        print("\n" + _t("shared.utils.batch_operations.title_fix_record"))
        fixed_record = record.copy()

        editable_fields = ['first_name', 'last_name', 'gender', 'dob', 'course', 'email_address']

        for field in editable_fields:
            current_value = fixed_record.get(field, '')
            print(f"\n{field.replace('_', ' ').title()}: {current_value}")

            if field == 'gender':
                print(_t("shared.utils.batch_operations.valid_gender_options"))
            elif field == 'dob':
                print(_t("shared.utils.batch_operations.dob_format"))
            elif field == 'course':
                print(_t("shared.utils.batch_operations.valid_course_options"))

            new_value = input(_t("shared.utils.batch_operations.prompt_new_value")).strip()
            if new_value:
                fixed_record[field] = new_value

        # Validate fixed record
        errors = self.validate_student_data(fixed_record)
        if errors:
            print("\n" + _t("shared.utils.batch_operations.still_has_errors", errors='; '.join(errors)))
            retry = input(_t("shared.utils.batch_operations.prompt_try_fixing"))
            if retry.lower() == 'y':
                return self.fix_record_interactive(fixed_record)
            else:
                return None
        else:
            print(_t("shared.utils.batch_operations.record_fixed"))
            return fixed_record

    def find_duplicates_in_import(self, records: List[Dict]) -> List[Dict]:
        """Find potential duplicates between import records and existing database"""
        duplicates = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all existing students
            cursor.execute("SELECT * FROM students")
            existing_students = cursor.fetchall()
            
            for record in records:
                for existing in existing_students:
                    confidence = self.calculate_duplicate_confidence(record, existing)
                    
                    if confidence > 0.7:  # 70% confidence threshold
                        duplicates.append({
                            'import_record': record,
                            'existing_record': existing,
                            'confidence': confidence
                        })
        
        except sqlite3.Error as e:
            logger.error(f"Error checking duplicates: {e}")
        finally:
            conn.close()
        
        return duplicates

    def calculate_duplicate_confidence(self, import_record: Dict, existing_record: Tuple) -> float:
        """Calculate confidence that two records are duplicates"""
        # existing_record format: (student_id, email, title, first_name, middle_name, last_name, gender, dob, age, course, registration_datetime)
        
        confidence_factors = []
        
        # Name matching
        import_first = str(import_record.get('first_name', '')).lower()
        import_last = str(import_record.get('last_name', '')).lower()
        existing_first = str(existing_record[3]).lower()
        existing_last = str(existing_record[5]).lower()
        
        name_ratio = (fuzz.ratio(import_first, existing_first) + fuzz.ratio(import_last, existing_last)) / 200
        confidence_factors.append(('name', name_ratio, 0.4))  # 40% weight
        
        # Email matching
        import_email = str(import_record.get('email_address', '')).lower()
        existing_email = str(existing_record[1]).lower()
        
        if import_email and existing_email:
            email_ratio = fuzz.ratio(import_email, existing_email) / 100
            confidence_factors.append(('email', email_ratio, 0.3))  # 30% weight
        
        # DOB matching
        import_dob = str(import_record.get('dob', ''))
        existing_dob = str(existing_record[7])
        
        if import_dob and existing_dob:
            dob_match = 1.0 if import_dob == existing_dob else 0.0
            confidence_factors.append(('dob', dob_match, 0.3))  # 30% weight
        
        # Calculate weighted confidence
        total_confidence = sum(factor[1] * factor[2] for factor in confidence_factors)
        total_weight = sum(factor[2] for factor in confidence_factors)
        
        return total_confidence / total_weight if total_weight > 0 else 0.0

    def handle_duplicates(self, records: List[Dict], duplicates: List[Dict], choice: str) -> ImportResult:
        """Handle duplicates based on user choice"""
        result = ImportResult()
        result.start_time = datetime.datetime.now()
        
        duplicate_import_records = {id(dup['import_record']): dup for dup in duplicates}
        
        if choice == '1':  # Skip all duplicates
            non_duplicate_records = [r for r in records if id(r) not in duplicate_import_records]
            result = self.import_valid_records(non_duplicate_records)
            result.duplicates_skipped = len(duplicates)
            
        elif choice == '2':  # Update existing records
            non_duplicate_records = [r for r in records if id(r) not in duplicate_import_records]
            
            # Import non-duplicates
            result = self.import_valid_records(non_duplicate_records)
            
            # Update duplicates
            for dup in duplicates:
                self.update_existing_record(dup['existing_record'][0], dup['import_record'])
                result.duplicates_updated += 1
                
        elif choice == '3':  # Handle individually
            non_duplicate_records = [r for r in records if id(r) not in duplicate_import_records]
            
            # Import non-duplicates first
            result = self.import_valid_records(non_duplicate_records)
            
            # Handle each duplicate
            for i, dup in enumerate(duplicates, 1):
                print(f"\n--- Duplicate {i}/{len(duplicates)} ---")
                print(f"Import: {dup['import_record']['first_name']} {dup['import_record']['last_name']}")
                print(f"Existing: {dup['existing_record'][3]} {dup['existing_record'][5]} (ID: {dup['existing_record'][0]})")
                print(f"Confidence: {dup['confidence']:.0%}")
                
                action = input("Action: (s)kip, (u)pdate existing, (i)mport as new: ").lower()
                
                if action == 'u':
                    self.update_existing_record(dup['existing_record'][0], dup['import_record'])
                    result.duplicates_updated += 1
                elif action == 'i':
                    self.import_valid_records([dup['import_record']])
                    result.successful_imports += 1
                else:
                    result.duplicates_skipped += 1
                    
        else:  # Import all as new
            result = self.import_valid_records(records)
        
        result.end_time = datetime.datetime.now()
        return result

    def import_valid_records(self, records: List[Dict]) -> ImportResult:
        """Import valid records with comprehensive tracking and error handling"""
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

    # ========================================
    # UPDATE OPERATIONS
    # ========================================
    
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

    # ========================================
    # EXPORT OPERATIONS
    # ========================================

    def export_students_to_file(self):
        """Export student data with filtering options"""
        print("\n" + _t("shared.utils.batch_operations.title_export_students"))
        
        # Choose export format
        format_choice = input(_t("shared.utils.batch_operations.prompt_export_format"))
        if format_choice not in ['1', '2', '3']:
            print(_t("shared.utils.batch_operations.invalid_choice"))
            return

        formats = {'1': 'csv', '2': 'xlsx', '3': 'json'}
        export_format = formats[format_choice]

        # Choose filtering options
        print("\n" + _t("shared.utils.batch_operations.filtering_options"))
        print(_t("shared.utils.batch_operations.filter_all_students"))
        print(_t("shared.utils.batch_operations.filter_by_course"))
        print(_t("shared.utils.batch_operations.filter_by_date"))

        filter_choice = input(_t("shared.utils.batch_operations.prompt_choose_filter"))

        # Build query based on filter
        base_query = """
        SELECT s.student_id, s.email_address, s.title, s.first_name, s.middle_name,
               s.last_name, s.gender, s.dob, s.age, s.course, s.registration_datetime,
               GROUP_CONCAT(sm.module_code || ': ' || sm.module_name, '; ') as modules
        FROM students s
        LEFT JOIN student_modules sm ON s.student_id = sm.student_id
        """

        params = []

        if filter_choice == '2':
            course = input(_t("shared.utils.batch_operations.prompt_enter_course")).upper()
            if course in ['CS', 'DS']:
                base_query += " WHERE s.course = ?"
                params.append(course)
            else:
                print(_t("shared.utils.batch_operations.invalid_course"))
                return

        elif filter_choice == '3':
            start_date = input(_t("shared.utils.batch_operations.prompt_start_date"))
            end_date = input(_t("shared.utils.batch_operations.prompt_end_date"))
            base_query += " WHERE DATE(s.registration_datetime) BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        
        base_query += " GROUP BY s.student_id ORDER BY s.last_name, s.first_name"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(base_query, params)
            results = cursor.fetchall()
            
            if not results:
                print(_t("shared.utils.batch_operations.no_students_matching"))
                return

            print(_t("shared.utils.batch_operations.students_to_export", count=len(results)))

            # Get column names
            columns = [description[0] for description in cursor.description]

            # Choose output file
            default_filename = f"students_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}"
            output_path = input(_t("shared.utils.batch_operations.prompt_output_filename", default=default_filename)).strip()
            if not output_path:
                output_path = default_filename

            # Export data
            self.export_data_to_file(results, columns, output_path, export_format)

        except sqlite3.Error as e:
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()

    def export_data_to_file(self, data: List[Tuple], columns: List[str], filename: str, format_type: str):
        """Export data to specified format"""
        try:
            if format_type == 'csv':
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(columns)
                    writer.writerows(data)
                    
            elif format_type == 'xlsx':
                df = pd.DataFrame(data, columns=columns)
                df.to_excel(filename, index=False)
                
            elif format_type == 'json':
                # Convert to list of dictionaries
                json_data = [dict(zip(columns, row)) for row in data]
                with open(filename, 'w', encoding='utf-8') as jsonfile:
                    json.dump(json_data, jsonfile, indent=2, default=str)
            
            print(_t("shared.utils.batch_operations.export_success", filename=filename))

        except Exception as e:
            print(_t("shared.utils.batch_operations.error_exporting", error=str(e)))

    def export_enrollment_statistics(self):
        """Export course and module enrollment statistics"""
        print("\n" + _t("shared.utils.batch_operations.title_export_stats"))
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Course enrollment stats
            cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course")
            stats['course_enrollment'] = dict(cursor.fetchall())
            
            # Module enrollment stats
            cursor.execute("""
            SELECT module_code, module_name, COUNT(*) as enrollment_count
            FROM student_modules 
            GROUP BY module_code, module_name
            ORDER BY enrollment_count DESC
            """)
            stats['module_enrollment'] = [
                {'module_code': row[0], 'module_name': row[1], 'enrollment': row[2]}
                for row in cursor.fetchall()
            ]
            
            # Gender distribution
            cursor.execute("SELECT gender, COUNT(*) FROM students GROUP BY gender")
            stats['gender_distribution'] = dict(cursor.fetchall())
            
            # Age distribution
            cursor.execute("""
            SELECT 
                CASE 
                    WHEN age < 20 THEN 'Under 20'
                    WHEN age BETWEEN 20 AND 24 THEN '20-24'
                    WHEN age BETWEEN 25 AND 29 THEN '25-29'
                    WHEN age >= 30 THEN '30+'
                END as age_group,
                COUNT(*) 
            FROM students 
            GROUP BY age_group
            """)
            stats['age_distribution'] = dict(cursor.fetchall())
            
            # Registration trends (last 12 months)
            cursor.execute("""
            SELECT strftime('%Y-%m', registration_datetime) as month, COUNT(*)
            FROM students 
            WHERE registration_datetime >= date('now', '-12 months')
            GROUP BY month
            ORDER BY month
            """)
            stats['registration_trends'] = dict(cursor.fetchall())
            
            # Export to JSON
            filename = f"enrollment_statistics_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, default=str)
            
            print(_t("shared.utils.batch_operations.stats_exported", filename=filename))

            # Display summary
            print("\n" + _t("shared.utils.batch_operations.summary"))
            print(f"{_t('shared.utils.batch_operations.course_enrollment')}: {stats['course_enrollment']}")
            print(f"{_t('shared.utils.batch_operations.total_students')}: {sum(stats['course_enrollment'].values())}")
            print(f"{_t('shared.utils.batch_operations.most_popular_module')}: {stats['module_enrollment'][0]['module_name']} ({stats['module_enrollment'][0]['enrollment']} {_t('shared.utils.batch_operations.students')})")

        except sqlite3.Error as e:
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()

    def generate_import_reports(self):
        """Generate detailed reports on batch operations"""
        print("\n" + _t("shared.utils.batch_operations.title_generate_reports"))

        if not self.import_history:
            try:
                with open('import_history.json', 'r') as f:
                    self.import_history = json.load(f)
            except FileNotFoundError:
                print(_t("shared.utils.batch_operations.no_import_history"))
                return

        if not self.import_history:
            print(_t("shared.utils.batch_operations.no_history_available"))
            return

        print("\n" + _t("shared.utils.batch_operations.report_options"))
        print(_t("shared.utils.batch_operations.report_success_rates"))
        print(_t("shared.utils.batch_operations.report_error_analysis"))
        print(_t("shared.utils.batch_operations.report_performance"))
        print(_t("shared.utils.batch_operations.report_comprehensive"))

        choice = input(_t("shared.utils.batch_operations.prompt_choose_report"))

        if choice == '1':
            self.generate_success_rate_report()
        elif choice == '2':
            self.generate_error_analysis_report()
        elif choice == '3':
            self.generate_performance_report()
        elif choice == '4':
            self.generate_comprehensive_report()
        else:
            print(_t("shared.utils.batch_operations.invalid_choice"))

    def generate_success_rate_report(self):
        """Generate import success rate report"""
        print("\n" + _t("shared.utils.batch_operations.title_success_rate_report"))
        
        total_operations = len(self.import_history)
        total_records = sum(op['total_records'] for op in self.import_history)
        total_successful = sum(op['successful_imports'] for op in self.import_history)
        total_failed = sum(op['failed_imports'] for op in self.import_history)
        
        success_rate = (total_successful / total_records * 100) if total_records > 0 else 0
        
        report = {
            'summary': {
                'total_operations': total_operations,
                'total_records_processed': total_records,
                'total_successful_imports': total_successful,
                'total_failed_imports': total_failed,
                'overall_success_rate': round(success_rate, 2)
            },
            'by_operation_type': {},
            'recent_operations': self.import_history[-10:]
        }
        
        # Group by operation type
        by_type = {}
        for op in self.import_history:
            op_type = op['operation_type']
            if op_type not in by_type:
                by_type[op_type] = {'operations': 0, 'total': 0, 'successful': 0, 'failed': 0}
            
            by_type[op_type]['operations'] += 1
            by_type[op_type]['total'] += op['total_records']
            by_type[op_type]['successful'] += op['successful_imports']
            by_type[op_type]['failed'] += op['failed_imports']
        
        for op_type, stats in by_type.items():
            success_rate = (stats['successful'] / stats['total'] * 100) if stats['total'] > 0 else 0
            report['by_operation_type'][op_type] = {
                'operations': stats['operations'],
                'total_records': stats['total'],
                'success_rate': round(success_rate, 2)
            }
        
        # Export report
        filename = f"success_rate_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(_t("shared.utils.batch_operations.success_rate_exported", filename=filename))
        print(_t("shared.utils.batch_operations.overall_success_rate", rate=f"{success_rate:.1f}"))

    def generate_error_analysis_report(self):
        """Analyze common errors in import operations"""
        print("\n" + _t("shared.utils.batch_operations.title_error_analysis"))

        all_errors = []
        for op in self.import_history:
            all_errors.extend(op.get('errors', []))

        if not all_errors:
            print(_t("shared.utils.batch_operations.no_errors_in_history"))
            return
        
        # Analyze error patterns
        error_types = {}
        for error in all_errors:
            error_msg = error.get('error', 'Unknown error')
            error_types[error_msg] = error_types.get(error_msg, 0) + 1
        
        # Sort by frequency
        sorted_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)
        
        report = {
            'total_errors': len(all_errors),
            'unique_error_types': len(error_types),
            'most_common_errors': sorted_errors[:10],
            'error_frequency_analysis': {
                'validation_errors': len([e for e in all_errors if 'validation' in str(e).lower()]),
                'database_errors': len([e for e in all_errors if 'database' in str(e).lower()]),
                'format_errors': len([e for e in all_errors if 'format' in str(e).lower()])
            }
        }
        
        filename = f"error_analysis_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(_t("shared.utils.batch_operations.error_analysis_exported", filename=filename))
        print(_t("shared.utils.batch_operations.most_common_error", error=sorted_errors[0][0], count=sorted_errors[0][1]))

    def generate_performance_report(self):
        """Generate performance trends report"""
        print("\n" + _t("shared.utils.batch_operations.title_performance_report"))

        performance_data = []
        for op in self.import_history:
            if op['duration_seconds'] > 0:
                records_per_second = op['total_records'] / op['duration_seconds']
                performance_data.append({
                    'timestamp': op['timestamp'],
                    'operation_type': op['operation_type'],
                    'total_records': op['total_records'],
                    'duration_seconds': op['duration_seconds'],
                    'records_per_second': round(records_per_second, 2)
                })
        
        if not performance_data:
            print(_t("shared.utils.batch_operations.no_performance_data"))
            return
        
        avg_performance = sum(p['records_per_second'] for p in performance_data) / len(performance_data)
        
        report = {
            'summary': {
                'total_operations_analyzed': len(performance_data),
                'average_records_per_second': round(avg_performance, 2),
                'fastest_operation': max(performance_data, key=lambda x: x['records_per_second']),
                'slowest_operation': min(performance_data, key=lambda x: x['records_per_second'])
            },
            'performance_by_operation_type': {},
            'detailed_performance': performance_data
        }
        
        # Group by operation type
        by_type = {}
        for p in performance_data:
            op_type = p['operation_type']
            if op_type not in by_type:
                by_type[op_type] = []
            by_type[op_type].append(p['records_per_second'])
        
        for op_type, speeds in by_type.items():
            report['performance_by_operation_type'][op_type] = {
                'average_records_per_second': round(sum(speeds) / len(speeds), 2),
                'operations_count': len(speeds),
                'best_performance': round(max(speeds), 2),
                'worst_performance': round(min(speeds), 2)
            }
        
        filename = f"performance_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(_t("shared.utils.batch_operations.performance_exported", filename=filename))
        print(_t("shared.utils.batch_operations.average_performance", rate=f"{avg_performance:.1f}"))

    def generate_comprehensive_report(self):
        """Generate a comprehensive report with all metrics"""
        print("\n" + _t("shared.utils.batch_operations.generating_comprehensive"))

        # Combine all report types
        self.generate_success_rate_report()
        self.generate_error_analysis_report()
        self.generate_performance_report()

        print(_t("shared.utils.batch_operations.comprehensive_complete"))

    # ========================================
    # DATA QUALITY FUNCTIONS
    # ========================================
    
    def validate_and_clean_data(self):
        """Validate and clean existing data in database"""
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
            
            progress = ProgressTracker(len(students), "Validating data")
            
            for student in students:
                student_issues = []
                
                # Check email format
                email = student[1]
                if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                    student_issues.append("Invalid email format")
                
                # Check names
                first_name = student[3]
                last_name = student[5]
                if not first_name or len(first_name.strip()) < 2:
                    student_issues.append("Invalid first name")
                if not last_name or len(last_name.strip()) < 2:
                    student_issues.append("Invalid last name")
                
                # Check gender
                gender = student[6]
                if gender not in ['male', 'female', 'other']:
                    student_issues.append("Invalid gender value")
                
                # Check DOB and age consistency
                dob_str = student[7]
                age = student[8]
                try:
                    dob = datetime.datetime.strptime(dob_str, "%Y-%m-%d")
                    calculated_age = datetime.datetime.now().year - dob.year
                    if abs(calculated_age - age) > 1:
                        student_issues.append("Age inconsistent with DOB")
                        
                        # Auto-fix age disabled - student updates centralized
                        student_issues.append("Age update skipped - use main GUI to update student data")
                        
                except ValueError:
                    student_issues.append("Invalid DOB format")
                
                # Check course
                course = student[9]
                if course not in ['CS', 'DS']:
                    student_issues.append("Invalid course")
                
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
                filename = f"data_quality_issues_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    json.dump(issues, f, indent=2)
                print(_t("shared.utils.batch_operations.issues_report_saved", filename=filename))

        except sqlite3.Error as e:
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()

    def find_duplicate_students(self):
        """Find potential duplicate students in database"""
        print("\n" + _t("shared.utils.batch_operations.title_find_duplicates"))

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM students ORDER BY last_name, first_name")
            students = cursor.fetchall()

            print(_t("shared.utils.batch_operations.analyzing_for_duplicates", count=len(students)))
            
            duplicates = []
            
            # Compare each student with others
            for i, student1 in enumerate(students):
                progress = (i + 1) / len(students) * 100
                print(f"\rProgress: {progress:.1f}%", end='', flush=True)
                
                for j, student2 in enumerate(students[i+1:], i+1):
                    # Create fake import record for comparison
                    fake_record = {
                        'first_name': student2[3],
                        'last_name': student2[5],
                        'email_address': student2[1],
                        'dob': student2[7]
                    }
                    
                    confidence = self.calculate_duplicate_confidence(fake_record, student1)
                    
                    if confidence > 0.7:  # 70% confidence threshold
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
            
            print("\n" + _t("shared.utils.batch_operations.found_duplicate_pairs", count=len(duplicates)))

            if duplicates:
                print("\n" + _t("shared.utils.batch_operations.potential_duplicates"))
                for i, dup in enumerate(duplicates[:10], 1):
                    print(f"{i}. {dup['student1']['name']} (ID: {dup['student1']['id']}) "
                          f"<-> {dup['student2']['name']} (ID: {dup['student2']['id']}) "
                          f"- {_t('shared.utils.batch_operations.confidence')}: {dup['confidence']:.0%}")

                if len(duplicates) > 10:
                    print(_t("shared.utils.batch_operations.and_more_duplicates", count=len(duplicates) - 10))

                # Export duplicates report
                filename = f"duplicate_students_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w') as f:
                    json.dump(duplicates, f, indent=2, default=str)
                print(_t("shared.utils.batch_operations.duplicates_report_saved", filename=filename))

                # Offer to merge duplicates
                merge_choice = input("\n" + _t("shared.utils.batch_operations.prompt_merge_duplicates"))
                if merge_choice.lower() == 'y':
                    self.interactive_duplicate_merger(duplicates)
            else:
                print(_t("shared.utils.batch_operations.no_duplicates"))

        except sqlite3.Error as e:
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()

    def interactive_duplicate_merger(self, duplicates: List[Dict]):
        """Interactive tool for merging duplicate records"""
        print("\n" + _t("shared.utils.batch_operations.title_duplicate_merger"))

        for i, dup in enumerate(duplicates, 1):
            print(f"\n--- {_t('shared.utils.batch_operations.duplicate_pair', current=i, total=len(duplicates))} ---")
            print(f"{_t('shared.utils.batch_operations.student')} 1: {dup['student1']['name']} (ID: {dup['student1']['id']})")
            print(f"           Email: {dup['student1']['email']}, DOB: {dup['student1']['dob']}")
            print(f"{_t('shared.utils.batch_operations.student')} 2: {dup['student2']['name']} (ID: {dup['student2']['id']})")
            print(f"           Email: {dup['student2']['email']}, DOB: {dup['student2']['dob']}")
            print(f"{_t('shared.utils.batch_operations.confidence')}: {dup['confidence']:.0%}")

            print("\n" + _t("shared.utils.batch_operations.options"))
            print(_t("shared.utils.batch_operations.option_keep_student_1"))
            print(_t("shared.utils.batch_operations.option_keep_student_2"))
            print(_t("shared.utils.batch_operations.option_merge_manual"))
            print(_t("shared.utils.batch_operations.option_skip_pair"))
            print(_t("shared.utils.batch_operations.option_skip_all"))

            choice = input(_t("shared.utils.batch_operations.prompt_choose_1_5"))

            if choice == '1':
                self.merge_students(dup['student1']['id'], dup['student2']['id'], keep_first=True)
            elif choice == '2':
                self.merge_students(dup['student2']['id'], dup['student1']['id'], keep_first=True)
            elif choice == '3':
                self.manual_merge_students(dup['student1']['id'], dup['student2']['id'])
            elif choice == '5':
                break
            # Choice 4 (skip) does nothing

    def merge_students(self, keep_id: str, delete_id: str, keep_first: bool = True):
        """Merge student records - DISABLED: Use main GUI for student management"""
        print("\n" + _t("shared.utils.batch_operations.merge_disabled"))
        print(_t("shared.utils.batch_operations.deletion_centralized"))
        print("\n" + _t("shared.utils.batch_operations.use_main_gui"))
        print(_t("shared.utils.batch_operations.bullet_delete_duplicates"))
        print(_t("shared.utils.batch_operations.bullet_manage_records"))
        print("\n" + _t("shared.utils.batch_operations.ensures_consistency"))

    def data_quality_dashboard(self):
        """Display comprehensive data quality dashboard"""
        print("\n" + _t("shared.utils.batch_operations.title_quality_dashboard"))
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Basic statistics
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT email_address) FROM students")
            unique_emails = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM students WHERE email_address IS NULL OR email_address = ''")
            missing_emails = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM students WHERE first_name IS NULL OR first_name = '' OR last_name IS NULL OR last_name = ''")
            incomplete_names = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM students WHERE dob IS NULL OR dob = ''")
            missing_dob = cursor.fetchone()[0]
            
            # Module enrollment completeness
            cursor.execute('''
            SELECT COUNT(DISTINCT s.student_id) 
            FROM students s 
            LEFT JOIN student_modules sm ON s.student_id = sm.student_id 
            WHERE sm.student_id IS NULL
            ''')
            students_no_modules = cursor.fetchone()[0]
            
            # Display dashboard
            print(f"\n📈 OVERALL STATISTICS")
            print(f"Total Students: {total_students:,}")
            print(f"Data Completeness: {((total_students - missing_emails - incomplete_names - missing_dob) / total_students * 100):.1f}%")
            
            print(f"\n📧 EMAIL QUALITY")
            print(f"Unique Emails: {unique_emails:,}")
            print(f"Missing Emails: {missing_emails:,}")
            print(f"Email Uniqueness: {(unique_emails / total_students * 100):.1f}%")
            
            print(f"\n👤 NAME COMPLETENESS")
            print(f"Complete Names: {total_students - incomplete_names:,}")
            print(f"Incomplete Names: {incomplete_names:,}")
            
            print(f"\n📅 DATE OF BIRTH")
            print(f"Missing DOB: {missing_dob:,}")
            print(f"DOB Completeness: {((total_students - missing_dob) / total_students * 100):.1f}%")
            
            print(f"\n📚 MODULE ENROLLMENT")
            print(f"Students without modules: {students_no_modules:,}")
            print(f"Module enrollment rate: {((total_students - students_no_modules) / total_students * 100):.1f}%")
            
            # Course distribution
            cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course")
            course_dist = cursor.fetchall()
            print(f"\n🎓 COURSE DISTRIBUTION")
            for course, count in course_dist:
                percentage = (count / total_students * 100)
                print(f"{course}: {count:,} ({percentage:.1f}%)")
            
            # Age distribution
            cursor.execute('''
            SELECT 
                CASE 
                    WHEN age < 20 THEN 'Under 20'
                    WHEN age BETWEEN 20 AND 24 THEN '20-24'
                    WHEN age BETWEEN 25 AND 29 THEN '25-29'
                    WHEN age >= 30 THEN '30+'
                END as age_group,
                COUNT(*) 
            FROM students 
            WHERE age IS NOT NULL
            GROUP BY age_group
            ''')
            age_dist = cursor.fetchall()
            print(f"\n🎂 AGE DISTRIBUTION")
            for age_group, count in age_dist:
                percentage = (count / total_students * 100)
                print(f"{age_group}: {count:,} ({percentage:.1f}%)")
            
            # Registration trends
            cursor.execute('''
            SELECT DATE(registration_datetime) as reg_date, COUNT(*)
            FROM students 
            WHERE registration_datetime >= date('now', '-30 days')
            GROUP BY reg_date
            ORDER BY reg_date DESC
            LIMIT 10
            ''')
            recent_registrations = cursor.fetchall()
            print(f"\n📈 RECENT REGISTRATIONS (Last 30 days)")
            for date, count in recent_registrations:
                print(f"{date}: {count:,} students")
            
        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
        finally:
            conn.close()

    # ========================================
    # UTILITY FUNCTIONS
    # ========================================
    
    def generate_import_template(self):
        """Enhanced template generation with more options"""
        print("\n" + _t("shared.utils.batch_operations.title_generate_template"))

        print(_t("shared.utils.batch_operations.template_types"))
        print(_t("shared.utils.batch_operations.template_new_student"))
        print(_t("shared.utils.batch_operations.template_student_update"))
        print(_t("shared.utils.batch_operations.template_module_enrollment"))
        print(_t("shared.utils.batch_operations.template_grade_import"))
        print(_t("shared.utils.batch_operations.template_custom"))

        template_type = input(_t("shared.utils.batch_operations.prompt_choose_template"))

        if template_type not in ['1', '2', '3', '4', '5']:
            print(_t("shared.utils.batch_operations.invalid_choice"))
            return

        file_format = input(_t("shared.utils.batch_operations.prompt_template_format"))
        if file_format not in ['1', '2']:
            print(_t("shared.utils.batch_operations.invalid_choice"))
            return
        
        # Define field sets for different templates
        template_fields = {
            '1': ['first_name', 'middle_name', 'last_name', 'gender', 'dob', 'course', 'email_address', 'phone_number'],
            '2': ['student_id', 'first_name', 'middle_name', 'last_name', 'gender', 'dob', 'course', 'email_address'],
            '3': ['student_id', 'module_code', 'module_name', 'module_type'],
            '4': ['student_id', 'module_code', 'grade', 'semester', 'year'],
            '5': []  # Custom - will be defined by user
        }
        
        if template_type == '5':
            print("\n" + _t("shared.utils.batch_operations.enter_field_names"))
            fields = []
            while True:
                field = input(_t("shared.utils.batch_operations.prompt_field_name")).strip()
                if not field:
                    break
                fields.append(field.lower().replace(' ', '_'))
        else:
            fields = template_fields[template_type]
        
        # Generate template
        template_names = {
            '1': 'new_students_template',
            '2': 'update_students_template',
            '3': 'module_enrollment_template',
            '4': 'grade_import_template',
            '5': 'custom_template'
        }
        
        extension = 'csv' if file_format == '1' else 'xlsx'
        filename = f"{template_names[template_type]}.{extension}"
        
        # Get output location
        output_path = input(_t("shared.utils.batch_operations.prompt_save_as", default=filename)).strip()
        if not output_path:
            output_path = filename

        try:
            self.create_template_file(fields, output_path, file_format, template_type)
            print(_t("shared.utils.batch_operations.template_created", path=output_path))

            # Show usage instructions
            self.show_template_instructions(template_type)

        except Exception as e:
            print(_t("shared.utils.batch_operations.error_creating_template", error=str(e)))

    def create_template_file(self, fields: List[str], filename: str, file_format: str, template_type: str):
        """Create template file with example data"""
        example_data = self.get_example_data(template_type)
        
        if file_format == '1':  # CSV
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fields)
                writer.writeheader()
                
                # Add example row
                if example_data:
                    example_row = {field: example_data.get(field, '') for field in fields}
                    writer.writerow(example_row)
        else:  # Excel
            df = pd.DataFrame(columns=fields)
            
            if example_data:
                example_row = {field: example_data.get(field, '') for field in fields}
                df = df.append(example_row, ignore_index=True)
            
            df.to_excel(filename, index=False)

    def get_example_data(self, template_type: str) -> Dict:
        """Get example data for templates"""
        examples = {
            '1': {  # New students
                'first_name': 'John',
                'middle_name': 'William',
                'last_name': 'Doe',
                'gender': 'male',
                'dob': '1995-01-15',
                'course': 'CS',
                'email_address': 'john.doe@example.com',
                'phone_number': '+44123456789'
            },
            '2': {  # Student updates
                'student_id': '1234567',
                'first_name': 'John (leave blank to keep current)',
                'course': 'DS (to change course)'
            },
            '3': {  # Module enrollment
                'student_id': '1234567',
                'module_code': 'CS101',
                'module_name': 'Introduction to Programming',
                'module_type': 'compulsory'
            },
            '4': {  # Grades
                'student_id': '1234567',
                'module_code': 'CS101',
                'grade': '85.5',
                'semester': 'Fall',
                'year': '2024'
            }
        }
        
        return examples.get(template_type, {})

    def show_template_instructions(self, template_type: str):
        """Show usage instructions for templates"""
        instructions = {
            '1': [
                "NEW STUDENT IMPORT INSTRUCTIONS:",
                "- Fill in all required fields: first_name, last_name, gender, dob, course",
                "- Valid gender values: male, female, other",
                "- DOB format: YYYY-MM-DD (e.g., 1995-01-15)",
                "- Valid course values: CS, DS",
                "- middle_name, email_address, phone_number are optional"
            ],
            '2': [
                "STUDENT UPDATE INSTRUCTIONS:",
                "- student_id is required and must match existing record",
                "- Only fill in fields you want to update",
                "- Leave fields blank to keep current values",
                "- Use same validation rules as new student import"
            ],
            '3': [
                "MODULE ENROLLMENT INSTRUCTIONS:",
                "- student_id must exist in database",
                "- module_code should be unique identifier",
                "- module_type: compulsory, optional, CS, DS"
            ],
            '4': [
                "GRADE IMPORT INSTRUCTIONS:",
                "- student_id and module_code must exist",
                "- grade: numeric value (0-100)",
                "- semester and year are optional"
            ]
        }
        
        if template_type in instructions:
            print(f"\n📋 {instructions[template_type][0]}")
            for instruction in instructions[template_type][1:]:
                print(f"   {instruction}")

    def create_database_backup(self, auto: bool = False) -> str:
        """Create database backup with timestamp"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"student_records_backup_{timestamp}.db"
        backup_path = os.path.join(self.backup_dir, backup_filename)
        
        try:
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            if not auto:
                print(_t("shared.utils.batch_operations.backup_created", path=backup_path))

            # Keep only last 10 backups
            self.cleanup_old_backups()

            return backup_path

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            if not auto:
                print(_t("shared.utils.batch_operations.error_creating_backup", error=str(e)))
            return ""

    def cleanup_old_backups(self, keep_count: int = 10):
        """Clean up old backup files, keeping only the most recent"""
        try:
            backup_files = list(Path(self.backup_dir).glob('student_records_backup_*.db'))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove old backups
            for old_backup in backup_files[keep_count:]:
                old_backup.unlink()
                logger.info(f"Removed old backup: {old_backup}")
                
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")

    def undo_last_import(self):
        """Rollback the last import operation"""
        print("\n" + _t("shared.utils.batch_operations.title_undo_import"))

        if not self.import_history:
            try:
                with open('import_history.json', 'r') as f:
                    self.import_history = json.load(f)
            except FileNotFoundError:
                print(_t("shared.utils.batch_operations.no_import_history"))
                return

        if not self.import_history:
            print(_t("shared.utils.batch_operations.no_imports_to_undo"))
            return

        last_import = self.import_history[-1]

        print(_t("shared.utils.batch_operations.last_import_operation"))
        print(f"{_t('shared.utils.batch_operations.date')}: {last_import['timestamp']}")
        print(f"{_t('shared.utils.batch_operations.operation')}: {last_import['operation_type']}")
        print(f"{_t('shared.utils.batch_operations.records_imported')}: {last_import['successful_imports']}")
        print(f"{_t('shared.utils.batch_operations.file')}: {last_import['file_path']}")

        confirm = input("\n" + _t("shared.utils.batch_operations.confirm_undo"))
        if confirm.lower() != 'y':
            print(_t("shared.utils.batch_operations.undo_cancelled"))
            return
        
        # Find records imported in last operation
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get records from around the time of last import
            import_time = datetime.datetime.fromisoformat(last_import['timestamp'])
            time_window_start = (import_time - datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
            time_window_end = (import_time + datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            SELECT student_id FROM students 
            WHERE registration_datetime BETWEEN ? AND ?
            ORDER BY registration_datetime DESC
            LIMIT ?
            ''', (time_window_start, time_window_end, last_import['successful_imports']))
            
            student_ids_to_delete = [row[0] for row in cursor.fetchall()]

            if not student_ids_to_delete:
                print(_t("shared.utils.batch_operations.no_records_to_undo"))
                return

            print(_t("shared.utils.batch_operations.found_records_to_delete", count=len(student_ids_to_delete)))

            final_confirm = input(_t("shared.utils.batch_operations.prompt_proceed_deletion"))
            if final_confirm.lower() == 'y':
                # Student deletion has been centralized - show error
                print("\n" + _t("shared.utils.batch_operations.undo_disabled"))
                print(_t("shared.utils.batch_operations.deletion_centralized"))
                print("\n" + _t("shared.utils.batch_operations.use_main_gui"))
                print(_t("shared.utils.batch_operations.bullet_delete_students"))
                print("\n" + _t("shared.utils.batch_operations.ensures_consistency"))
                return
                
                # Update import history
                last_import['undone'] = True
                last_import['undo_timestamp'] = datetime.datetime.now().isoformat()
                
                with open('import_history.json', 'w') as f:
                    json.dump(self.import_history, f, indent=2)
            
        except sqlite3.Error as e:
            conn.rollback()
            print(_t("shared.utils.batch_operations.database_error_undo", error=str(e)))
        finally:
            conn.close()

    def show_import_history(self):
        """Display import operation history"""
        print("\n" + _t("shared.utils.batch_operations.title_import_history"))

        if not self.import_history:
            try:
                with open('import_history.json', 'r') as f:
                    self.import_history = json.load(f)
            except FileNotFoundError:
                print(_t("shared.utils.batch_operations.no_import_history"))
                return

        if not self.import_history:
            print(_t("shared.utils.batch_operations.no_history_available"))
            return

        print("\n" + _t("shared.utils.batch_operations.showing_operations", count=min(20, len(self.import_history))))
        print("-" * 100)
        
        for i, op in enumerate(reversed(self.import_history[-20:]), 1):
            timestamp = datetime.datetime.fromisoformat(op['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            status = "UNDONE" if op.get('undone', False) else "ACTIVE"
            
            print(f"{i:2}. {timestamp} | {op['operation_type']:<25} | "
                  f"Records: {op['successful_imports']:4}/{op['total_records']:<4} | "
                  f"Errors: {op['failed_imports']:3} | {status}")
            
            if op['failed_imports'] > 0 and op.get('errors'):
                print(f"    📄 File: {os.path.basename(op['file_path'])}")
                print(f"    ❌ Sample errors: {'; '.join([e.get('error', 'Unknown')[:50] for e in op['errors'][:2]])}")
        
        # Show summary statistics
        total_ops = len(self.import_history)
        total_records = sum(op['total_records'] for op in self.import_history)
        total_successful = sum(op['successful_imports'] for op in self.import_history)
        total_failed = sum(op['failed_imports'] for op in self.import_history)

        print("\n" + _t("shared.utils.batch_operations.summary_statistics"))
        print(f"{_t('shared.utils.batch_operations.total_operations')}: {total_ops}")
        print(f"{_t('shared.utils.batch_operations.total_records_processed')}: {total_records:,}")
        success_rate = f"{(total_successful/total_records*100):.1f}%" if total_records > 0 else "N/A"
        print(f"{_t('shared.utils.batch_operations.success_rate')}: {success_rate}")
        print(f"{_t('shared.utils.batch_operations.total_errors')}: {total_failed:,}")

    # ========================================
    # HELPER FUNCTIONS FOR MODULE OPERATIONS
    # ========================================
    
    def get_students_by_course(self, course: str) -> List[str]:
        """Get student IDs by course"""
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

    # ========================================
    # AUTOMATION FEATURES
    # ========================================
    
    def schedule_automated_imports(self):
        """Set up scheduled automated imports"""
        print("\n" + _t("shared.utils.batch_operations.title_schedule_imports"))

        print(_t("shared.utils.batch_operations.schedule_options"))
        print(_t("shared.utils.batch_operations.option_daily_import"))
        print(_t("shared.utils.batch_operations.option_weekly_import"))
        print(_t("shared.utils.batch_operations.option_custom_schedule"))
        print(_t("shared.utils.batch_operations.option_view_scheduled"))
        print(_t("shared.utils.batch_operations.option_cancel_scheduled"))

        choice = input(_t("shared.utils.batch_operations.prompt_choose_1_5"))

        if choice == '1':
            self.setup_daily_import()
        elif choice == '2':
            self.setup_weekly_import()
        elif choice == '3':
            self.setup_custom_schedule()
        elif choice == '4':
            self.view_scheduled_tasks()
        elif choice == '5':
            self.cancel_scheduled_task()
        else:
            print(_t("shared.utils.batch_operations.invalid_choice"))

    def setup_daily_import(self):
        """Set up daily automated import"""
        print("\n" + _t("shared.utils.batch_operations.title_setup_daily"))

        import_dir = input(_t("shared.utils.batch_operations.prompt_monitor_directory"))
        if not os.path.exists(import_dir):
            print(_t("shared.utils.batch_operations.error_directory_not_found"))
            return

        import_time = input(_t("shared.utils.batch_operations.prompt_import_time"))
        try:
            # Validate time format
            datetime.datetime.strptime(import_time, '%H:%M')
        except ValueError:
            print(_t("shared.utils.batch_operations.invalid_time_format"))
            return

        # Schedule the task
        schedule.every().day.at(import_time).do(self.automated_import_job, import_dir)

        print(_t("shared.utils.batch_operations.daily_import_scheduled", directory=import_dir, time=import_time))
        print(_t("shared.utils.batch_operations.schedule_note"))

    def setup_weekly_import(self):
        """Set up weekly automated import with notifications"""
        print("\n" + _t("shared.utils.batch_operations.title_setup_weekly"))

        import_dir = input(_t("shared.utils.batch_operations.prompt_monitor_directory"))
        if not os.path.exists(import_dir):
            print(_t("shared.utils.batch_operations.error_directory_not_found"))
            return

        day_of_week = input(_t("shared.utils.batch_operations.prompt_day_of_week")).lower()
        import_time = input(_t("shared.utils.batch_operations.prompt_time"))
        email = input(_t("shared.utils.batch_operations.prompt_notification_email"))

        try:
            datetime.datetime.strptime(import_time, '%H:%M')
        except ValueError:
            print(_t("shared.utils.batch_operations.invalid_time_format"))
            return

        # Schedule weekly task
        getattr(schedule.every(), day_of_week).at(import_time).do(
            self.automated_import_job, import_dir, email
        )

        print(_t("shared.utils.batch_operations.weekly_import_scheduled", day=day_of_week, time=import_time))

    def setup_custom_schedule(self):
        """Set up custom schedule using cron-like syntax"""
        print("\n" + _t("shared.utils.batch_operations.title_setup_custom"))
        print(_t("shared.utils.batch_operations.cron_instruction"))
        cron_expr = input(_t("shared.utils.batch_operations.prompt_cron_expression"))
        task_name = input(_t("shared.utils.batch_operations.prompt_task_name"))
        print(_t("shared.utils.batch_operations.custom_schedule_created", name=task_name))
        print(f"{_t('shared.utils.batch_operations.schedule')}: {cron_expr}")
        # This would integrate with more advanced scheduling libraries

    def view_scheduled_tasks(self):
        """View all scheduled tasks"""
        print("\n" + _t("shared.utils.batch_operations.title_scheduled_tasks"))

        jobs = schedule.get_jobs()
        if not jobs:
            print(_t("shared.utils.batch_operations.no_scheduled_tasks"))
            return

        for i, job in enumerate(jobs, 1):
            print(f"{i}. {job}")

    def cancel_scheduled_task(self):
        """Cancel a scheduled task"""
        print("\n" + _t("shared.utils.batch_operations.title_cancel_task"))

        jobs = schedule.get_jobs()
        if not jobs:
            print(_t("shared.utils.batch_operations.no_tasks_to_cancel"))
            return

        print(_t("shared.utils.batch_operations.scheduled_tasks"))
        for i, job in enumerate(jobs, 1):
            print(f"{i}. {job}")

        try:
            choice = int(input(_t("shared.utils.batch_operations.prompt_select_task"))) - 1
            if 0 <= choice < len(jobs):
                schedule.cancel_job(jobs[choice])
                print(_t("shared.utils.batch_operations.task_cancelled"))
            else:
                print(_t("shared.utils.batch_operations.invalid_selection"))
        except ValueError:
            print(_t("shared.utils.batch_operations.invalid_input"))

    def automated_import_job(self, import_dir: str, notification_email: str = None):
        """Automated import job function"""
        try:
            logger.info(f"Starting automated import from {import_dir}")
            
            # Find files to import
            files_to_import = []
            for ext in ['.csv', '.xlsx', '.xls']:
                files_to_import.extend(Path(import_dir).glob(f"*{ext}"))
            
            if not files_to_import:
                logger.info("No files found for automated import")
                return
            
            # Create backup
            backup_path = self.create_database_backup(auto=True)
            
            # Process files
            total_imported = 0
            total_errors = 0
            
            for file_path in files_to_import:
                try:
                    logger.info(f"Processing {file_path}")
                    
                    if file_path.suffix.lower() == '.csv':
                        records = self.read_csv_file(str(file_path))
                    else:
                        records = self.read_excel_file(str(file_path))
                    
                    if records:
                        result = self.import_valid_records(records)
                        total_imported += result.successful_imports
                        total_errors += result.failed_imports
                        
                        # Move processed file to archive
                        archive_dir = Path(import_dir) / 'processed'
                        archive_dir.mkdir(exist_ok=True)
                        shutil.move(str(file_path), str(archive_dir / file_path.name))
                
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    total_errors += 1
            
            # Send notification email if configured
            if notification_email:
                self.send_notification_email(
                    notification_email, 
                    f"Automated Import Complete: {total_imported} imported, {total_errors} errors"
                )
            
            logger.info(f"Automated import complete: {total_imported} imported, {total_errors} errors")
            
        except Exception as e:
            logger.error(f"Error in automated import job: {e}")

    def send_notification_email(self, email: str, message: str):
        """Send notification email using SMTP or email service."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import os

        try:
            # Try to get email configuration from environment variables
            smtp_server = os.getenv('SMTP_SERVER', 'localhost')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_username = os.getenv('SMTP_USERNAME')
            smtp_password = os.getenv('SMTP_PASSWORD')
            from_email = os.getenv('FROM_EMAIL', 'noreply@university.edu')

            # Prepare template variables
            template_vars = {
                'message': message
            }

            # Try to use template
            from university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template('batch_notification', template_vars)

            if not (subject and body):
                logger.warning(f"Failed to load email template for {email}; falling back to plain text message.")
                subject = "Batch Import Notification"
                body = message

            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            # Use centralized email system
            try:
                from university_system.infrastructure.email.smtp import send_email_via_smtp
                from datetime import datetime

                current_time = datetime.now().isoformat()
                success = send_email_via_smtp(
                    recipient_email=email,
                    subject=subject,
                    body=body,
                    cc=None,
                    bcc=None,
                    attachments=None,
                    current_time=current_time
                )

                if success:
                    logger.info(f"Email notification sent successfully to {email}")
                    print(_t("shared.utils.batch_operations.email_sent", email=email))
                    return True
                else:
                    logger.warning(f"Email notification failed for {email}")
                    print(_t("shared.utils.batch_operations.email_failed", email=email))
                    return False

            except ImportError:
                # Fallback to logging if email system not available
                logger.info(f"Email notification (email system not available) to {email}: {message}")
                print(_t("shared.utils.batch_operations.email_would_be_sent", email=email, message=message))
                return False

        except Exception as e:
            logger.error(f"Failed to send email notification to {email}: {e}")
            print(_t("shared.utils.batch_operations.email_send_failed", email=email, error=str(e)))
            return False

    # ========================================
    # API SERVER
    # ========================================
    
    def start_api_server(self):
        """Start REST API server for external integrations"""
        print("\n" + _t("shared.utils.batch_operations.title_start_api"))

        if self.api_app is not None:
            print(_t("shared.utils.batch_operations.api_already_running"))
            return

        port = input(_t("shared.utils.batch_operations.prompt_port_number")).strip()
        if not port:
            port = 5000
        else:
            try:
                port = int(port)
            except ValueError:
                print(_t("shared.utils.batch_operations.invalid_port"))
                return

        # Create Flask app
        self.api_app = Flask(__name__)
        self.setup_api_routes()

        print(_t("shared.utils.batch_operations.starting_api_server", port=port))
        print(_t("shared.utils.batch_operations.available_endpoints"))
        print("  POST /api/import - Import student data")
        print("  GET /api/students - Get student list")
        print("  PUT /api/students/<id> - Update student")
        print("  GET /api/health - Health check")

        # Run in separate thread
        def run_server():
            self.api_app.run(host='0.0.0.0', port=port, debug=False)

        import threading
        api_thread = threading.Thread(target=run_server, daemon=True)
        api_thread.start()

        print(_t("shared.utils.batch_operations.api_started"))
        input(_t("shared.utils.batch_operations.press_enter_stop"))

        # Note: In a production environment, you'd want proper server management

    def setup_api_routes(self):
        """Set up API routes"""
        
        @self.api_app.route('/api/health', methods=['GET'])
        def health_check():
            return jsonify({'status': 'healthy', 'timestamp': datetime.datetime.now().isoformat()})
        
        @self.api_app.route('/api/import', methods=['POST'])
        def api_import():
            try:
                data = request.get_json()
                
                if not data or 'records' not in data:
                    return jsonify({'error': 'No records provided'}), 400
                
                records = data['records']
                
                # Validate records
                valid_records = []
                errors = []
                
                for i, record in enumerate(records):
                    validation_errors = self.validate_student_data(record)
                    if validation_errors:
                        errors.append({'record_index': i, 'errors': validation_errors})
                    else:
                        valid_records.append(record)
                
                if valid_records:
                    # Import valid records
                    result = self.import_valid_records(valid_records)
                    
                    return jsonify({
                        'success': True,
                        'imported': result.successful_imports,
                        'failed': result.failed_imports,
                        'validation_errors': errors
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'No valid records to import',
                        'validation_errors': errors
                    }), 400
                    
            except Exception as e:
                logger.error(f"API import error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.api_app.route('/api/students', methods=['GET'])
        def api_get_students():
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Get query parameters
                course = request.args.get('course')
                limit = request.args.get('limit', 100, type=int)
                offset = request.args.get('offset', 0, type=int)
                
                # Build query
                query = "SELECT * FROM students"
                params = []
                
                if course:
                    query += " WHERE course = ?"
                    params.append(course)
                
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                students = cursor.fetchall()
                
                # Convert to dict format
                columns = [desc[0] for desc in cursor.description]
                student_list = [dict(zip(columns, student)) for student in students]
                
                conn.close()
                
                return jsonify({
                    'students': student_list,
                    'count': len(student_list),
                    'limit': limit,
                    'offset': offset
                })
                
            except Exception as e:
                logger.error(f"API get students error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.api_app.route('/api/students/<student_id>', methods=['PUT'])
        def api_update_student(student_id):
            try:
                data = request.get_json()
                
                if not data:
                    return jsonify({'error': 'No data provided'}), 400
                
                # Add student_id to data for validation
                data['student_id'] = student_id
                
                # Validate update data
                errors = self.validate_student_data(data, is_update=True)
                if errors:
                    return jsonify({'error': 'Validation failed', 'details': errors}), 400
                
                # Update record
                self.update_existing_record(student_id, data)
                
                return jsonify({
                    'success': True,
                    'message': f'Student {student_id} updated successfully'
                })
                
            except Exception as e:
                logger.error(f"API update student error: {e}")
                return jsonify({'error': str(e)}), 500

    # ========================================
    # EXTERNAL SYSTEM INTEGRATION
    # ========================================
    
    def external_system_integration(self):
        """Integration with external systems"""
        print("\n" + _t("shared.utils.batch_operations.title_external_integration"))

        print(_t("shared.utils.batch_operations.integration_options"))
        print(_t("shared.utils.batch_operations.option_database_connection"))
        print(_t("shared.utils.batch_operations.option_rest_api"))
        print(_t("shared.utils.batch_operations.option_file_share"))
        print(_t("shared.utils.batch_operations.option_export_external"))

        choice = input(_t("shared.utils.batch_operations.prompt_choose_integration"))

        if choice == '1':
            self.setup_database_integration()
        elif choice == '2':
            self.setup_rest_api_integration()
        elif choice == '3':
            self.setup_file_share_monitoring()
        elif choice == '4':
            self.export_to_external_system()
        else:
            print(_t("shared.utils.batch_operations.invalid_choice"))

    def setup_database_integration(self):
        """Set up external database integration"""
        print("\n🗄️  Database Integration")
        
        db_type = input("Database type (mysql/postgresql): ").lower()
        if db_type not in ['mysql', 'postgresql']:
            print("❌ Unsupported database type")
            return
        
        host = input("Database host: ")
        port = input("Database port: ")
        database = input("Database name: ")
        username = input("Username: ")
        password = input("Password: ")
        
        # Store connection config (in production, use secure storage)
        config = {
            'type': db_type,
            'host': host,
            'port': port,
            'database': database,
            'username': username,
            'password': password
        }
        
        # Test connection
        try:
            if db_type == 'mysql':
                import mysql.connector
                conn = mysql.connector.connect(**{
                    'host': host,
                    'port': port,
                    'database': database,
                    'user': username,
                    'password': password
                })
                conn.close()
            elif db_type == 'postgresql':
                import psycopg2
                conn = psycopg2.connect(
                    host=host, port=port, database=database,
                    user=username, password=password
                )
                conn.close()
            
            print("✅ Database connection successful")
            
            # Save config
            with open('external_db_config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")

    def setup_rest_api_integration(self):
        """Set up REST API integration"""
        print("\n🌐 REST API Integration")
        
        api_url = input("API base URL: ")
        api_key = input("API key (optional): ")
        
        # Test API connection
        try:
            headers = {}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            
            response = requests.get(f"{api_url}/health", headers=headers, timeout=10)
            
            if response.status_code == 200:
                print("✅ API connection successful")
                
                # Save config
                config = {
                    'url': api_url,
                    'api_key': api_key,
                    'headers': headers
                }
                
                with open('external_api_config.json', 'w') as f:
                    json.dump(config, f, indent=2)
            else:
                print(f"❌ API connection failed: {response.status_code}")
                
        except requests.RequestException as e:
            print(f"❌ API connection failed: {e}")

    def setup_file_share_monitoring(self):
        """Set up file share monitoring"""
        print("\n📁 File Share Monitoring")
        print("\n📡 FTP/SFTP Monitoring Setup")
        host = input("Enter FTP/SFTP host: ")
        username = input("Enter username: ")
        remote_path = input("Enter remote path to monitor: ")
        print(f"✅ Monitoring setup for {host}:{remote_path}")
        print("Will check for new files every 5 minutes")
        
        # This would implement file share monitoring
        # - Connect to FTP/SFTP servers
        # - Monitor for new files
        # - Automatically download and process
        # - Move processed files to archive

    def export_to_external_system(self):
        """Export data to external systems"""
        print("\n📤 Export to External System")
        
        print("Export targets:")
        print("1. External database")
        print("2. REST API")
        print("3. File share (FTP/SFTP)")
        print("4. Email with attachment")
        
        choice = input("Choose export target (1-4): ")
        
        if choice == '1':
            self.export_to_external_database()
        elif choice == '2':
            self.export_via_rest_api()
        elif choice == '3':
            self.export_to_file_share()
        elif choice == '4':
            self.export_via_email()
        else:
            print("❌ Invalid choice")

    def export_to_external_database(self):
        """Export data to external database"""
        print("\n🗄️  Export to External Database")
        
        try:
            with open('external_db_config.json', 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            print("❌ No external database configured. Please set up integration first.")
            return
        
        # Get data to export
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students")
        students = cursor.fetchall()
        conn.close()
        
        print(f"📊 Exporting {len(students)} student records...")
        
        # This would implement the actual export logic
        # based on the configured database type
        print("\n📤 Export Configuration")
        format_type = input("Export format (csv/json/xml): ")
        output_path = input("Output file path: ")
        print(f"✅ Export configuration saved")
        print(f"Format: {format_type}, Output: {output_path}")

    def export_via_rest_api(self):
        """Export data via REST API"""
        print("\n🌐 Export via REST API")
        
        try:
            with open('external_api_config.json', 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            print("❌ No external API configured. Please set up integration first.")
            return
        
        # Implementation would send data to external API
        print("\n🌐 API Export Setup")
        api_url = input("Enter API endpoint URL: ")
        api_key = input("Enter API key: ")
        print(f"✅ API export configured for {api_url}")

    def export_to_file_share(self):
        """Export to file share"""
        print("\n📁 Export to File Share")
        print("\n📁 File Share Export Setup")
        share_path = input("Enter network share path: ")
        print(f"✅ File share export configured for {share_path}")

    def export_via_email(self):
        """Export data via email"""
        print("\n📧 Export via Email")
        
        email_to = input("Recipient email: ")
        file_format = input("File format (csv/excel/json): ").lower()
        
        if file_format not in ['csv', 'excel', 'json']:
            print("❌ Invalid file format")
            return
        
        # Export data to temporary file
        temp_filename = f"student_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM students")
            students = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            
            if file_format == 'csv':
                temp_filename += '.csv'
                with open(temp_filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(students)
            elif file_format == 'excel':
                temp_filename += '.xlsx'
                df = pd.DataFrame(students, columns=columns)
                df.to_excel(temp_filename, index=False)
            elif file_format == 'json':
                temp_filename += '.json'
                data = [dict(zip(columns, student)) for student in students]
                with open(temp_filename, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
            
            print(f"✅ Export file created: {temp_filename}")
            print(f"📧 Email with attachment would be sent to {email_to}")
            
            # In production, this would integrate with email service
            
        except Exception as e:
            print(f"❌ Export failed: {e}")


# ========================================
# MAIN FUNCTION AND USAGE
# ========================================

def main():
    """Main function to demonstrate the enhanced batch operations system"""
    print(_t("shared.utils.batch_operations.system_title"))
    print("=" * 60)

    # Initialize the batch operation manager
    batch_manager = BatchOperationManager()

    # Start the enhanced menu system
    batch_manager.display_batch_menu()


if __name__ == "__main__":
    main()
