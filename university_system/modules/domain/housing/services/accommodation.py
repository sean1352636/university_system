# Standard library imports
import csv
import os
import logging
import re
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging first using centralized configuration
from university_system.utils.logging.log_config import configure_logging

# Setup logger using centralized configuration
logger = configure_logging(name=__name__)

# Application imports
from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection

# Optional dependencies for export and dashboards
try:
    import pandas as pd
except ImportError:
    pd = None
    logger.warning("pandas not available. Some export features will be disabled.")

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph  # Fixed typo
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
except ImportError:
    canvas = None
    logger.warning("reportlab not available. PDF generation will be disabled.")

# Integration imports with fallbacks
try:
    from university_system.infrastructure.auth import get_current_user, UserAuth
except ImportError:
    logger.warning("Authentication module not available. Using fallback.")
    def get_current_user():  # type: ignore
        return 'system'
    UserAuth = None  # type: ignore

try:
    from university_system.infrastructure import email as email_manager
except ImportError:
    email_manager = None
    logger.warning("Email manager not available. Email features will be disabled.")

try:
    from university_system.infrastructure.database.data_backup import backup_before_operation
except ImportError:
    logger.warning("Data backup module not available. Using fallback.")
    def backup_before_operation(operation_type):  # type: ignore
        logger.info(f"Backup requested before {operation_type} operation, but data_backup module not available")

# Shared path constants keep runtime artefacts inside program/data
from university_system.modules.shared.constants import paths

# Configuration constants
DB_PATH = os.fspath(paths.DEFAULT_DB_PATH)
NOTIFICATION_THRESHOLD_DAYS = 7
TEMPLATES_TABLE = 'accommodation_templates'
ACCOMMODATION_LOG_PATH = os.fspath(paths.LOG_DIR / 'accommodation')
UPLOADS_DIR = os.fspath(paths.DATA_DIR / 'uploads' / 'accommodation')

# Ensure required directories exist
for directory in [ACCOMMODATION_LOG_PATH, UPLOADS_DIR]:
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Could not create directory {directory}: {e}")

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# Import centralized auth management
from university_system.infrastructure.shared_context import get_auth, set_auth as set_shared_auth

# Import internationalization support
from university_system.modules.shared.utils.i18n import get_text

# Import secure file upload handler
try:
    from university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None

# Import immutable audit logging for compliance
try:
    from university_system.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        get_current_user_id,
    )
    from university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False
    def secure_filename(x):
        return x

auth = None
_AUDIT_LOG_COLUMNS_CACHE = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Set in centralized shared context
    set_shared_auth(auth_instance)
    # Also set it in the user_authentication module if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
def log_action(action, accommodation_id=None, details=None):
    """Record an audit log entry with enhanced tracking."""
    try:
        user = get_current_user()
        user_id = None
        legacy_user_label = 'system'

        # Handle different types of user values
        if user is None or user == 'system':
            # For system actions, use NULL user_id but include username in details
            user_id = None
            if details:
                details = f"[system] {details}"
            else:
                details = "[system action]"
            legacy_user_label = 'system'
        elif isinstance(user, dict) and 'id' in user:
            # User object with ID
            user_id = user['id']
            legacy_user_label = str(user.get('username') or user.get('email') or user.get('id'))
        elif isinstance(user, (int, str)) and str(user).isdigit():
            # Numeric user ID
            user_id = int(user)
            legacy_user_label = str(user_id)
        else:
            # Unknown user format, log as system
            user_id = None
            if details:
                details = f"[unknown_user:{user}] {details}"
            else:
                details = f"[unknown_user:{user}]"
            legacy_user_label = str(user)

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ip_address = "127.0.0.1"  # Default localhost - in a real system, would get actual IP

        if details is not None and not isinstance(details, str):
            details = str(details)

        try:
            record_id_int = int(accommodation_id) if accommodation_id is not None else None
        except (TypeError, ValueError):
            record_id_int = None
        record_id_text = str(accommodation_id) if accommodation_id is not None else None

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            global _AUDIT_LOG_COLUMNS_CACHE
            if _AUDIT_LOG_COLUMNS_CACHE is None:
                cursor.execute("PRAGMA table_info(audit_log)")
                _AUDIT_LOG_COLUMNS_CACHE = tuple(row[1] for row in cursor.fetchall())

            columns = _AUDIT_LOG_COLUMNS_CACHE or ()

            if 'table_affected' in columns:
                cursor.execute('''
                    INSERT INTO audit_log (user_id, action, table_affected, record_id, new_values, timestamp, ip_address, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, action, 'accommodations', record_id_text, details, ts, ip_address, True))
            else:
                legacy_user_value = legacy_user_label or 'system'
                cursor.execute('''
                    INSERT INTO audit_log (action, user_id, accommodation_id, details, ip_address, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (action, legacy_user_value, record_id_int, details, ip_address, ts))

            conn.commit()
            logging.info(f"Audit log: {action} by {user_id or legacy_user_label} for accommodation {accommodation_id}")
    except Exception as e:
        logging.error(f"Failed to log action '{action}': {e}")
        print(get_text("housing.accommodation.log.warning_action_logging_failed", "Warning: Action logging failed: {error}").format(error=e))
        
def init_accommodation_db():
    """Initialize accommodation, audit, and template tables with better error handling."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Create accommodations table with additional fields
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accommodations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    accommodation_type TEXT NOT NULL,
                    description TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT DEFAULT 'active',
                    approved_by TEXT,
                    approval_date TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            ''')
            
            # Create audit log table with more detailed tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    accommodation_id INTEGER,
                    details TEXT,
                    ip_address TEXT,
                    timestamp TEXT NOT NULL
                )
            ''')
            
            # Create templates table
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS [" + TEMPLATES_TABLE + "] ("
                " name TEXT PRIMARY KEY,"
                " accommodation_type TEXT NOT NULL,"
                " description TEXT,"
                " start_offset_days INTEGER,"
                " duration_days INTEGER,"
                " created_by TEXT,"
                " created_at TEXT,"
                " updated_at TEXT"
                ")"
            )
            
            # Create accommodation types table for standardized types
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accommodation_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    requires_approval BOOLEAN DEFAULT 0,
                    max_duration_days INTEGER,
                    created_at TEXT
                )
            ''')
            
            # Add some default accommodation types if the table is empty
            cursor.execute('SELECT COUNT(*) FROM accommodation_types')
            if cursor.fetchone()[0] == 0:
                default_types = [
                    ('Extended Time', 'Additional time for assignments or exams', 0, 365),
                    ('Alternate Format', 'Materials provided in alternate formats', 0, 365),
                    ('Note-Taking', 'Note-taking assistance in classes', 0, 365),
                    ('Assistive Technology', 'Access to specialized technology', 1, 365),
                    ('Flexible Attendance', 'Modified attendance requirements', 1, 180)
                ]
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for type_name, desc, req_approval, max_days in default_types:
                    cursor.execute('''
                        INSERT INTO accommodation_types 
                        (type_name, description, requires_approval, max_duration_days, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (type_name, desc, req_approval, max_days, now))
                
            # Create accommodation_documents table for attaching documentation
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accommodation_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    accommodation_id INTEGER NOT NULL,
                    document_name TEXT NOT NULL,
                    document_path TEXT NOT NULL,
                    uploaded_by TEXT,
                    uploaded_at TEXT,
                    FOREIGN KEY (accommodation_id) REFERENCES accommodations(id)
                )
            ''')
            
            conn.commit()
            logging.info("Accommodation database initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize accommodation database: {e}")
        print(get_text("housing.accommodation.db.error_init_failed", "Error: Could not initialize accommodation database. Details: {error}").format(error=e))
        # Attempt to create essential tables as fallback
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS accommodations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        accommodation_type TEXT NOT NULL,
                        description TEXT,
                        start_date TEXT,
                        end_date TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        accommodation_id INTEGER,
                        timestamp TEXT NOT NULL
                    )
                ''')
                conn.commit()
                logging.info("Minimal accommodation database created as fallback")
                print(get_text("housing.accommodation.db.created_minimal_tables", "Created minimal accommodation database tables"))
        except Exception as fallback_e:
            logging.critical(f"Fallback database creation also failed: {fallback_e}")
            print(get_text("housing.accommodation.db.critical_error_minimal_tables", "Critical Error: Could not create even minimal database tables: {error}").format(error=fallback_e))

def validate_date(date_str):
    """Validate date format and return tuple (is_valid, error_message)."""
    if not date_str:  # Empty date is allowed (means indefinite or not set)
        return True, None
    
    try:
        # Validate format and attempts to parse the date
        date_obj = datetime.fromisoformat(date_str)
        
        # Check if date is not too far in the past or future (optional)
        now = datetime.now()
        max_future = now + timedelta(days=3650)  # ~10 years
        min_past = now - timedelta(days=3650)  # ~10 years
        
        if date_obj > max_future:
            return False, get_text("housing.accommodation.validation.date_too_far_future", "Date is too far in the future (maximum 10 years ahead)")
        if date_obj < min_past:
            return False, get_text("housing.accommodation.validation.date_too_far_past", "Date is too far in the past (maximum 10 years ago)")
            
        return True, None
    except ValueError:
        return False, get_text("housing.accommodation.validation.invalid_date_format", "Invalid date format. Please use YYYY-MM-DD format.")
    except Exception as e:
        return False, get_text("housing.accommodation.validation.date_validation_error", "Date validation error: {error}").format(error=str(e))


def check_conflict(student_id, accommodation_type, start_date, end_date, excluded_id=None):
    """Return True if new dates overlap existing for same student and type, with improved error handling."""
    init_accommodation_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Exclude the current record if we're updating
            exclude_clause = " AND id != ?" if excluded_id else ""
            params = [student_id, accommodation_type]
            if excluded_id:
                params.append(excluded_id)
                
            cursor.execute(
                "SELECT id, start_date, end_date FROM accommodations"
                " WHERE student_id=? AND accommodation_type=? AND status='active' " + exclude_clause,
                params)
            
            rows = cursor.fetchall()
            if not rows:
                return False
                
            for aid, sd, ed in rows:
                if not sd and not ed:  # Indefinite accommodation already exists
                    return True
                
                if not start_date and not end_date:  # New indefinite accommodation
                    return True
                    
                # Convert to date objects for comparison
                existing_start = datetime.fromisoformat(sd) if sd else datetime.min
                existing_end = datetime.fromisoformat(ed) if ed else datetime.max
                new_start = datetime.fromisoformat(start_date) if start_date else datetime.min
                new_end = datetime.fromisoformat(end_date) if end_date else datetime.max
                
                # Check for overlap
                if not (new_end < existing_start or new_start > existing_end):
                    return True
        
        return False
    except Exception as e:
        logging.error(f"Error checking accommodation conflicts: {e}")
        print(get_text("housing.accommodation.conflict.error_checking", "Error checking for accommodation conflicts: {error}").format(error=e))
        # Since we couldn't check for conflicts, fail safe and return True
        return True

def get_accommodation_types():
    """Retrieve list of available accommodation types from the database."""
    init_accommodation_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM accommodation_types ORDER BY type_name')
            types = [row[0] for row in cursor.fetchall()]
            return types if types else ["Extended Time", "Alternate Format", "Note-Taking", "Assistive Technology"]
    except Exception as e:
        logging.error(f"Error retrieving accommodation types: {e}")
        # Return default list if database query fails
        return ["Extended Time", "Alternate Format", "Note-Taking", "Assistive Technology"]


def validate_student_id(student_id):
    """Validate if student exists in the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
            return cursor.fetchone()[0] > 0
    except Exception as e:
        logging.error(f"Error validating student ID: {e}")
        return False


def add_accommodation():
    """Register a student to an accommodation, with conflict detection and better validation."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_add", "You must be logged in to add accommodations."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_add", "You don't have permission to add accommodations."))
        return
    
    # Backup before making changes
    backup_before_operation('accommodation_add')
    
    init_accommodation_db()
    try:
        # Get student ID with validation
        while True:
            student_id = input(get_text("housing.accommodation.input.enter_student_id", "Enter student ID: ")).strip()
            if not student_id:
                print(get_text("housing.accommodation.error.student_id_required", "Error: Student ID is required."))
                continue

            if not validate_student_id(student_id):
                print(get_text("housing.accommodation.error.student_not_found", "Error: Student ID not found in the system."))
                retry = input(get_text("housing.accommodation.input.try_again", "Would you like to try again? (y/n): "))
                if retry.lower() != 'y':
                    return
                continue
            break

        # Get accommodation type with autocomplete
        available_types = get_accommodation_types()
        print("\n" + get_text("housing.accommodation.label.available_types", "Available accommodation types:"))
        for i, type_name in enumerate(available_types):
            print(f"{i+1}. {type_name}")

        while True:
            type_choice = input("\n" + get_text("housing.accommodation.input.select_type", "Select type (number or enter custom): ")).strip()
            if type_choice.isdigit() and 1 <= int(type_choice) <= len(available_types):
                accommodation_type = available_types[int(type_choice)-1]
                break
            elif type_choice:
                accommodation_type = type_choice
                break
            else:
                print(get_text("housing.accommodation.error.type_required", "Error: Accommodation type is required."))

        # Get description
        description = input(get_text("housing.accommodation.input.enter_description", "Enter description [optional]: ")).strip() or None

        # Get dates with validation
        while True:
            start_date = input(get_text("housing.accommodation.input.enter_start_date", "Enter start date (YYYY-MM-DD) [optional]: ")).strip() or None
            if start_date:
                valid, error = validate_date(start_date)
                if not valid:
                    print(get_text("housing.accommodation.error.generic", "Error: {error}").format(error=error))
                    continue
            break

        while True:
            end_date = input(get_text("housing.accommodation.input.enter_end_date", "Enter end date (YYYY-MM-DD) [optional]: ")).strip() or None
            if end_date:
                valid, error = validate_date(end_date)
                if not valid:
                    print(get_text("housing.accommodation.error.generic", "Error: {error}").format(error=error))
                    continue

                # Check that end date is after start date
                if start_date and end_date:
                    start = datetime.fromisoformat(start_date)
                    end = datetime.fromisoformat(end_date)
                    if end <= start:
                        print(get_text("housing.accommodation.error.end_date_after_start", "Error: End date must be after start date."))
                        continue
            break

        # Check for conflicts
        if check_conflict(student_id, accommodation_type, start_date, end_date):
            print(get_text("housing.accommodation.warning.overlap_existing", "Warning: This accommodation overlaps an existing record."))
            cont = input(get_text("housing.accommodation.input.continue_anyway", "Continue anyway? (y/n): "))
            if cont.lower() != 'y':
                return

        # Additional fields
        notes = input(get_text("housing.accommodation.input.additional_notes", "Additional notes [optional]: ")).strip() or None
        status = 'pending' if 'requires_approval' else 'active'
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO accommodations 
                (student_id, accommodation_type, description, start_date, end_date, status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, accommodation_type, description, start_date, end_date, status, notes, now, now))
            aid = cursor.lastrowid
            conn.commit()
        
        print(get_text("housing.accommodation.success.added", "Accommodation added successfully."))

        # Document upload option
        doc_upload = input(get_text("housing.accommodation.input.upload_documentation", "Would you like to upload supporting documentation? (y/n): "))
        if doc_upload.lower() == 'y':
            upload_accommodation_document(aid)
            
        log_action('add', aid, f"Added {accommodation_type} for student {student_id}")
        notify_student(student_id, 'Accommodation Registered', 
                      f"You have been registered for {accommodation_type}.")
                      
        # Display the added accommodation details
        view_accommodation_by_id(aid)
        
    except Exception as e:
        logging.error(f"Error adding accommodation: {e}")
        print(get_text("housing.accommodation.error.adding", "Error adding accommodation: {error}").format(error=e))
        print(get_text("housing.accommodation.error.try_again_or_contact", "Please try again or contact technical support."))

def upload_accommodation_document(accommodation_id):
    """Upload a document for an accommodation by copying the file to a managed directory."""
    auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_upload", "You must be logged in to upload documents."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_upload", "You don't have permission to upload documents."))
        return

    try:
        document_name = input(get_text("housing.accommodation.input.enter_document_name", "Enter document name: ")).strip()
        if not document_name:
            print(get_text("housing.accommodation.error.document_name_required", "Error: Document name is required."))
            return

        file_path = input(get_text("housing.accommodation.input.enter_file_path", "Enter full path to the file: ")).strip()
        if not file_path or not os.path.exists(file_path):
            print(get_text("housing.accommodation.error.invalid_file_path", "Error: File path is invalid or file does not exist."))
            return

        # Read file content for secure validation
        original_filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Validate file using secure upload handler
        if SECURE_UPLOAD_AVAILABLE and validate_upload:
            validation = validate_upload(original_filename, file_content, category='documents')
            if not validation['valid']:
                print(f"Error: File validation failed - {validation['error']}")
                logger.warning(f"Secure upload validation failed for {original_filename}: {validation['error']}")
                return
            safe_name = validation['safe_filename']
        else:
            safe_name = secure_filename(original_filename)

        # Ensure uploads directory exists with restrictive permissions
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        try:
            os.chmod(UPLOADS_DIR, 0o700)
        except OSError:
            pass

        # Create a safe unique filename
        ext = os.path.splitext(safe_name)[1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{accommodation_id}_{timestamp}{ext}"
        destination_path = os.path.join(UPLOADS_DIR, unique_filename)

        # Copy the file to uploads dir securely
        shutil.copy(file_path, destination_path)

        # Set restrictive permissions on uploaded file
        try:
            os.chmod(destination_path, 0o600)
        except OSError:
            pass

        logger.info(f"Accommodation document uploaded securely: {unique_filename}")

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = get_current_user()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO accommodation_documents
                (accommodation_id, document_name, document_path, uploaded_by, uploaded_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (accommodation_id, document_name, destination_path, user, now))
            conn.commit()

        print(get_text("housing.accommodation.success.document_uploaded", "Document uploaded and recorded successfully."))
        log_action('upload_document', accommodation_id, f"Uploaded document: {document_name}")

    except Exception as e:
        logging.error(f"Error uploading document: {e}")
        print(get_text("housing.accommodation.error.uploading_document", "Error uploading document: {error}").format(error=e))

def view_accommodation_by_id(accommodation_id):
    """View a specific accommodation by ID."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get accommodation details
            cursor.execute('''
                SELECT a.*, s.first_name, s.last_name, s.email_address
                FROM accommodations a
                LEFT JOIN students s ON a.student_id = s.student_id
                WHERE a.id = ?
            ''', (accommodation_id,))
            
            accommodation = cursor.fetchone()
            if not accommodation:
                print(get_text("housing.accommodation.error.not_found_id", "No accommodation found with ID {id}").format(id=accommodation_id))
                return
                
            # Get documents
            cursor.execute('''
                SELECT * FROM accommodation_documents
                WHERE accommodation_id = ?
            ''', (accommodation_id,))
            
            documents = cursor.fetchall()
            
            # Display accommodation details
            print("\n" + "="*60)
            print(get_text("housing.accommodation.view.id", "Accommodation ID: {id}").format(id=accommodation['id']))
            print(get_text("housing.accommodation.view.student", "Student: {student_id} - {first_name} {last_name}").format(
                student_id=accommodation['student_id'],
                first_name=accommodation['first_name'],
                last_name=accommodation['last_name']))
            print(get_text("housing.accommodation.view.type", "Type: {type}").format(type=accommodation['accommodation_type']))
            print(get_text("housing.accommodation.view.description", "Description: {description}").format(
                description=accommodation['description'] or get_text("housing.accommodation.label.na", "N/A")))
            print(get_text("housing.accommodation.view.start_date", "Start Date: {date}").format(
                date=accommodation['start_date'] or get_text("housing.accommodation.label.not_specified", "Not specified")))
            print(get_text("housing.accommodation.view.end_date", "End Date: {date}").format(
                date=accommodation['end_date'] or get_text("housing.accommodation.label.not_specified", "Not specified")))
            print(get_text("housing.accommodation.view.status", "Status: {status}").format(status=accommodation['status']))
            print(get_text("housing.accommodation.view.notes", "Notes: {notes}").format(
                notes=accommodation['notes'] or get_text("housing.accommodation.label.na", "N/A")))
            print(get_text("housing.accommodation.view.created", "Created: {date}").format(date=accommodation['created_at']))
            print(get_text("housing.accommodation.view.updated", "Last Updated: {date}").format(date=accommodation['updated_at']))

            if documents:
                print("\n" + get_text("housing.accommodation.view.attached_documents", "Attached Documents:"))
                for doc in documents:
                    print(f" - {doc['document_name']} ({get_text('housing.accommodation.view.uploaded', 'Uploaded')}: {doc['uploaded_at']})")

            print("="*60)
            
    except Exception as e:
        logging.error(f"Error viewing accommodation {accommodation_id}: {e}")
        print(get_text("housing.accommodation.error.viewing", "Error viewing accommodation: {error}").format(error=e))


def bulk_import_from_csv(filepath):
    """Bulk register students from a CSV file with enhanced validation and error handling."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_bulk_import", "You must be logged in to perform bulk imports."))
        return

    if not auth.check_permission('manage_accommodations') or not auth.check_permission('batch_operations'):
        print(get_text("housing.accommodation.auth.no_permission_bulk_import", "You don't have permission to perform bulk imports."))
        return

    # Backup before making changes
    backup_before_operation('accommodation_bulk_import')

    init_accommodation_db()
    if not os.path.exists(filepath):
        print(get_text("housing.accommodation.error.file_not_found", "Error: File not found."))
        return

    print(get_text("housing.accommodation.bulk.beginning_import", "Beginning bulk import from {filepath}").format(filepath=filepath))
    success_count = 0
    error_count = 0
    conflict_count = 0
    
    try:
        # Track imported records for logging
        import_log = []
        
        with open(filepath, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            required_fields = ['student_id', 'accommodation_type']
            
            # Validate CSV headers
            headers = reader.fieldnames
            if not all(field in headers for field in required_fields):
                print(get_text("housing.accommodation.error.csv_missing_columns", "Error: CSV must contain columns: {columns}").format(columns=', '.join(required_fields)))
                return
                
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header row
                try:
                    # Extract and validate required fields
                    student_id = row.get('student_id', '').strip()
                    typ = row.get('accommodation_type', '').strip()
                    
                    if not student_id or not typ:
                        error_count += 1
                        import_log.append(f"Row {row_num}: Missing required fields")
                        continue
                        
                    # Validate student exists
                    if not validate_student_id(student_id):
                        error_count += 1
                        import_log.append(f"Row {row_num}: Student ID {student_id} not found")
                        continue
                    
                    # Extract optional fields
                    desc = row.get('description', '').strip() or None
                    sd = row.get('start_date', '').strip() or None
                    ed = row.get('end_date', '').strip() or None
                    notes = row.get('notes', '').strip() or None
                    status = row.get('status', '').strip() or 'active'
                    
                    # Validate dates
                    if sd:
                        valid, error = validate_date(sd)
                        if not valid:
                            error_count += 1
                            import_log.append(f"Row {row_num}: Invalid start date - {error}")
                            continue
                            
                    if ed:
                        valid, error = validate_date(ed)
                        if not valid:
                            error_count += 1
                            import_log.append(f"Row {row_num}: Invalid end date - {error}")
                            continue
                    
                    # Check date range
                    if sd and ed:
                        try:
                            start = datetime.fromisoformat(sd)
                            end = datetime.fromisoformat(ed)
                            if end <= start:
                                error_count += 1
                                import_log.append(f"Row {row_num}: End date must be after start date")
                                continue
                        except ValueError:
                            error_count += 1
                            import_log.append(f"Row {row_num}: Date format error")
                            continue
                    
                    # Check for conflicts
                    if check_conflict(student_id, typ, sd, ed):
                        conflict_count += 1
                        import_log.append(f"Row {row_num}: Conflict for student {student_id}, type {typ}")
                        # Continue with import if configured to do so
                        # In a real system, you might want to make this configurable
                    
                    # Insert into database
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO accommodations 
                            (student_id, accommodation_type, description, start_date, end_date, status, notes, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (student_id, typ, desc, sd, ed, status, notes, now, now))
                        aid = cursor.lastrowid
                        conn.commit()
                        
                        log_action('bulk_add', aid, f"Bulk import: {typ} for {student_id}")
                        success_count += 1
                        import_log.append(f"Row {row_num}: Successfully added {typ} for {student_id}")
                        
                except sqlite3.Error as db_e:
                    error_count += 1
                    import_log.append(f"Row {row_num}: Database error - {db_e}")
                    logging.error(f"Bulk import DB error for row {row_num}: {db_e}")
                    continue
                except Exception as row_e:
                    error_count += 1
                    import_log.append(f"Row {row_num}: Unexpected error - {row_e}")
                    logging.error(f"Bulk import error for row {row_num}: {row_e}")
                    continue
        
        # Write import log to file
        log_filename = f"accommodation_import_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        log_path = os.path.join(ACCOMMODATION_LOG_PATH, log_filename)
        try:
            with open(log_path, 'w') as log_file:
                log_file.write(f"Import from {filepath} at {now}\n")
                log_file.write(f"Summary: {success_count} succeeded, {error_count} failed, {conflict_count} conflicts\n\n")
                log_file.write("Details:\n")
                for entry in import_log:
                    log_file.write(f"{entry}\n")
            print(get_text("housing.accommodation.bulk.log_saved", "Import log saved to {path}").format(path=log_path))
        except Exception as log_e:
            logging.error(f"Error writing import log: {log_e}")
            print(get_text("housing.accommodation.warning.could_not_save_log", "Warning: Could not save import log: {error}").format(error=log_e))

        print(get_text("housing.accommodation.bulk.complete", "Bulk import complete. {count} records imported successfully.").format(count=success_count))
        if error_count > 0:
            print(get_text("housing.accommodation.bulk.errors", "{count} records had errors and were not imported.").format(count=error_count))
        if conflict_count > 0:
            print(get_text("housing.accommodation.bulk.conflicts", "{count} records had conflicts but were imported anyway.").format(count=conflict_count))

    except Exception as e:
        logging.error(f"Bulk import error: {e}")
        print(get_text("housing.accommodation.error.bulk_import", "Error during bulk import: {error}").format(error=e))
        print(get_text("housing.accommodation.warning.partial_complete", "Operation may be partially complete. Check logs for details."))


def save_template():
    """Save current inputs as a reusable template with improved validation."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_save_template", "You must be logged in to save templates."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_save_template", "You don't have permission to save templates."))
        return

    init_accommodation_db()
    try:
        # Get template name with validation
        while True:
            name = input(get_text("housing.accommodation.input.template_name", "Template name: ")).strip()
            if not name:
                print(get_text("housing.accommodation.error.template_name_required", "Error: Template name is required."))
                continue

            # Check if template already exists
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM [" + TEMPLATES_TABLE + "] WHERE name = ?", (name,))
                if cursor.fetchone():
                    overwrite = input(get_text("housing.accommodation.input.template_overwrite", "Template '{name}' already exists. Overwrite? (y/n): ").format(name=name))
                    if overwrite.lower() != 'y':
                        continue
            break

        # Get accommodation type
        available_types = get_accommodation_types()
        print("\n" + get_text("housing.accommodation.label.available_types", "Available accommodation types:"))
        for i, type_name in enumerate(available_types):
            print(f"{i+1}. {type_name}")

        while True:
            type_choice = input("\n" + get_text("housing.accommodation.input.select_type", "Select type (number or enter custom): ")).strip()
            if type_choice.isdigit() and 1 <= int(type_choice) <= len(available_types):
                typ = available_types[int(type_choice)-1]
                break
            elif type_choice:
                typ = type_choice
                break
            else:
                print(get_text("housing.accommodation.error.type_required", "Error: Accommodation type is required."))

        desc = input(get_text("housing.accommodation.input.description_optional", "Description [optional]: ")).strip() or None

        # Get offset days with validation
        while True:
            offset_str = input(get_text("housing.accommodation.input.start_offset_days", "Start offset days from today: ")).strip()
            try:
                offset = int(offset_str)
                if offset < 0:
                    print(get_text("housing.accommodation.error.offset_non_negative", "Error: Offset must be a non-negative number."))
                    continue
                break
            except ValueError:
                print(get_text("housing.accommodation.error.valid_number", "Error: Please enter a valid number."))

        # Get duration days with validation
        while True:
            duration_str = input(get_text("housing.accommodation.input.duration_days", "Duration days: ")).strip()
            try:
                duration = int(duration_str)
                if duration <= 0:
                    print(get_text("housing.accommodation.error.duration_positive", "Error: Duration must be a positive number."))
                    continue
                break
            except ValueError:
                print(get_text("housing.accommodation.error.valid_number", "Error: Please enter a valid number."))
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = get_current_user()
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO [" + TEMPLATES_TABLE + "]"
                " (name, accommodation_type, description, start_offset_days, duration_days, created_by, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, typ, desc, offset, duration, user, now, now))
            conn.commit()
            
        print(get_text("housing.accommodation.success.template_saved", "Template '{name}' saved successfully.").format(name=name))
        log_action('save_template', None, f"Saved template: {name} for {typ}")

    except Exception as e:
        logging.error(f"Error saving template: {e}")
        print(get_text("housing.accommodation.error.saving_template", "Error saving template: {error}").format(error=e))


def apply_template():
    """Apply a saved template to a student with improved validation and error handling."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_apply_template", "You must be logged in to apply templates."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_apply_template", "You don't have permission to apply templates."))
        return
    
    # Backup before making changes
    backup_before_operation('accommodation_apply_template')
    
    init_accommodation_db()
    try:
        # List available templates
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, accommodation_type FROM [" + TEMPLATES_TABLE + "] ORDER BY name")
            templates = cursor.fetchall()
            
        if not templates:
            print(get_text("housing.accommodation.error.no_templates", "No templates available. Please create a template first."))
            return

        print("\n" + get_text("housing.accommodation.label.available_templates", "Available templates:"))
        for i, (name, atype) in enumerate(templates):
            print(f"{i+1}. {name} ({atype})")

        # Get template selection
        while True:
            choice = input("\n" + get_text("housing.accommodation.input.select_template", "Select template (number or name): ")).strip()
            if choice.isdigit() and 1 <= int(choice) <= len(templates):
                name = templates[int(choice)-1][0]
                break
            else:
                # Check if they entered the name directly
                name = choice
                cursor.execute("SELECT COUNT(*) FROM [" + TEMPLATES_TABLE + "] WHERE name = ?", (name,))
                if cursor.fetchone()[0] > 0:
                    break
                print(get_text("housing.accommodation.error.invalid_template_selection", "Error: Invalid template selection."))

        # Get student ID with validation
        while True:
            student_id = input(get_text("housing.accommodation.input.enter_student_id", "Enter student ID: ")).strip()
            if not student_id:
                print(get_text("housing.accommodation.error.student_id_required", "Error: Student ID is required."))
                continue

            if not validate_student_id(student_id):
                print(get_text("housing.accommodation.error.student_not_found", "Error: Student ID not found in the system."))
                retry = input(get_text("housing.accommodation.input.try_again", "Would you like to try again? (y/n): "))
                if retry.lower() != 'y':
                    return
                continue
            break
        
        # Get the template details
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT accommodation_type, description, start_offset_days, duration_days"
                " FROM [" + TEMPLATES_TABLE + "] WHERE name = ?",
                (name,))
            
            template = cursor.fetchone()
            if not template:
                print(get_text("housing.accommodation.error.template_not_found", "Error: Template '{name}' not found.").format(name=name))
                return
                
            typ, desc, offset, duration = template
            
            # Calculate dates
            sd_date = datetime.now() + timedelta(days=offset)
            ed_date = sd_date + timedelta(days=duration)
            sd = sd_date.strftime('%Y-%m-%d')
            ed = ed_date.strftime('%Y-%m-%d')
            
            # Check for conflicts
            if check_conflict(student_id, typ, sd, ed):
                print(get_text("housing.accommodation.warning.overlap_existing", "Warning: This accommodation overlaps an existing record."))
                cont = input(get_text("housing.accommodation.input.continue_anyway", "Continue anyway? (y/n): "))
                if cont.lower() != 'y':
                    return
            
            # Insert accommodation
            now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            status = 'active'  # Default status
            notes = f"Applied from template: {name}"
            
            cursor.execute('''
                INSERT INTO accommodations
                (student_id, accommodation_type, description, start_date, end_date, status, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, typ, desc, sd, ed, status, notes, now_ts, now_ts))
            
            aid = cursor.lastrowid
            conn.commit()
            
        print(get_text("housing.accommodation.success.template_applied", "Template '{name}' applied successfully to student {student_id}.").format(name=name, student_id=student_id))
        log_action('apply_template', aid, f"Applied template {name} to student {student_id}")
        notify_student(student_id, 'Accommodation Template Applied', 
                      f"Template '{name}' for {typ} has been applied to your account.")
        
        # Display the added accommodation details
        view_accommodation_by_id(aid)
        
    except Exception as e:
        logging.error(f"Error applying template: {e}")
        print(get_text("housing.accommodation.error.applying_template", "Error applying template: {error}").format(error=e))


def update_accommodation():
    """Update an existing accommodation record."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_update", "You must be logged in to update accommodations."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_update", "You don't have permission to update accommodations."))
        return
    
    # Backup before making changes
    backup_before_operation('accommodation_update')
    
    init_accommodation_db()
    try:
        # Get accommodation ID
        while True:
            id_str = input(get_text("housing.accommodation.input.enter_id_to_update", "Enter accommodation ID to update: ")).strip()
            if not id_str:
                print(get_text("housing.accommodation.error.accommodation_id_required", "Error: Accommodation ID is required."))
                continue

            try:
                accommodation_id = int(id_str)
                break
            except ValueError:
                print(get_text("housing.accommodation.error.valid_id_number", "Error: Please enter a valid ID number."))
        
        # Check if accommodation exists
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM accommodations WHERE id = ?', (accommodation_id,))
            accommodation = cursor.fetchone()
            
        if not accommodation:
            print(get_text("housing.accommodation.error.not_found_id", "No accommodation found with ID {id}").format(id=accommodation_id))
            return

        # Display current accommodation
        print("\n" + get_text("housing.accommodation.label.current_details", "Current accommodation details:"))
        view_accommodation_by_id(accommodation_id)

        # Get field to update
        print("\n" + get_text("housing.accommodation.menu.which_field_update", "Which field would you like to update?"))
        print("1. " + get_text("housing.accommodation.menu.accommodation_type", "Accommodation Type"))
        print("2. " + get_text("housing.accommodation.menu.description", "Description"))
        print("3. " + get_text("housing.accommodation.menu.start_date", "Start Date"))
        print("4. " + get_text("housing.accommodation.menu.end_date", "End Date"))
        print("5. " + get_text("housing.accommodation.menu.status", "Status"))
        print("6. " + get_text("housing.accommodation.menu.notes", "Notes"))
        print("7. " + get_text("housing.accommodation.menu.cancel", "Cancel"))

        choice = input(get_text("housing.accommodation.input.enter_choice", "Enter your choice (1-7): ")).strip()

        if choice == '7':
            print(get_text("housing.accommodation.message.update_cancelled", "Update cancelled."))
            return
            
        # Initialize values with current data
        student_id = accommodation['student_id']
        accommodation_type = accommodation['accommodation_type']
        description = accommodation['description']
        start_date = accommodation['start_date']
        end_date = accommodation['end_date']
        status = accommodation['status']
        notes = accommodation['notes']
        
        # Update selected field
        if choice == '1':
            available_types = get_accommodation_types()
            print("\n" + get_text("housing.accommodation.label.available_types", "Available accommodation types:"))
            for i, type_name in enumerate(available_types):
                print(f"{i+1}. {type_name}")

            while True:
                type_choice = input("\n" + get_text("housing.accommodation.input.select_new_type", "Select new type (number or enter custom): ")).strip()
                if type_choice.isdigit() and 1 <= int(type_choice) <= len(available_types):
                    accommodation_type = available_types[int(type_choice)-1]
                    break
                elif type_choice:
                    accommodation_type = type_choice
                    break
                else:
                    print(get_text("housing.accommodation.error.type_required", "Error: Accommodation type is required."))

        elif choice == '2':
            description = input(get_text("housing.accommodation.input.enter_new_description", "Enter new description [leave blank to clear]: ")).strip() or None

        elif choice == '3':
            while True:
                start_date = input(get_text("housing.accommodation.input.enter_new_start_date", "Enter new start date (YYYY-MM-DD) [leave blank to clear]: ")).strip() or None
                if start_date:
                    valid, error = validate_date(start_date)
                    if not valid:
                        print(get_text("housing.accommodation.error.generic", "Error: {error}").format(error=error))
                        continue
                break

        elif choice == '4':
            while True:
                end_date = input(get_text("housing.accommodation.input.enter_new_end_date", "Enter new end date (YYYY-MM-DD) [leave blank to clear]: ")).strip() or None
                if end_date:
                    valid, error = validate_date(end_date)
                    if not valid:
                        print(get_text("housing.accommodation.error.generic", "Error: {error}").format(error=error))
                        continue

                    # Check that end date is after start date if start date exists
                    if start_date and end_date:
                        try:
                            start = datetime.fromisoformat(start_date)
                            end = datetime.fromisoformat(end_date)
                            if end <= start:
                                print(get_text("housing.accommodation.error.end_date_after_start", "Error: End date must be after start date."))
                                continue
                        except ValueError:
                            print(get_text("housing.accommodation.validation.invalid_date_format", "Invalid date format. Please use YYYY-MM-DD format."))
                            continue
                break

        elif choice == '5':
            print("\n" + get_text("housing.accommodation.label.available_statuses", "Available statuses:"))
            print("1. " + get_text("housing.accommodation.status.active", "active"))
            print("2. " + get_text("housing.accommodation.status.pending", "pending"))
            print("3. " + get_text("housing.accommodation.status.suspended", "suspended"))
            print("4. " + get_text("housing.accommodation.status.expired", "expired"))

            while True:
                status_choice = input(get_text("housing.accommodation.input.select_new_status", "Select new status (1-4): ")).strip()
                if status_choice == '1':
                    status = 'active'
                    break
                elif status_choice == '2':
                    status = 'pending'
                    break
                elif status_choice == '3':
                    status = 'suspended'
                    break
                elif status_choice == '4':
                    status = 'expired'
                    break
                else:
                    print(get_text("housing.accommodation.error.invalid_selection", "Error: Invalid selection."))

        elif choice == '6':
            notes = input(get_text("housing.accommodation.input.enter_new_notes", "Enter new notes [leave blank to clear]: ")).strip() or None

        else:
            print(get_text("housing.accommodation.error.invalid_choice_cancelled", "Invalid choice. Update cancelled."))
            return
        
        # Check for conflicts if dates or type changed
        if start_date != accommodation['start_date'] or end_date != accommodation['end_date'] or accommodation_type != accommodation['accommodation_type']:
            if check_conflict(student_id, accommodation_type, start_date, end_date, excluded_id=accommodation_id):
                print(get_text("housing.accommodation.warning.update_conflict", "Warning: This update creates a conflict with an existing accommodation."))
                cont = input(get_text("housing.accommodation.input.continue_anyway", "Continue anyway? (y/n): "))
                if cont.lower() != 'y':
                    return
        
        # Update the accommodation record
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE accommodations SET
                    accommodation_type = ?,
                    description = ?,
                    start_date = ?,
                    end_date = ?,
                    status = ?,
                    notes = ?,
                    updated_at = ?
                    WHERE id = ?
                ''', (accommodation_type, description, start_date, end_date, status, notes, now, accommodation_id))
                conn.commit()
                
            print(get_text("housing.accommodation.success.updated", "Accommodation updated successfully."))
            log_action('update', accommodation_id, f"Updated accommodation for student {student_id}")
            
            # Notify student
            notify_student(student_id, 'Accommodation Updated', 
                          f"Your {accommodation_type} accommodation has been updated.")
            
            # Display updated record
            view_accommodation_by_id(accommodation_id)
            
        except Exception as update_e:
            logging.error(f"Error updating accommodation {accommodation_id}: {update_e}")
            print(get_text("housing.accommodation.error.updating", "Error updating accommodation: {error}").format(error=update_e))

    except Exception as e:
        logging.error(f"Error in update_accommodation: {e}")
        print(get_text("housing.accommodation.error.updating", "Error updating accommodation: {error}").format(error=e))


def remove_accommodation():
    """Remove an accommodation record with validation and confirmation."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_remove", "You must be logged in to remove accommodations."))
        return

    if not auth.check_permission('manage_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_remove", "You don't have permission to remove accommodations."))
        return
    
    # Backup before making changes
    backup_before_operation('accommodation_remove')
    
    init_accommodation_db()
    try:
        # Get accommodation ID
        while True:
            id_str = input(get_text("housing.accommodation.input.enter_id_to_remove", "Enter accommodation ID to remove: ")).strip()
            if not id_str:
                print(get_text("housing.accommodation.error.accommodation_id_required", "Error: Accommodation ID is required."))
                continue

            try:
                accommodation_id = int(id_str)
                break
            except ValueError:
                print(get_text("housing.accommodation.error.valid_id_number", "Error: Please enter a valid ID number."))

        # Check if accommodation exists and get student info
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT student_id, accommodation_type FROM accommodations WHERE id = ?', (accommodation_id,))
            accommodation = cursor.fetchone()

        if not accommodation:
            print(get_text("housing.accommodation.error.not_found_id", "No accommodation found with ID {id}").format(id=accommodation_id))
            return

        # Display accommodation for confirmation
        view_accommodation_by_id(accommodation_id)

        # Confirm removal
        confirm = input("\n" + get_text("housing.accommodation.input.confirm_remove", "Are you sure you want to remove this accommodation? (y/n): ")).strip().lower()
        if confirm != 'y':
            print(get_text("housing.accommodation.message.removal_cancelled", "Removal cancelled."))
            return

        # Ask for removal reason
        reason = input(get_text("housing.accommodation.input.removal_reason", "Please enter a reason for removal [optional]: ")).strip() or get_text("housing.accommodation.label.not_specified", "Not specified")

        # Soft delete or hard delete option
        delete_type = input(get_text("housing.accommodation.input.delete_or_expire", "Permanently delete or mark as expired? (1=delete/2=expire): ")).strip()
        
        if delete_type == '2':
            # Soft delete - mark as expired
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE accommodations SET
                    status = 'expired',
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (f"Expired: {reason}", f"Expired: {reason}", now, accommodation_id))
                conn.commit()

            print(get_text("housing.accommodation.success.marked_expired", "Accommodation marked as expired."))

        else:
            # Hard delete - remove from database
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # First remove any associated documents
                cursor.execute('DELETE FROM accommodation_documents WHERE accommodation_id = ?', (accommodation_id,))

                # Then remove the accommodation record
                cursor.execute('DELETE FROM accommodations WHERE id = ?', (accommodation_id,))
                conn.commit()

            print(get_text("housing.accommodation.success.permanently_deleted", "Accommodation permanently deleted."))
        
        # Log the action
        student_id = accommodation['student_id']
        accommodation_type = accommodation['accommodation_type']
        log_action('remove', accommodation_id, f"Removed {accommodation_type} for student {student_id}. Reason: {reason}")
        
        # Notify student
        notify_student(student_id, 'Accommodation Removed', 
                      f"Your {accommodation_type} accommodation has been removed. Reason: {reason}")
        
    except Exception as e:
        logging.error(f"Error removing accommodation: {e}")
        print(get_text("housing.accommodation.error.removing", "Error removing accommodation: {error}").format(error=e))


def view_students_by_accommodation():
    """View all students with a specific accommodation type."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_view_reports", "You must be logged in to view accommodation reports."))
        return

    if not auth.check_permission('view_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_view_reports", "You don't have permission to view accommodation reports."))
        return
    
    init_accommodation_db()
    try:
        # Get available accommodation types
        available_types = get_accommodation_types()
        print("\n" + get_text("housing.accommodation.label.available_types", "Available accommodation types:"))
        for i, type_name in enumerate(available_types):
            print(f"{i+1}. {type_name}")

        # Get accommodation type selection
        while True:
            type_choice = input("\n" + get_text("housing.accommodation.input.select_type_to_view", "Select type to view (number or enter name): ")).strip()
            if type_choice.isdigit() and 1 <= int(type_choice) <= len(available_types):
                accommodation_type = available_types[int(type_choice)-1]
                break
            elif type_choice:
                accommodation_type = type_choice
                break
            else:
                print(get_text("housing.accommodation.error.select_type", "Error: Please select an accommodation type."))

        # Get optional status filter
        print("\n" + get_text("housing.accommodation.label.filter_by_status", "Filter by status (leave blank for all):"))
        print("1. " + get_text("housing.accommodation.status.active", "active"))
        print("2. " + get_text("housing.accommodation.status.pending", "pending"))
        print("3. " + get_text("housing.accommodation.status.suspended", "suspended"))
        print("4. " + get_text("housing.accommodation.status.expired", "expired"))

        status_filter = None
        status_choice = input(get_text("housing.accommodation.input.select_status_filter", "Select status filter (1-4 or blank): ")).strip()
        if status_choice == '1':
            status_filter = 'active'
        elif status_choice == '2':
            status_filter = 'pending'
        elif status_choice == '3':
            status_filter = 'suspended'
        elif status_choice == '4':
            status_filter = 'expired'
        
        # Query database
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = '''
                SELECT a.*, s.first_name, s.last_name, s.email_address
                FROM accommodations a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.accommodation_type = ?
            '''
            params = [accommodation_type]
            
            if status_filter:
                query += " AND a.status = ?"
                params.append(status_filter)
                
            query += " ORDER BY a.start_date DESC"
            
            cursor.execute(query, params)
            accommodations = cursor.fetchall()
            
        # Display results
        if not accommodations:
            print(get_text("housing.accommodation.message.no_students_found_type", "No students found with {type} accommodation.").format(type=accommodation_type))
            return

        status_text = get_text("housing.accommodation.label.with_status", " with status '{status}'").format(status=status_filter) if status_filter else ""
        print("\n" + get_text("housing.accommodation.message.students_with_type", "Students with {type} accommodation{status}:").format(type=accommodation_type, status=status_text))
        print("=" * 80)
        print(f"{get_text('housing.accommodation.table.id', 'ID'):<5} {get_text('housing.accommodation.table.student_id', 'Student ID'):<10} {get_text('housing.accommodation.table.name', 'Name'):<25} {get_text('housing.accommodation.table.start_date', 'Start Date'):<12} {get_text('housing.accommodation.table.end_date', 'End Date'):<12} {get_text('housing.accommodation.table.status', 'Status'):<10}")
        print("-" * 80)

        for acc in accommodations:
            name = f"{acc['first_name']} {acc['last_name']}"
            start_date = acc['start_date'] or get_text("housing.accommodation.label.na", "N/A")
            end_date = acc['end_date'] or get_text("housing.accommodation.label.na", "N/A")
            print(f"{acc['id']:<5} {acc['student_id']:<10} {name:<25} {start_date:<12} {end_date:<12} {acc['status']:<10}")

        print("=" * 80)
        print(get_text("housing.accommodation.message.total_records", "Total: {count} record(s)").format(count=len(accommodations)))

        # Offer detailed view option
        detail_view = input("\n" + get_text("housing.accommodation.input.enter_id_for_details", "Enter accommodation ID to view details (or press Enter to return): ")).strip()
        if detail_view.isdigit():
            view_accommodation_by_id(int(detail_view))

    except Exception as e:
        logging.error(f"Error viewing students by accommodation: {e}")
        print(get_text("housing.accommodation.error.viewing_students_by_type", "Error viewing students by accommodation: {error}").format(error=e))


def view_accommodations():
    """Rich search and filters, integrating student profiles."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_view", "You must be logged in to view accommodations."))
        return

    if not auth.check_permission('view_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_view", "You don't have permission to view accommodations."))
        return
    
    init_accommodation_db()
    try:
        print(get_text("housing.accommodation.filter.options", "Filter options:"))
        print("1) " + get_text("housing.accommodation.filter.all", "All accommodations"))
        print("2) " + get_text("housing.accommodation.filter.by_student", "By student"))
        print("3) " + get_text("housing.accommodation.filter.by_type", "By accommodation type"))
        print("4) " + get_text("housing.accommodation.filter.active", "Active accommodations"))
        print("5) " + get_text("housing.accommodation.filter.expired", "Expired accommodations"))
        print("6) " + get_text("housing.accommodation.filter.date_range", "Date range"))
        print("7) " + get_text("housing.accommodation.filter.keyword_search", "Keyword search in description"))
        print("8) " + get_text("housing.accommodation.filter.by_status", "By status (active/pending/suspended/expired)"))
        print("9) " + get_text("housing.accommodation.filter.recently_added", "Recently added"))
        print("10) " + get_text("housing.accommodation.filter.recently_updated", "Recently updated"))

        choice = input("\n" + get_text("housing.accommodation.input.choose_filter", "Choose filter (1-10): ")).strip()
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            base_query = '''
                SELECT a.id, a.student_id, a.accommodation_type, a.description, 
                       a.start_date, a.end_date, a.status, a.created_at, a.updated_at,
                       s.first_name, s.last_name, s.email_address
                FROM accommodations a 
                LEFT JOIN students s ON a.student_id = s.student_id
            '''
            
            where_clauses = []
            params = []
            
            if choice == '2':
                student_id = input(get_text("housing.accommodation.input.enter_student_id", "Enter student ID: ")).strip()
                where_clauses.append('a.student_id = ?')
                params.append(student_id)

            elif choice == '3':
                available_types = get_accommodation_types()
                print("\n" + get_text("housing.accommodation.label.available_types", "Available accommodation types:"))
                for i, type_name in enumerate(available_types):
                    print(f"{i+1}. {type_name}")

                type_choice = input("\n" + get_text("housing.accommodation.input.select_type", "Select type (number or enter custom): ")).strip()
                if type_choice.isdigit() and 1 <= int(type_choice) <= len(available_types):
                    accommodation_type = available_types[int(type_choice)-1]
                else:
                    accommodation_type = type_choice
                    
                where_clauses.append('a.accommodation_type = ?')
                params.append(accommodation_type)
                
            elif choice == '4':
                today = datetime.now().strftime('%Y-%m-%d')
                where_clauses.append("(a.end_date >= ? OR a.end_date IS NULL) AND a.status = 'active'")
                params.append(today)
                
            elif choice == '5':
                today = datetime.now().strftime('%Y-%m-%d')
                where_clauses.append("(a.end_date < ? OR a.status = 'expired')")
                params.append(today)
                
            elif choice == '6':
                start_date = input(get_text("housing.accommodation.input.start_date_gte", "Start date >= (YYYY-MM-DD): ")).strip()
                end_date = input(get_text("housing.accommodation.input.end_date_lte", "End date <= (YYYY-MM-DD): ")).strip()
                valid_start, error_start = validate_date(start_date)
                valid_end, error_end = validate_date(end_date)

                if not valid_start:
                    print(get_text("housing.accommodation.error.with_start_date", "Error with start date: {error}").format(error=error_start))
                    return
                if not valid_end:
                    print(get_text("housing.accommodation.error.with_end_date", "Error with end date: {error}").format(error=error_end))
                    return
                    
                where_clauses.append('a.start_date >= ? AND a.end_date <= ?')
                params.extend([start_date, end_date])
                
            elif choice == '7':
                keyword = input(get_text("housing.accommodation.input.enter_keyword", "Enter keyword: ")).strip()
                where_clauses.append('(a.description LIKE ? OR a.notes LIKE ?)')
                params.extend([f'%{keyword}%', f'%{keyword}%'])

            elif choice == '8':
                print("\n" + get_text("housing.accommodation.label.select_status", "Select status:"))
                print("1. " + get_text("housing.accommodation.status.active", "active"))
                print("2. " + get_text("housing.accommodation.status.pending", "pending"))
                print("3. " + get_text("housing.accommodation.status.suspended", "suspended"))
                print("4. " + get_text("housing.accommodation.status.expired", "expired"))

                status_choice = input(get_text("housing.accommodation.input.enter_choice_1_4", "Enter choice (1-4): ")).strip()
                if status_choice == '1':
                    status = 'active'
                elif status_choice == '2':
                    status = 'pending'
                elif status_choice == '3':
                    status = 'suspended'
                elif status_choice == '4':
                    status = 'expired'
                else:
                    print(get_text("housing.accommodation.error.invalid_status_choice", "Invalid status choice."))
                    return
                    
                where_clauses.append('a.status = ?')
                params.append(status)
                
            elif choice == '9':
                days = input(get_text("housing.accommodation.input.show_added_last_days", "Show accommodations added in the last X days (default 30): ")).strip()
                if not days:
                    days = 30
                try:
                    days = int(days)
                    if days <= 0:
                        raise ValueError
                except ValueError:
                    print(get_text("housing.accommodation.error.positive_number", "Error: Please enter a positive number."))
                    return
                    
                date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                where_clauses.append('a.created_at >= ?')
                params.append(date_limit)
                
            elif choice == '10':
                days = input(get_text("housing.accommodation.input.show_updated_last_days", "Show accommodations updated in the last X days (default 30): ")).strip()
                if not days:
                    days = 30
                try:
                    days = int(days)
                    if days <= 0:
                        raise ValueError
                except ValueError:
                    print(get_text("housing.accommodation.error.positive_number", "Error: Please enter a positive number."))
                    return
                    
                date_limit = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                where_clauses.append('a.updated_at >= ?')
                params.append(date_limit)
            
            # Construct and execute the query
            query = base_query
            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)
                
            # Add sort options
            print("\n" + get_text("housing.accommodation.label.sort_by", "Sort by:"))
            print("1. " + get_text("housing.accommodation.sort.start_date_newest", "Start date (newest first)"))
            print("2. " + get_text("housing.accommodation.sort.end_date_soonest", "End date (soonest first)"))
            print("3. " + get_text("housing.accommodation.sort.student_id", "Student ID"))
            print("4. " + get_text("housing.accommodation.sort.accommodation_type", "Accommodation type"))

            sort_choice = input(get_text("housing.accommodation.input.select_sort", "Select sort option (1-4): ")).strip()
            if sort_choice == '1':
                query += ' ORDER BY a.start_date DESC'
            elif sort_choice == '2':
                query += ' ORDER BY a.end_date ASC'
            elif sort_choice == '3':
                query += ' ORDER BY a.student_id'
            elif sort_choice == '4':
                query += ' ORDER BY a.accommodation_type'
            else:
                query += ' ORDER BY a.id DESC'  # Default sort
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
        if not rows:
            print(get_text("housing.accommodation.message.no_records_matching", "No records found matching your criteria."))
            return

        # Display results
        print("\n" + get_text("housing.accommodation.message.found_records", "Found {count} record(s):").format(count=len(rows)))
        print("=" * 100)
        print(f"{get_text('housing.accommodation.table.id', 'ID'):<5} {get_text('housing.accommodation.table.student', 'Student'):<10} {get_text('housing.accommodation.table.type', 'Type'):<20} {get_text('housing.accommodation.table.start_date', 'Start Date'):<12} {get_text('housing.accommodation.table.end_date', 'End Date'):<12} {get_text('housing.accommodation.table.status', 'Status'):<10} {get_text('housing.accommodation.table.name', 'Name'):<25}")
        print("-" * 100)

        for row in rows:
            student_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or get_text("housing.accommodation.label.na", "N/A")
            start_date = row['start_date'] or get_text("housing.accommodation.label.na", "N/A")
            end_date = row['end_date'] or get_text("housing.accommodation.label.na", "N/A")

            print(f"{row['id']:<5} {row['student_id']:<10} {row['accommodation_type'][:20]:<20} "
                  f"{start_date:<12} {end_date:<12} {row['status']:<10} {student_name[:25]:<25}")

        print("=" * 100)

        # Offer detailed view option
        while True:
            detail_view = input("\n" + get_text("housing.accommodation.input.enter_id_for_details", "Enter accommodation ID to view details (or press Enter to return): ")).strip()
            if not detail_view:
                break

            try:
                acc_id = int(detail_view)
                view_accommodation_by_id(acc_id)
            except ValueError:
                print(get_text("housing.accommodation.error.valid_id_number", "Error: Please enter a valid ID number."))

    except Exception as e:
        logging.error(f"Error in view_accommodations: {e}")
        print(get_text("housing.accommodation.error.viewing_accommodations", "Error viewing accommodations: {error}").format(error=e))


def notify_student(student_id, subject, message):
    """Send an email notification to the student with improved handling."""
    try:
        # Skip if email manager is not available
        if not email_manager:
            logging.info(f"Notification to {student_id}: {subject} -- {message}")
            print(get_text("housing.accommodation.message.email_would_be_sent", "Email would be sent to student {student_id}: {subject}").format(student_id=student_id, subject=subject))
            return

        # Get student email
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (student_id,))
            row = cursor.fetchone()

        if not row:
            logging.warning(f"Cannot notify student {student_id}: Student not found")
            print(get_text("housing.accommodation.warning.student_not_found", "Warning: Student {student_id} not found").format(student_id=student_id))
            return

        email_address = row[0] if row else None
        if not email_address:
            logging.warning(f"Cannot notify student {student_id}: No email address found")
            print(get_text("housing.accommodation.warning.cannot_send_email_no_address", "Warning: Cannot send email to student {student_id}: No email address found").format(student_id=student_id))
            return

        # Send email - catch any exceptions from the email service
        try:
            email_manager.send_email(email_address, subject, message)
            logging.info(f"Email sent to {student_id} ({email_address}): {subject}")
            print(get_text("housing.accommodation.message.email_sent", "Email sent to student {student_id}").format(student_id=student_id))
        except AttributeError as e:
            # Handle case where email_manager doesn't have send_email method
            logging.error(f"Email manager misconfigured: {e}")
            print(get_text("housing.accommodation.error.email_service_error", "Error: Email service not properly configured"))
        except (KeyError, TypeError) as e:
            # Handle case where email configuration or parameters are incorrect
            logging.error(f"Email configuration error for {student_id}: {e}")
            print(get_text("housing.accommodation.error.email_config_error", "Error: Email configuration problem: {error}").format(error=e))

    except sqlite3.Error as e:
        logging.error(f"Database error while notifying student {student_id}: {e}")
        print(get_text("housing.accommodation.error.database_error_notification", "Database error while sending notification: {error}").format(error=e))
    except Exception as e:
        logging.error(f"Error notifying student {student_id}: {e}")
        print(get_text("housing.accommodation.error.sending_notification", "Error sending notification to student {student_id}: {error}").format(student_id=student_id, error=e))


def check_expiry_notifications(days=NOTIFICATION_THRESHOLD_DAYS):
    """Alert for accommodations nearing expiry with improved error handling."""
    auth = get_auth()

    # Check for permission if called interactively
    if auth is not None:
        if not auth.current_user:
            print(get_text("housing.accommodation.auth.must_be_logged_in_check_expiry", "You must be logged in to check expirations."))
            return

        if not auth.check_permission('manage_accommodations'):
            print(get_text("housing.accommodation.auth.no_permission_check_expiry", "You don't have permission to check expirations."))
            return
    
    init_accommodation_db()
    try:
        # Calculate threshold date for expirations
        threshold = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Find active accommodations expiring on the threshold date
            cursor.execute('''
                SELECT a.id, a.student_id, a.accommodation_type, a.end_date, 
                       s.first_name, s.last_name, s.email_address
                FROM accommodations a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.end_date = ? AND a.status = 'active'
            ''', (threshold,))
            
            expiring_soon = cursor.fetchall()
            
            # Find accommodations that expired today but still have active status
            cursor.execute('''
                SELECT a.id, a.student_id, a.accommodation_type, a.end_date,
                       s.first_name, s.last_name, s.email_address
                FROM accommodations a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.end_date = ? AND a.status = 'active'
            ''', (today,))
            
            expired_today = cursor.fetchall()
        
        # Process accommodations expiring soon
        if expiring_soon:
            print("\n" + get_text("housing.accommodation.message.found_expiring_in_days", "Found {count} accommodation(s) expiring in {days} days:").format(count=len(expiring_soon), days=days))

            for acc in expiring_soon:
                student_id = acc['student_id']
                name = f"{acc['first_name'] or ''} {acc['last_name'] or ''}".strip() or get_text("housing.accommodation.label.na", "N/A")

                print(get_text("housing.accommodation.message.expiry_record", "ID: {id} - Student: {student_id} ({name}) - Type: {type}").format(
                    id=acc['id'], student_id=student_id, name=name, type=acc['accommodation_type']))
                
                try:
                    # Send notification
                    msg = f"Your accommodation '{acc['accommodation_type']}' will expire on {acc['end_date']}. Please contact the accommodations office if you need to renew it."
                    notify_student(student_id, 'Accommodation Expiry Warning', msg)
                    
                    # Log the notification
                    log_action('expiry_notification', acc['id'], f"Expiry notification for {acc['accommodation_type']}")
                    
                except Exception as notify_e:
                    logging.error(f"Expiry notification error for {acc['id']}: {notify_e}")
                    print(get_text("housing.accommodation.error.sending_notification_for", "Error sending notification for accommodation {id}: {error}").format(id=acc['id'], error=notify_e))
        else:
            print(get_text("housing.accommodation.message.no_expiring_in_days", "No accommodations found expiring in {days} days.").format(days=days))

        # Process accommodations expired today
        if expired_today:
            print("\n" + get_text("housing.accommodation.message.found_expired_today", "Found {count} accommodation(s) expired today:").format(count=len(expired_today)))

            for acc in expired_today:
                student_id = acc['student_id']
                name = f"{acc['first_name'] or ''} {acc['last_name'] or ''}".strip() or get_text("housing.accommodation.label.na", "N/A")

                print(get_text("housing.accommodation.message.expiry_record", "ID: {id} - Student: {student_id} ({name}) - Type: {type}").format(
                    id=acc['id'], student_id=student_id, name=name, type=acc['accommodation_type']))
                
                try:
                    # Send notification
                    msg = f"Your accommodation '{acc['accommodation_type']}' has expired today ({acc['end_date']}). Please contact the accommodations office if you need to extend it."
                    notify_student(student_id, 'Accommodation Expired', msg)
                    
                    # Update status to expired
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE accommodations
                            SET status = 'expired', updated_at = ?
                            WHERE id = ?
                        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), acc['id']))
                        conn.commit()
                    
                    # Log the expiration
                    log_action('expired', acc['id'], f"Accommodation {acc['accommodation_type']} expired")
                    
                except Exception as expire_e:
                    logging.error(f"Expiration processing error for {acc['id']}: {expire_e}")
                    print(get_text("housing.accommodation.error.processing_expiration", "Error processing expiration for accommodation {id}: {error}").format(id=acc['id'], error=expire_e))
        else:
            print(get_text("housing.accommodation.message.no_expired_today", "No accommodations expired today."))

    except Exception as e:
        logging.error(f"Error checking expiry notifications: {e}")
        print(get_text("housing.accommodation.error.checking_expiry", "Error checking expiry notifications: {error}").format(error=e))


def export_accommodations():
    """Export accommodation data to various formats."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_export", "You must be logged in to export accommodations."))
        return

    if not auth.check_permission('export_data'):
        print(get_text("housing.accommodation.auth.no_permission_export", "You don't have permission to export accommodations."))
        return
    
    init_accommodation_db()
    try:
        # Get export format
        print(get_text("housing.accommodation.export.choose_format", "Choose export format:"))
        print("1. CSV")
        print("2. Excel")
        print("3. PDF")
        print("4. JSON")
        print("5. " + get_text("housing.accommodation.menu.cancel", "Cancel"))

        format_choice = input(get_text("housing.accommodation.input.enter_choice_1_5", "Enter choice (1-5): ")).strip()
        if format_choice == '5':
            print(get_text("housing.accommodation.message.export_cancelled", "Export cancelled."))
            return

        # Get export filters
        print("\n" + get_text("housing.accommodation.export.filters", "Export filters (leave blank for all records):"))
        student_id = input(get_text("housing.accommodation.input.student_id_optional", "Student ID (optional): ")).strip() or None
        acc_type = input(get_text("housing.accommodation.input.type_optional", "Accommodation type (optional): ")).strip() or None
        status = input(get_text("housing.accommodation.input.status_optional", "Status (active/pending/suspended/expired) (optional): ")).strip() or None
        
        # Build query based on filters
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = '''
                SELECT a.*, s.first_name, s.last_name, s.email_address
                FROM accommodations a
                LEFT JOIN students s ON a.student_id = s.student_id
            '''
            
            where_clauses = []
            params = []
            
            if student_id:
                where_clauses.append('a.student_id = ?')
                params.append(student_id)
                
            if acc_type:
                where_clauses.append('a.accommodation_type = ?')
                params.append(acc_type)
                
            if status:
                where_clauses.append('a.status = ?')
                params.append(status)
                
            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)
                
            query += ' ORDER BY a.id'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
        if not rows:
            print(get_text("housing.accommodation.message.no_records_matching", "No records found matching your criteria."))
            return

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_base = f"accommodation_export_{timestamp}"

        # Export based on selected format
        if format_choice == '1':  # CSV
            filename = filename_base + ".csv"
            export_to_csv(rows, filename)
        elif format_choice == '2':  # Excel
            if not pd:
                print(get_text("housing.accommodation.error.pandas_not_installed", "Error: pandas module not installed. Cannot export to Excel."))
                return
            filename = filename_base + ".xlsx"
            export_to_excel(rows, filename)
        elif format_choice == '3':  # PDF
            if not canvas:
                print(get_text("housing.accommodation.error.reportlab_not_installed", "Error: reportlab module not installed. Cannot export to PDF."))
                return
            filename = filename_base + ".pdf"
            export_to_pdf(rows, filename)
        elif format_choice == '4':  # JSON
            filename = filename_base + ".json"
            export_to_json(rows, filename)
        else:
            print(get_text("housing.accommodation.error.invalid_format_choice", "Invalid format choice."))
            return

    except Exception as e:
        logging.error(f"Error exporting accommodations: {e}")
        print(get_text("housing.accommodation.error.exporting", "Error exporting accommodations: {error}").format(error=e))


def export_to_csv(rows, filename):
    """Export accommodation data to CSV file."""
    try:
        # Get save location
        path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
        if path:
            full_path = os.path.join(path, filename)
        else:
            full_path = filename
            
        # Ensure directory exists
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        # Extract data and write to CSV
        with open(full_path, 'w', newline='') as csvfile:
            headers = [
                'ID', 'Student ID', 'Student Name', 'Email', 'Accommodation Type',
                'Description', 'Start Date', 'End Date', 'Status', 'Notes',
                'Created At', 'Updated At'
            ]
            
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            
            for row in rows:
                student_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or 'N/A'
                writer.writerow([
                    row['id'],
                    row['student_id'],
                    student_name,
                    row['email_address'] or 'N/A',
                    row['accommodation_type'],
                    row['description'] or '',
                    row['start_date'] or '',
                    row['end_date'] or '',
                    row['status'],
                    row['notes'] or '',
                    row['created_at'],
                    row['updated_at']
                ])
                
        print(get_text("housing.accommodation.success.data_exported", "Data exported to {path}").format(path=full_path))
    except Exception as e:
        logging.error(f"Error exporting to CSV: {e}")
        print(get_text("housing.accommodation.error.exporting_csv", "Error exporting to CSV: {error}").format(error=e))


def export_to_excel(rows, filename):
    """Export accommodation data to Excel file."""
    try:
        # Check for pandas
        if not pd:
            print(get_text("housing.accommodation.error.pandas_not_installed", "Error: pandas module not installed. Cannot export to Excel."))
            return

        # Get save location
        path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
        if path:
            full_path = os.path.join(path, filename)
        else:
            full_path = filename
            
        # Ensure directory exists
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        # Convert data to DataFrame
        data = []
        for row in rows:
            student_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or 'N/A'
            data.append({
                'ID': row['id'],
                'Student ID': row['student_id'],
                'Student Name': student_name,
                'Email': row['email_address'] or 'N/A',
                'Accommodation Type': row['accommodation_type'],
                'Description': row['description'] or '',
                'Start Date': row['start_date'] or '',
                'End Date': row['end_date'] or '',
                'Status': row['status'],
                'Notes': row['notes'] or '',
                'Created At': row['created_at'],
                'Updated At': row['updated_at']
            })
            
        df = pd.DataFrame(data)
        
        # Write to Excel
        with pd.ExcelWriter(full_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Accommodations', index=False)

        print(get_text("housing.accommodation.success.data_exported", "Data exported to {path}").format(path=full_path))
    except Exception as e:
        logging.error(f"Error exporting to Excel: {e}")
        print(get_text("housing.accommodation.error.exporting_excel", "Error exporting to Excel: {error}").format(error=e))


def export_to_pdf(rows, filename):
    """Export accommodation data to PDF file."""
    try:
        # Check for reportlab
        if not canvas:
            print(get_text("housing.accommodation.error.reportlab_not_installed", "Error: reportlab module not installed. Cannot export to PDF."))
            return

        # Get save location
        path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
        if path:
            full_path = os.path.join(path, filename)
        else:
            full_path = filename
            
        # Ensure directory exists
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        # Create PDF document
        doc = SimpleDocTemplate(full_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Add title
        title = Paragraph("Accommodation Records", styles['Title'])
        elements.append(title)
        
        # Add timestamp
        timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
        elements.append(timestamp)
        elements.append(Paragraph("<br/>", styles['Normal']))
        
        # Add summary
        elements.append(Paragraph(f"Total Records: {len(rows)}", styles['Heading2']))
        elements.append(Paragraph("<br/>", styles['Normal']))
        
        # Add table data
        table_data = [['ID', 'Student', 'Accommodation Type', 'Dates', 'Status']]
        
        for row in rows:
            student_name = f"{row['student_id']} - {row['first_name'] or ''} {row['last_name'] or ''}".strip()
            dates = f"Start: {row['start_date'] or 'N/A'}\nEnd: {row['end_date'] or 'N/A'}"
            
            table_data.append([
                str(row['id']),
                student_name,
                row['accommodation_type'],
                dates,
                row['status']
            ])
            
        # Create table
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        elements.append(Paragraph("<br/><br/>", styles['Normal']))
        
        # Add detailed records
        elements.append(Paragraph("Detailed Records", styles['Heading2']))
        
        for row in rows:
            student_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or 'N/A'
            
            elements.append(Paragraph(f"<br/><b>Record ID: {row['id']}</b>", styles['Normal']))
            elements.append(Paragraph(f"Student: {row['student_id']} - {student_name}", styles['Normal']))
            elements.append(Paragraph(f"Type: {row['accommodation_type']}", styles['Normal']))
            elements.append(Paragraph(f"Description: {row['description'] or 'N/A'}", styles['Normal']))
            elements.append(Paragraph(f"Start Date: {row['start_date'] or 'N/A'}", styles['Normal']))
            elements.append(Paragraph(f"End Date: {row['end_date'] or 'N/A'}", styles['Normal']))
            elements.append(Paragraph(f"Status: {row['status']}", styles['Normal']))
            
            if row['notes']:
                elements.append(Paragraph(f"Notes: {row['notes']}", styles['Normal']))
                
            elements.append(Paragraph(f"Created: {row['created_at']}", styles['Normal']))
            elements.append(Paragraph(f"Updated: {row['updated_at']}", styles['Normal']))
            elements.append(Paragraph("<br/>", styles['Normal']))
            
        # Build the PDF
        doc.build(elements)
        print(get_text("housing.accommodation.success.data_exported", "Data exported to {path}").format(path=full_path))

    except Exception as e:
        logging.error(f"Error exporting to PDF: {e}")
        print(get_text("housing.accommodation.error.exporting_pdf", "Error exporting to PDF: {error}").format(error=e))


def export_to_json(rows, filename):
    """Export accommodation data to JSON file."""
    try:
        # Get save location
        path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
        if path:
            full_path = os.path.join(path, filename)
        else:
            full_path = filename
            
        # Ensure directory exists
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        # Convert to list of dictionaries
        data = []
        for row in rows:
            data.append({
                'id': row['id'],
                'student_id': row['student_id'],
                'student_name': f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or None,
                'email': row['email_address'],
                'accommodation_type': row['accommodation_type'],
                'description': row['description'],
                'start_date': row['start_date'],
                'end_date': row['end_date'],
                'status': row['status'],
                'notes': row['notes'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
            
        # Write to JSON file
        with open(full_path, 'w') as json_file:
            json.dump(data, json_file, indent=2)

        print(get_text("housing.accommodation.success.data_exported", "Data exported to {path}").format(path=full_path))
    except Exception as e:
        logging.error(f"Error exporting to JSON: {e}")
        print(get_text("housing.accommodation.error.exporting_json", "Error exporting to JSON: {error}").format(error=e))


def show_dashboard_metrics():
    """Display summary metrics for dashboard with improved visualizations."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_dashboard", "You must be logged in to view dashboard metrics."))
        return

    if not auth.check_permission('view_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_dashboard", "You don't have permission to view dashboard metrics."))
        return
    
    init_accommodation_db()
    try:
        # Current date for active/expired calculations
        today = datetime.now().strftime('%Y-%m-%d')
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get counts by accommodation type
            cursor.execute('''
                SELECT accommodation_type, COUNT(*) as count
                FROM accommodations
                GROUP BY accommodation_type
                ORDER BY count DESC
            ''')
            by_type = cursor.fetchall()
            
            # Get counts by status
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM accommodations
                GROUP BY status
                ORDER BY count DESC
            ''')
            by_status = cursor.fetchall()
            
            # Count recently added accommodations (last 30 days)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE created_at >= ?
            ''', (thirty_days_ago,))
            recent_count = cursor.fetchone()[0]
            
            # Count active accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE (end_date >= ? OR end_date IS NULL) AND status = 'active'
            ''', (today,))
            active_count = cursor.fetchone()[0]
            
            # Count expired accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE (end_date < ? OR status = 'expired')
            ''', (today,))
            expired_count = cursor.fetchone()[0]
            
            # Count pending accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE status = 'pending'
            ''')
            pending_count = cursor.fetchone()[0]
            
            # Count expiring soon (next 30 days)
            thirty_days_future = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE end_date BETWEEN ? AND ? AND status = 'active'
            ''', (today, thirty_days_future))
            expiring_soon = cursor.fetchone()[0]
            
            # Get total count
            cursor.execute('SELECT COUNT(*) FROM accommodations')
            total = cursor.fetchone()[0]
            
        # Display dashboard metrics
        print("\n" + "="*50)
        print(" "*15 + "ACCOMMODATION DASHBOARD")
        print("="*50)
        
        print("\nOVERVIEW:")
        print(f"Total Records: {total}")
        print(f"Active: {active_count} ({(active_count/total*100) if total > 0 else 0:.1f}%)")
        print(f"Expired: {expired_count} ({(expired_count/total*100) if total > 0 else 0:.1f}%)")
        print(f"Pending Approval: {pending_count} ({(pending_count/total*100) if total > 0 else 0:.1f}%)")
        print(f"Added in Last 30 Days: {recent_count}")
        print(f"Expiring in Next 30 Days: {expiring_soon}")
        
        print("\nBREAKDOWN BY TYPE:")
        print("-"*50)
        print(f"{'Type':<25} {'Count':<10} {'Percentage':<15}")
        print("-"*50)
        
        for type_row in by_type:
            type_name = type_row['accommodation_type']
            count = type_row['count']
            percent = (count/total*100) if total > 0 else 0
            
            # Create simple bar chart
            bar_length = int(percent / 2)  # Scale to max 50 chars
            bar = '█' * bar_length
            
            print(f"{type_name[:25]:<25} {count:<10} {percent:.1f}% {bar}")
            
        print("\nBREAKDOWN BY STATUS:")
        print("-"*50)
        print(f"{'Status':<15} {'Count':<10} {'Percentage':<15}")
        print("-"*50)
        
        for status_row in by_status:
            status_name = status_row['status']
            count = status_row['count']
            percent = (count/total*100) if total > 0 else 0
            
            # Create simple bar chart
            bar_length = int(percent / 2)  # Scale to max 50 chars
            bar = '█' * bar_length
            
            print(f"{status_name[:15]:<15} {count:<10} {percent:.1f}% {bar}")
            
        print("="*50)
        
        # Offer to generate PDF report
        generate_report = input("\n" + get_text("housing.accommodation.input.generate_pdf_report", "Would you like to generate a PDF report of these metrics? (y/n): ")).lower()
        if generate_report == 'y':
            export_dashboard_report()

    except Exception as e:
        logging.error(f"Error showing dashboard metrics: {e}")
        print(get_text("housing.accommodation.error.displaying_dashboard", "Error displaying dashboard metrics: {error}").format(error=e))


def export_dashboard_report():
    """Generate a PDF report of dashboard metrics."""
    try:
        # Check for reportlab
        if not canvas:
            print(get_text("housing.accommodation.error.reportlab_not_installed", "Error: reportlab module not installed. Cannot export to PDF."))
            return

        # Get save location
        filename = f"accommodation_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
        if path:
            full_path = os.path.join(path, filename)
        else:
            full_path = filename
            
        # Ensure directory exists
        directory = os.path.dirname(full_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        # Current date for active/expired calculations
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get data
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get counts by accommodation type
            cursor.execute('''
                SELECT accommodation_type, COUNT(*) as count
                FROM accommodations
                GROUP BY accommodation_type
                ORDER BY count DESC
            ''')
            by_type = cursor.fetchall()
            
            # Get counts by status
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM accommodations
                GROUP BY status
                ORDER BY count DESC
            ''')
            by_status = cursor.fetchall()
            
            # Count recently added accommodations (last 30 days)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE created_at >= ?
            ''', (thirty_days_ago,))
            recent_count = cursor.fetchone()[0]
            
            # Count active accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE (end_date >= ? OR end_date IS NULL) AND status = 'active'
            ''', (today,))
            active_count = cursor.fetchone()[0]
            
            # Count expired accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE (end_date < ? OR status = 'expired')
            ''', (today,))
            expired_count = cursor.fetchone()[0]
            
            # Count pending accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE status = 'pending'
            ''')
            pending_count = cursor.fetchone()[0]
            
            # Count expiring soon (next 30 days)
            thirty_days_future = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE end_date BETWEEN ? AND ? AND status = 'active'
            ''', (today, thirty_days_future))
            expiring_soon = cursor.fetchone()[0]
            
            # Get total count
            cursor.execute('SELECT COUNT(*) FROM accommodations')
            total = cursor.fetchone()[0]
            
        # Create PDF document
        doc = SimpleDocTemplate(full_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Add title
        title = Paragraph("Accommodation Dashboard Report", styles['Title'])
        elements.append(title)
        
        # Add timestamp
        timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
        elements.append(timestamp)
        elements.append(Paragraph("<br/>", styles['Normal']))
        
        # Add overview
        elements.append(Paragraph("Overview", styles['Heading2']))
        overview_data = [
            ['Metric', 'Count', 'Percentage'],
            ['Total Records', str(total), '100%'],
            ['Active', str(active_count), f"{(active_count/total*100) if total > 0 else 0:.1f}%"],
            ['Expired', str(expired_count), f"{(expired_count/total*100) if total > 0 else 0:.1f}%"],
            ['Pending Approval', str(pending_count), f"{(pending_count/total*100) if total > 0 else 0:.1f}%"],
            ['Added in Last 30 Days', str(recent_count), f"{(recent_count/total*100) if total > 0 else 0:.1f}%"],
            ['Expiring in Next 30 Days', str(expiring_soon), f"{(expiring_soon/total*100) if total > 0 else 0:.1f}%"]
        ]
        
        overview_table = Table(overview_data, colWidths=[200, 100, 100])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(overview_table)
        elements.append(Paragraph("<br/><br/>", styles['Normal']))
        
        # Add type breakdown
        elements.append(Paragraph("Breakdown by Accommodation Type", styles['Heading2']))
        type_data = [['Type', 'Count', 'Percentage']]
        
        for type_row in by_type:
            type_name = type_row['accommodation_type']
            count = type_row['count']
            percent = (count/total*100) if total > 0 else 0
            type_data.append([type_name, str(count), f"{percent:.1f}%"])
            
        type_table = Table(type_data, colWidths=[200, 100, 100])
        type_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(type_table)
        elements.append(Paragraph("<br/><br/>", styles['Normal']))
        
        # Add status breakdown
        elements.append(Paragraph("Breakdown by Status", styles['Heading2']))
        status_data = [['Status', 'Count', 'Percentage']]
        
        for status_row in by_status:
            status_name = status_row['status']
            count = status_row['count']
            percent = (count/total*100) if total > 0 else 0
            status_data.append([status_name, str(count), f"{percent:.1f}%"])
            
        status_table = Table(status_data, colWidths=[200, 100, 100])
        status_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(status_table)
        
        # Build the PDF
        doc.build(elements)
        print(get_text("housing.accommodation.success.dashboard_exported", "Dashboard report exported to {path}").format(path=full_path))

    except Exception as e:
        logging.error(f"Error exporting dashboard report: {e}")
        print(get_text("housing.accommodation.error.exporting_dashboard", "Error exporting dashboard report: {error}").format(error=e))


def approve_accommodation():
    """Approve or reject pending accommodations."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_approve", "You must be logged in to approve accommodations."))
        return

    if not auth.check_permission('approve_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_approve", "You don't have permission to approve accommodations."))
        return
    
    # Backup before making changes
    backup_before_operation('accommodation_approval')
    
    init_accommodation_db()
    try:
        # Get list of pending accommodations
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id, a.student_id, a.accommodation_type, a.description, a.start_date, a.end_date,
                       s.first_name, s.last_name
                FROM accommodations a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.status = 'pending'
                ORDER BY a.created_at DESC
            ''')
            
            pending = cursor.fetchall()
            
        if not pending:
            print(get_text("housing.accommodation.message.no_pending_approvals", "No pending accommodations require approval."))
            return
            
        print(f"\nPending Accommodations ({len(pending)}):")
        print("=" * 80)
        print(f"{'ID':<5} {'Student':<20} {'Type':<20} {'Dates':<25} {'Desc':<20}")
        print("-" * 80)
        
        for acc in pending:
            student_name = f"{acc['student_id']} - {acc['first_name'] or ''} {acc['last_name'] or ''}".strip()
            dates = f"{acc['start_date'] or 'N/A'} to {acc['end_date'] or 'N/A'}"
            desc = acc['description'] or 'N/A'
            if len(desc) > 20:
                desc = desc[:17] + "..."
                
            print(f"{acc['id']:<5} {student_name[:20]:<20} {acc['accommodation_type'][:20]:<20} {dates[:25]:<25} {desc[:20]:<20}")
            
        print("=" * 80)
        
        # Get accommodation ID to approve/reject
        while True:
            id_str = input("\n" + get_text("housing.accommodation.input.enter_id_to_process", "Enter accommodation ID to process (or 'q' to quit): ")).strip()
            if id_str.lower() == 'q':
                return

            try:
                accommodation_id = int(id_str)
                # Check if this ID is in the pending list
                if not any(acc['id'] == accommodation_id for acc in pending):
                    print(get_text("housing.accommodation.error.not_pending_id", "Error: {id} is not a pending accommodation ID.").format(id=accommodation_id))
                    continue
                break
            except ValueError:
                print(get_text("housing.accommodation.error.valid_id_number", "Error: Please enter a valid ID number."))
                
        # Display the selected accommodation
        view_accommodation_by_id(accommodation_id)
        
        # Get approval decision
        print("\n" + get_text("housing.accommodation.label.approval_options", "Approval Options:"))
        print("1. " + get_text("housing.accommodation.menu.approve", "Approve"))
        print("2. " + get_text("housing.accommodation.menu.reject", "Reject"))
        print("3. " + get_text("housing.accommodation.menu.request_more_info", "Request more information"))
        print("4. " + get_text("housing.accommodation.menu.cancel", "Cancel"))

        decision = input(get_text("housing.accommodation.input.enter_choice_1_4", "Enter your choice (1-4): ")).strip()

        if decision == '4':
            print(get_text("housing.accommodation.message.approval_cancelled", "Approval process cancelled."))
            return

        # Get approval reason
        reason = input(get_text("housing.accommodation.input.reason_or_comments", "Enter reason or comments [optional]: ")).strip() or None
        
        # Process the decision
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user = get_current_user()
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get the student ID for notification
            cursor.execute('SELECT student_id, accommodation_type FROM accommodations WHERE id = ?', (accommodation_id,))
            acc_info = cursor.fetchone()
            student_id = acc_info[0]
            acc_type = acc_info[1]
            
            if decision == '1':  # Approve
                cursor.execute('''
                    UPDATE accommodations SET
                    status = 'active',
                    approved_by = ?,
                    approval_date = ?,
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (user, now, f"Approved: {reason}", f"Approved: {reason}", now, accommodation_id))
                
                action_type = 'approve'
                message = f"Your {acc_type} accommodation has been approved."
                if reason:
                    message += f" Comments: {reason}"
                    
                print(get_text("housing.accommodation.success.approved", "Accommodation {id} approved.").format(id=accommodation_id))

            elif decision == '2':  # Reject
                cursor.execute('''
                    UPDATE accommodations SET
                    status = 'rejected',
                    approved_by = ?,
                    approval_date = ?,
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (user, now, f"Rejected: {reason}", f"Rejected: {reason}", now, accommodation_id))
                
                action_type = 'reject'
                message = f"Your {acc_type} accommodation has been rejected."
                if reason:
                    message += f" Reason: {reason}"
                    
                print(get_text("housing.accommodation.success.rejected", "Accommodation {id} rejected.").format(id=accommodation_id))

            elif decision == '3':  # Request more info
                cursor.execute('''
                    UPDATE accommodations SET
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (f"More info requested: {reason}", f"More info requested: {reason}", now, accommodation_id))
                
                action_type = 'request_info'
                message = f"More information is required for your {acc_type} accommodation."
                if reason:
                    message += f" Details: {reason}"
                    
                print(get_text("housing.accommodation.success.more_info_requested", "More information requested for accommodation {id}.").format(id=accommodation_id))

            conn.commit()
            
        # Log the action
        log_action(action_type, accommodation_id, f"{action_type.capitalize()} accommodation for {student_id}: {reason}")
        
        # Notify student
        from university_system.infrastructure.email.template_utils import render_template

        subject, body = render_template('accommodation_notification', {
            'action_type': action_type.replace('_', ' ').title(),
            'message': message
        })

        if subject and body:
            notify_student(student_id, subject, body)
        
    except Exception as e:
        logging.error(f"Error in approve_accommodation: {e}")
        print(get_text("housing.accommodation.error.processing_approval", "Error processing accommodation approval: {error}").format(error=e))


def import_from_json():
    """Import accommodations from a JSON file."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_import", "You must be logged in to import accommodations."))
        return

    if not auth.check_permission('manage_accommodations') or not auth.check_permission('batch_operations'):
        print(get_text("housing.accommodation.auth.no_permission_import", "You don't have permission to import accommodations."))
        return
    
    # Backup before making changes
    backup_before_operation('accommodation_import')
    
    init_accommodation_db()
    try:
        # Get file path
        file_path = input(get_text("housing.accommodation.input.enter_json_path", "Enter path to JSON file: ")).strip()
        if not os.path.exists(file_path):
            print(get_text("housing.accommodation.error.file_not_found", "Error: File not found."))
            return
            
        # Read and parse JSON file
        with open(file_path, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(get_text("housing.accommodation.error.invalid_json_format", "Error: Invalid JSON format - {error}").format(error=e))
                return

        if not isinstance(data, list):
            print(get_text("housing.accommodation.error.json_must_be_list", "Error: JSON file must contain a list of accommodation records."))
            return
            
        # Process records
        success_count = 0
        error_count = 0
        
        for i, record in enumerate(data):
            try:
                # Validate required fields
                student_id = record.get('student_id')
                acc_type = record.get('accommodation_type')
                
                if not student_id or not acc_type:
                    error_count += 1
                    print(f"Error: Record {i+1} - Missing required fields")
                    continue
                    
                # Check if student exists
                if not validate_student_id(student_id):
                    error_count += 1
                    print(f"Error: Record {i+1} - Student ID {student_id} not found")
                    continue
                    
                # Extract other fields
                description = record.get('description')
                start_date = record.get('start_date')
                end_date = record.get('end_date')
                status = record.get('status', 'active')
                notes = record.get('notes')
                
                # Validate dates
                if start_date:
                    valid, error = validate_date(start_date)
                    if not valid:
                        error_count += 1
                        print(f"Error: Record {i+1} - Invalid start date - {error}")
                        continue
                        
                if end_date:
                    valid, error = validate_date(end_date)
                    if not valid:
                        error_count += 1
                        print(f"Error: Record {i+1} - Invalid end date - {error}")
                        continue
                
                # Check for conflicts
                if check_conflict(student_id, acc_type, start_date, end_date):
                    print(f"Warning: Record {i+1} - Conflict for student {student_id}, type {acc_type}")
                    
                # Insert record
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO accommodations 
                        (student_id, accommodation_type, description, start_date, end_date, status, notes, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, acc_type, description, start_date, end_date, status, notes, now, now))
                    
                    aid = cursor.lastrowid
                    conn.commit()
                    
                    log_action('import', aid, f"Imported from JSON: {acc_type} for {student_id}")
                    success_count += 1
                    
            except Exception as rec_e:
                error_count += 1
                logging.error(f"Error importing record {i+1}: {rec_e}")
                print(f"Error: Record {i+1} - {rec_e}")
                
        print("\n" + get_text("housing.accommodation.json.import_complete", "Import complete: {success} records imported successfully, {errors} errors.").format(success=success_count, errors=error_count))

    except Exception as e:
        logging.error(f"Error importing from JSON: {e}")
        print(get_text("housing.accommodation.error.importing_json", "Error importing from JSON: {error}").format(error=e))


def generate_statistics_report():
    """Generate detailed statistics about accommodations."""
    auth = get_auth()

    # Check for permission
    if not auth or not auth.current_user:
        print(get_text("housing.accommodation.auth.must_be_logged_in_reports", "You must be logged in to generate reports."))
        return

    if not auth.check_permission('view_accommodations'):
        print(get_text("housing.accommodation.auth.no_permission_reports", "You don't have permission to generate reports."))
        return
    
    init_accommodation_db()
    try:
        print("\n" + get_text("housing.accommodation.message.generating_statistics", "Generating Accommodation Statistics Report..."))
        
        # Current date for calculations
        today = datetime.now().strftime('%Y-%m-%d')
        current_year = datetime.now().year
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Total accommodations
            cursor.execute('SELECT COUNT(*) FROM accommodations')
            total_count = cursor.fetchone()[0]
            
            # Active accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM accommodations
                WHERE (end_date >= ? OR end_date IS NULL) AND status = 'active'
            ''', (today,))
            active_count = cursor.fetchone()[0]
            
            # Monthly trends for the current year
            cursor.execute('''
                SELECT strftime('%m', created_at) as month, COUNT(*) as count
                FROM accommodations
                WHERE created_at LIKE ?
                GROUP BY month
                ORDER BY month
            ''', (f"{current_year}%",))
            
            monthly_data = cursor.fetchall()
            
            # Number of students with multiple accommodations
            cursor.execute('''
                SELECT COUNT(*) FROM (
                    SELECT student_id
                    FROM accommodations
                    WHERE status = 'active'
                    GROUP BY student_id
                    HAVING COUNT(*) > 1
                )
            ''')
            multiple_acc_count = cursor.fetchone()[0]
            
            # Course distribution of accommodations
            cursor.execute('''
                SELECT s.course, COUNT(*) as count
                FROM accommodations a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.status = 'active'
                GROUP BY s.course
                ORDER BY count DESC
            ''')
            
            course_distribution = cursor.fetchall()
            
            # Average duration of accommodations
            cursor.execute('''
                SELECT AVG(julianday(end_date) - julianday(start_date)) as avg_days
                FROM accommodations
                WHERE start_date IS NOT NULL AND end_date IS NOT NULL
            ''')
            
            avg_duration = cursor.fetchone()['avg_days'] or 0
            
            # Approval rate for accommodations that require approval
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as approved
                FROM accommodations
                WHERE status IN ('active', 'rejected')
            ''')
            
            approval_data = cursor.fetchone()
            total_requests = approval_data['total_requests']
            approved = approval_data['approved']
            approval_rate = (approved / total_requests * 100) if total_requests > 0 else 0
            
        # Display the statistics
        print("\n" + "="*60)
        print(" "*15 + "ACCOMMODATION STATISTICS")
        print("="*60)
        
        print(f"\nTotal accommodations: {total_count}")
        print(f"Currently active: {active_count} ({(active_count/total_count*100) if total_count > 0 else 0:.1f}%)")
        print(f"Students with multiple accommodations: {multiple_acc_count}")
        print(f"Average accommodation duration: {avg_duration:.1f} days")
        print(f"Approval rate: {approval_rate:.1f}%")
        
        print("\nCourse Distribution:")
        for course in course_distribution:
            course_name = course['course'] or 'Unknown'
            count = course['count']
            percent = (count/active_count*100) if active_count > 0 else 0
            print(f" - {course_name}: {count} ({percent:.1f}%)")
            
        # Show monthly trends
        print("\nMonthly Trends for Current Year:")
        month_names = {
            '01': 'January', '02': 'February', '03': 'March', '04': 'April',
            '05': 'May', '06': 'June', '07': 'July', '08': 'August',
            '09': 'September', '10': 'October', '11': 'November', '12': 'December'
        }
        
        max_count = max([row['count'] for row in monthly_data]) if monthly_data else 0
        
        for month_data in monthly_data:
            month = month_data['month']
            count = month_data['count']
            month_name = month_names.get(month, month)
            
            # Generate simple bar chart
            bar_width = 40  # characters
            bar_length = int((count / max_count) * bar_width) if max_count > 0 else 0
            bar = '█' * bar_length
            
            print(f"{month_name:10} ({count:3}): {bar}")
            
        print("="*60)
        
        # Ask to export the report
        export = input("\n" + get_text("housing.accommodation.input.export_report", "Would you like to export this report to a file? (y/n): ")).lower()
        if export == 'y':
            export_statistics_report(total_count, active_count, multiple_acc_count,
                                   avg_duration, approval_rate, course_distribution,
                                   monthly_data, month_names)

    except Exception as e:
        logging.error(f"Error generating statistics report: {e}")
        print(get_text("housing.accommodation.error.generating_statistics", "Error generating statistics report: {error}").format(error=e))


def export_statistics_report(total_count, active_count, multiple_acc_count,
                           avg_duration, approval_rate, course_distribution,
                           monthly_data, month_names):
    """Export the statistics report to a file."""
    try:
        # Ask for export format
        print("\n" + get_text("housing.accommodation.export.format", "Export format:"))
        print("1. CSV")
        print("2. PDF")
        print("3. TXT")

        format_choice = input(get_text("housing.accommodation.input.select_format", "Select format (1-3): ")).strip()
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_base = f"accommodation_statistics_{timestamp}"
        
        if format_choice == '1':  # CSV
            filename = filename_base + ".csv"

            # Get save location
            path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
            if path:
                full_path = os.path.join(path, filename)
            else:
                full_path = filename
                
            # Ensure directory exists
            directory = os.path.dirname(full_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            # Write to CSV
            with open(full_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write summary
                writer.writerow(['Accommodation Statistics Report', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow([])
                writer.writerow(['Metric', 'Value'])
                writer.writerow(['Total Accommodations', total_count])
                writer.writerow(['Active Accommodations', active_count])
                writer.writerow(['Active Percentage', f"{(active_count/total_count*100) if total_count > 0 else 0:.1f}%"])
                writer.writerow(['Students with Multiple Accommodations', multiple_acc_count])
                writer.writerow(['Average Duration (days)', f"{avg_duration:.1f}"])
                writer.writerow(['Approval Rate', f"{approval_rate:.1f}%"])
                writer.writerow([])
                
                # Write course distribution
                writer.writerow(['Course Distribution'])
                writer.writerow(['Course', 'Count', 'Percentage'])
                for course in course_distribution:
                    course_name = course['course'] or 'Unknown'
                    count = course['count']
                    percent = (count/active_count*100) if active_count > 0 else 0
                    writer.writerow([course_name, count, f"{percent:.1f}%"])
                writer.writerow([])
                
                # Write monthly trends
                writer.writerow(['Monthly Trends'])
                writer.writerow(['Month', 'Count'])
                for month_data in monthly_data:
                    month = month_data['month']
                    count = month_data['count']
                    month_name = month_names.get(month, month)
                    writer.writerow([month_name, count])
                    
            print(get_text("housing.accommodation.success.statistics_exported", "Statistics exported to {path}").format(path=full_path))

        elif format_choice == '2':  # PDF
            if not canvas:
                print(get_text("housing.accommodation.error.reportlab_not_installed", "Error: reportlab module not installed. Cannot export to PDF."))
                return

            filename = filename_base + ".pdf"

            # Get save location
            path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
            if path:
                full_path = os.path.join(path, filename)
            else:
                full_path = filename
                
            # Ensure directory exists
            directory = os.path.dirname(full_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            # Create PDF document
            doc = SimpleDocTemplate(full_path, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []
            
            # Add title
            title = Paragraph("Accommodation Statistics Report", styles['Title'])
            elements.append(title)
            
            # Add timestamp
            timestamp = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
            elements.append(timestamp)
            elements.append(Paragraph("<br/>", styles['Normal']))
            
            # Add summary
            elements.append(Paragraph("Summary", styles['Heading2']))
            summary_data = [
                ['Metric', 'Value'],
                ['Total Accommodations', str(total_count)],
                ['Active Accommodations', str(active_count)],
                ['Active Percentage', f"{(active_count/total_count*100) if total_count > 0 else 0:.1f}%"],
                ['Students with Multiple Accommodations', str(multiple_acc_count)],
                ['Average Duration (days)', f"{avg_duration:.1f}"],
                ['Approval Rate', f"{approval_rate:.1f}%"]
            ]
            
            summary_table = Table(summary_data, colWidths=[300, 100])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(summary_table)
            elements.append(Paragraph("<br/><br/>", styles['Normal']))
            
            # Add course distribution
            elements.append(Paragraph("Course Distribution", styles['Heading2']))
            course_data = [['Course', 'Count', 'Percentage']]
            
            for course in course_distribution:
                course_name = course['course'] or 'Unknown'
                count = course['count']
                percent = (count/active_count*100) if active_count > 0 else 0
                course_data.append([course_name, str(count), f"{percent:.1f}%"])
                
            course_table = Table(course_data, colWidths=[200, 100, 100])
            course_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(course_table)
            elements.append(Paragraph("<br/><br/>", styles['Normal']))
            
            # Add monthly trends
            elements.append(Paragraph("Monthly Trends", styles['Heading2']))
            month_data = [['Month', 'Count']]
            
            for month_info in monthly_data:
                month = month_info['month']
                count = month_info['count']
                month_name = month_names.get(month, month)
                month_data.append([month_name, str(count)])
                
            month_table = Table(month_data, colWidths=[200, 100])
            month_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(month_table)
            
            # Build the PDF
            doc.build(elements)
            print(get_text("housing.accommodation.success.statistics_exported", "Statistics exported to {path}").format(path=full_path))

        elif format_choice == '3':  # TXT
            filename = filename_base + ".txt"

            # Get save location
            path = input(get_text("housing.accommodation.input.enter_save_path", "Enter save path (or press Enter for current directory): ")).strip()
            if path:
                full_path = os.path.join(path, filename)
            else:
                full_path = filename
                
            # Ensure directory exists
            directory = os.path.dirname(full_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            # Write to text file
            with open(full_path, 'w') as txtfile:
                txtfile.write("ACCOMMODATION STATISTICS REPORT\n")
                txtfile.write("="*60 + "\n\n")
                txtfile.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                txtfile.write("SUMMARY:\n")
                txtfile.write("-"*60 + "\n")
                txtfile.write(f"Total accommodations: {total_count}\n")
                txtfile.write(f"Currently active: {active_count} ({(active_count/total_count*100) if total_count > 0 else 0:.1f}%)\n")
                txtfile.write(f"Students with multiple accommodations: {multiple_acc_count}\n")
                txtfile.write(f"Average accommodation duration: {avg_duration:.1f} days\n")
                txtfile.write(f"Approval rate: {approval_rate:.1f}%\n\n")
                
                txtfile.write("COURSE DISTRIBUTION:\n")
                txtfile.write("-"*60 + "\n")
                for course in course_distribution:
                    course_name = course['course'] or 'Unknown'
                    count = course['count']
                    percent = (count/active_count*100) if active_count > 0 else 0
                    txtfile.write(f"{course_name}: {count} ({percent:.1f}%)\n")
                    
                txtfile.write("\nMONTHLY TRENDS:\n")
                txtfile.write("-"*60 + "\n")
                for month_data in monthly_data:
                    month = month_data['month']
                    count = month_data['count']
                    month_name = month_names.get(month, month)
                    txtfile.write(f"{month_name}: {count}\n")
                    
            print(get_text("housing.accommodation.success.statistics_exported", "Statistics exported to {path}").format(path=full_path))

        else:
            print(get_text("housing.accommodation.error.invalid_format_selection", "Invalid format selection."))

    except Exception as e:
        logging.error(f"Error exporting statistics report: {e}")
        print(get_text("housing.accommodation.error.exporting_statistics", "Error exporting statistics report: {error}").format(error=e))


def display_accommodation_menu():
    """Interactive menu for accommodation management including advanced features."""
    auth = get_auth()

    init_accommodation_db()
    
    # Define menu options with permission requirements
    options = {
        '1': ('Register Student Accommodation', add_accommodation, ['manage_accommodations']),
        '2': ('Bulk Import from CSV', bulk_import_from_csv, ['manage_accommodations', 'batch_operations']),
        '3': ('Import from JSON', import_from_json, ['manage_accommodations', 'batch_operations']),
        '4': ('Save Template', save_template, ['manage_accommodations']),
        '5': ('Apply Template', apply_template, ['manage_accommodations']),
        '6': ('Search/Filter Accommodations', view_accommodations, ['view_accommodations']),
        '7': ('Update Accommodation', update_accommodation, ['manage_accommodations']),
        '8': ('Remove Accommodation', remove_accommodation, ['manage_accommodations']),
        '9': ('View by Accommodation Type', view_students_by_accommodation, ['view_accommodations']),
        '10': ('Approve/Reject Accommodations', approve_accommodation, ['approve_accommodations']),
        '11': ('Export Data', export_accommodations, ['export_data']),
        '12': ('Check Expiry Notifications', check_expiry_notifications, ['manage_accommodations']),
        '13': ('Dashboard Metrics', show_dashboard_metrics, ['view_accommodations']),
        '14': ('Generate Statistics Report', generate_statistics_report, ['view_accommodations']),
        '15': ('Return to Main Menu', None, [])
    }
    
    while True:
        print("\n" + get_text("housing.accommodation.menu.title", "Accommodation Management:"))
        print("=" * 40)
        
        # Display only options the user has permission for
        available_options = []
        
        for key, (desc, _, required_perms) in options.items():
            # If no auth or no permissions required, show the option
            if not auth or not required_perms or not auth.current_user:
                print(f"{key}. {desc}")
                available_options.append(key)
            # Otherwise, check permissions
            elif auth and auth.current_user:
                if all(auth.check_permission(perm) for perm in required_perms):
                    print(f"{key}. {desc}")
                    available_options.append(key)
        
        choice = input("\n" + get_text("housing.accommodation.input.enter_your_choice", "Enter your choice: ")).strip()

        if choice not in options:
            print(get_text("housing.accommodation.error.invalid_choice", "Invalid choice. Please try again."))
            continue

        if choice not in available_options:
            print(get_text("housing.accommodation.error.no_permission_option", "You don't have permission to access that option."))
            continue

        desc, func, _ = options[choice]
        if func:
            try:
                # If function requires a filepath parameter
                if func == bulk_import_from_csv:
                    filepath = input(get_text("housing.accommodation.input.csv_file_path", "CSV file path: ")).strip()
                    func(filepath)
                else:
                    func()
            except Exception as e:
                logging.error(f"Menu action error ({desc}): {e}")
                print(get_text("housing.accommodation.error.during_action", "An error occurred during {action}: {error}").format(action=desc, error=e))
                print(get_text("housing.accommodation.error.try_again_or_contact", "Please try again or contact technical support."))
        else:
            # Return to main menu
            break

def migrate_audit_log_schema():
    """Migrate the audit_log table to include missing columns."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check current schema of audit_log table
            cursor.execute("PRAGMA table_info(audit_log)")
            columns = [row[1] for row in cursor.fetchall()]

            print(get_text("housing.accommodation.db.current_columns", "Current audit_log columns:"), columns)

            # Check if accommodation_id column exists
            if 'accommodation_id' not in columns:
                print(get_text("housing.accommodation.db.adding_column", "Adding missing {column} column...").format(column="accommodation_id"))
                cursor.execute('ALTER TABLE audit_log ADD COLUMN accommodation_id INTEGER')

            # Check if details column exists
            if 'details' not in columns:
                print(get_text("housing.accommodation.db.adding_column", "Adding missing {column} column...").format(column="details"))
                cursor.execute('ALTER TABLE audit_log ADD COLUMN details TEXT')

            # Check if ip_address column exists
            if 'ip_address' not in columns:
                print(get_text("housing.accommodation.db.adding_column", "Adding missing {column} column...").format(column="ip_address"))
                cursor.execute('ALTER TABLE audit_log ADD COLUMN ip_address TEXT')

            conn.commit()
            print(get_text("housing.accommodation.db.migration_complete", "Schema migration completed successfully!"))

            # Verify the new schema
            cursor.execute("PRAGMA table_info(audit_log)")
            new_columns = [row[1] for row in cursor.fetchall()]
            print(get_text("housing.accommodation.db.updated_columns", "Updated audit_log columns:"), new_columns)

    except Exception as e:
        logging.error(f"Error migrating audit_log schema: {e}")
        print(get_text("housing.accommodation.error.migrating_schema", "Error migrating schema: {error}").format(error=e))
        return False

    return True


def fix_accommodation_db_schema():
    """Fix any schema issues in the accommodation database."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check if the accommodations table exists and has all required columns
            cursor.execute("PRAGMA table_info(accommodations)")
            acc_columns = [row[1] for row in cursor.fetchall()]

            print(get_text("housing.accommodation.db.current_acc_columns", "Current accommodations columns:"), acc_columns)
            
            # Required columns for accommodations table
            required_acc_columns = [
                ('status', 'TEXT DEFAULT "active"'),
                ('approved_by', 'TEXT'),
                ('approval_date', 'TEXT'),
                ('notes', 'TEXT')
            ]
            
            for col_name, col_def in required_acc_columns:
                if col_name not in acc_columns:
                    print(get_text("housing.accommodation.db.adding_column_to_table", "Adding missing column {column} to accommodations table...").format(column=col_name))
                    from university_system.core.sql_safety import validate_identifier
                    validate_identifier(col_name, "column")
                    cursor.execute("ALTER TABLE accommodations ADD COLUMN [" + col_name + "] " + col_def)
            
            # Check if accommodation_types table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='accommodation_types'
            """)
            
            if not cursor.fetchone():
                print(get_text("housing.accommodation.db.creating_table", "Creating missing {table} table...").format(table="accommodation_types"))
                cursor.execute('''
                    CREATE TABLE accommodation_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        type_name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        requires_approval BOOLEAN DEFAULT 0,
                        max_duration_days INTEGER,
                        created_at TEXT
                    )
                ''')
                
                # Add default types
                default_types = [
                    ('Extended Time', 'Additional time for assignments or exams', 0, 365),
                    ('Alternate Format', 'Materials provided in alternate formats', 0, 365),
                    ('Note-Taking', 'Note-taking assistance in classes', 0, 365),
                    ('Assistive Technology', 'Access to specialized technology', 1, 365),
                    ('Flexible Attendance', 'Modified attendance requirements', 1, 180)
                ]
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for type_name, desc, req_approval, max_days in default_types:
                    cursor.execute('''
                        INSERT INTO accommodation_types 
                        (type_name, description, requires_approval, max_duration_days, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (type_name, desc, req_approval, max_days, now))
            
            # Check if accommodation_documents table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='accommodation_documents'
            """)

            if not cursor.fetchone():
                print(get_text("housing.accommodation.db.creating_table", "Creating missing {table} table...").format(table="accommodation_documents"))
                cursor.execute('''
                    CREATE TABLE accommodation_documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        accommodation_id INTEGER NOT NULL,
                        document_name TEXT NOT NULL,
                        document_path TEXT NOT NULL,
                        uploaded_by TEXT,
                        uploaded_at TEXT,
                        FOREIGN KEY (accommodation_id) REFERENCES accommodations(id)
                    )
                ''')
            
            # Check if accommodation_templates table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='accommodation_templates'
            """)

            if not cursor.fetchone():
                print(get_text("housing.accommodation.db.creating_table", "Creating missing {table} table...").format(table="accommodation_templates"))
                cursor.execute('''
                    CREATE TABLE accommodation_templates (
                        name TEXT PRIMARY KEY,
                        accommodation_type TEXT NOT NULL,
                        description TEXT,
                        start_offset_days INTEGER,
                        duration_days INTEGER,
                        created_by TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )
                ''')
            
            conn.commit()
            print(get_text("housing.accommodation.db.schema_fix_complete", "Accommodation database schema fix completed!"))

    except Exception as e:
        logging.error(f"Error fixing accommodation database schema: {e}")
        print(get_text("housing.accommodation.error.fixing_schema", "Error fixing schema: {error}").format(error=e))
        return False

    return True


def verify_database_schema():
    """Verify that all required tables and columns exist."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get list of all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            print(get_text("housing.accommodation.db.available_tables", "Available tables:"), tables)

            # Check each table's schema
            for table in tables:
                from university_system.core.sql_safety import validate_table_name
                validated_table = validate_table_name(table, conn=conn)
                cursor.execute("PRAGMA table_info([" + validated_table + "])")
                columns = cursor.fetchall()
                print(f"\n{table} " + get_text("housing.accommodation.db.table_columns", "table columns:"))
                for col in columns:
                    print(f"  - {col[1]} ({col[2]})")

    except Exception as e:
        print(get_text("housing.accommodation.error.verifying_schema", "Error verifying schema: {error}").format(error=e))

if __name__ == "__main__":
    print(get_text("housing.accommodation.main.starting_migration", "Starting database schema migration..."))
    print("=" * 50)

    # Step 1: Migrate audit_log table
    print("\n" + get_text("housing.accommodation.main.step1", "Step 1: Migrating audit_log table..."))
    if migrate_audit_log_schema():
        print(get_text("housing.accommodation.main.audit_log_success", "audit_log migration successful"))
    else:
        print(get_text("housing.accommodation.main.audit_log_failed", "audit_log migration failed"))

    # Step 2: Fix accommodation database schema
    print("\n" + get_text("housing.accommodation.main.step2", "Step 2: Fixing accommodation database schema..."))
    if fix_accommodation_db_schema():
        print(get_text("housing.accommodation.main.schema_fix_success", "Accommodation schema fix successful"))
    else:
        print(get_text("housing.accommodation.main.schema_fix_failed", "Accommodation schema fix failed"))

    # Step 3: Verify final schema
    print("\n" + get_text("housing.accommodation.main.step3", "Step 3: Verifying database schema..."))
    verify_database_schema()

    print("\n" + "=" * 50)
    print(get_text("housing.accommodation.main.migration_completed", "Migration completed!"))

    display_accommodation_menu()
