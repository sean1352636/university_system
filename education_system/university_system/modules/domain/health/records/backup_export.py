from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection, DEFAULT_DB_PATH
from education_system.university_system.modules.domain.health.services import validate_csv_format, log_audit_event
from datetime import datetime, timedelta
import random
import os
import hashlib
import hmac
import json
import logging
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from cryptography.fernet import Fernet
import requests
from collections import defaultdict
import csv
import statistics
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)
from education_system.university_system.utils.logging.log_config import configure_logging

# Configure logging for audit trail
audit_logger = configure_logging(name=__name__)

# Encryption key management


def export_vaccination_records(auth):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get date range
    start_date = input("Start date (YYYY-MM-DD) [leave blank for all]: ").strip()
    end_date = input("End date (YYYY-MM-DD) [leave blank for all]: ").strip()
    
    query = '''
    SELECT vr.id, vr.student_id, s.first_name, s.last_name, vr.vaccine_name,
           vr.administered_date, vr.expiry_date, vr.lot_number, vr.manufacturer,
           vr.administered_by, vr.verified, vr.adverse_reaction
    FROM vaccination_records vr
    JOIN students s ON vr.student_id = s.student_id
    '''
    
    params = []
    
    if start_date and end_date:
        query += " WHERE vr.administered_date BETWEEN ? AND ?"
        params = [start_date, end_date]
    elif start_date:
        query += " WHERE vr.administered_date >= ?"
        params = [start_date]
    elif end_date:
        query += " WHERE vr.administered_date <= ?"
        params = [end_date]
    
    query += " ORDER BY vr.administered_date DESC"
    
    cursor.execute(query, params)
    records = cursor.fetchall()
    
    if not records:
        print("No vaccination records found for export.")
        conn.close()
        return
    
    # Export to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"vaccination_export_{timestamp}.csv"
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'Record ID', 'Student ID', 'First Name', 'Last Name', 'Vaccine',
                'Administered Date', 'Expiry Date', 'Lot Number', 'Manufacturer',
                'Administered By', 'Verified', 'Adverse Reaction'
            ])
            
            # Write data
            for record in records:
                writer.writerow(record)
        
        log_audit_event(auth.current_user['id'], 'export_vaccination_records', 'data_export', filename)
        print(f"\nVaccination records exported successfully to: {filename}")
        print(f"Total records exported: {len(records)}")
        
    except Exception as e:
        print(f"Error exporting data: {e}")
    
    conn.close()

def export_appointment_data(auth):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get date range
    start_date = input("Start date (YYYY-MM-DD) [leave blank for all]: ").strip()
    end_date = input("End date (YYYY-MM-DD) [leave blank for all]: ").strip()
    
    query = '''
    SELECT ha.id, ha.student_id, s.first_name, s.last_name, ha.appointment_type,
           ha.appointment_date, ha.appointment_time, ha.provider, ha.reason,
           ha.status, ha.scheduled_at
    FROM health_appointments ha
    JOIN students s ON ha.student_id = s.student_id
    '''
    
    params = []
    
    if start_date and end_date:
        query += " WHERE ha.appointment_date BETWEEN ? AND ?"
        params = [start_date, end_date]
    elif start_date:
        query += " WHERE ha.appointment_date >= ?"
        params = [start_date]
    elif end_date:
        query += " WHERE ha.appointment_date <= ?"
        params = [end_date]
    
    query += " ORDER BY ha.appointment_date DESC"
    
    cursor.execute(query, params)
    records = cursor.fetchall()
    
    if not records:
        print("No appointment data found for export.")
        conn.close()
        return
    
    # Export to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"appointments_export_{timestamp}.csv"
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'Appointment ID', 'Student ID', 'First Name', 'Last Name', 'Type',
                'Date', 'Time', 'Provider', 'Reason', 'Status', 'Scheduled At'
            ])
            
            # Write data
            for record in records:
                writer.writerow(record)
        
        log_audit_event(auth.current_user['id'], 'export_appointment_data', 'data_export', filename)
        print(f"\nAppointment data exported successfully to: {filename}")
        print(f"Total records exported: {len(records)}")
        
    except Exception as e:
        print(f"Error exporting data: {e}")
    
    conn.close()

def export_lab_results(auth):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get date range
    start_date = input("Start date (YYYY-MM-DD) [leave blank for all]: ").strip()
    end_date = input("End date (YYYY-MM-DD) [leave blank for all]: ").strip()
    
    query = '''
    SELECT lr.id, lr.student_id, s.first_name, s.last_name, lr.test_name,
           lr.result_value, lr.reference_range, lr.units, lr.status,
           lr.ordered_date, lr.collected_date, lr.resulted_date,
           lr.ordering_provider, lr.lab_name, lr.abnormal_flag
    FROM lab_results lr
    JOIN students s ON lr.student_id = s.student_id
    '''
    
    params = []
    
    if start_date and end_date:
        query += " WHERE lr.resulted_date BETWEEN ? AND ?"
        params = [start_date, end_date]
    elif start_date:
        query += " WHERE lr.resulted_date >= ?"
        params = [start_date]
    elif end_date:
        query += " WHERE lr.resulted_date <= ?"
        params = [end_date]
    
    query += " ORDER BY lr.resulted_date DESC"
    
    cursor.execute(query, params)
    records = cursor.fetchall()
    
    if not records:
        print("No lab results found for export.")
        conn.close()
        return
    
    # Export to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"lab_results_export_{timestamp}.csv"
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'Result ID', 'Student ID', 'First Name', 'Last Name', 'Test Name',
                'Result Value', 'Reference Range', 'Units', 'Status',
                'Ordered Date', 'Collected Date', 'Resulted Date',
                'Ordering Provider', 'Lab Name', 'Abnormal Flag'
            ])
            
            # Write data
            for record in records:
                writer.writerow(record)
        
        log_audit_event(auth.current_user['id'], 'export_lab_results', 'data_export', filename)
        print(f"\nLab results exported successfully to: {filename}")
        print(f"Total records exported: {len(records)}")
        
    except Exception as e:
        print(f"Error exporting data: {e}")
    
    conn.close()

def export_custom_dataset(auth):
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Custom Dataset Export =====")
    
    # Available tables
    tables = [
        'health_records',
        'vaccination_records',
        'health_appointments',
        'medical_conditions',
        'allergies',
        'prescriptions',
        'vital_signs',
        'lab_results',
        'emergency_contacts'
    ]
    
    print("Available data tables:")
    for i, table in enumerate(tables):
        print(f"{i+1}. {table}")
    
    while True:
        choice = input(f"\nSelect table to export (1-{len(tables)}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(tables):
            selected_table = tables[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    # Custom filters
    print(f"\nExporting from table: {selected_table}")
    
    # Get table structure
    from education_system.university_system.core.sql_safety import validate_table_name
    validated_selected_table = validate_table_name(selected_table, conn=conn)
    cursor.execute("PRAGMA table_info([" + validated_selected_table + "])")
    columns = cursor.fetchall()
    
    print(f"Available columns:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")

    # Get limit (safely)
    limit = input("\nLIMIT (optional, max records to export): ").strip()
    limit_num = None
    if limit:
        try:
            limit_num = int(limit)
            if limit_num <= 0:
                print("Invalid limit value. Exporting all records.")
                limit_num = None
        except ValueError:
            print("Invalid limit value. Exporting all records.")
            limit_num = None

    # Construct query (selected_table already validated above)
    safe_table = "[" + validated_selected_table + "]"
    if selected_table in ['health_records', 'vaccination_records', 'health_appointments',
                         'medical_conditions', 'allergies', 'prescriptions', 'vital_signs',
                         'lab_results', 'emergency_contacts']:
        # Join with students table for name information
        query = (
            "SELECT " + safe_table + ".*, s.first_name, s.last_name"
            " FROM " + safe_table +
            " JOIN students s ON " + safe_table + ".student_id = s.student_id"
        )
    else:
        query = "SELECT * FROM " + safe_table

    if limit_num:
        query += " LIMIT " + str(int(limit_num))
    
    print(f"\nExecuting query: {query}")
    
    try:
        cursor.execute(query)
        records = cursor.fetchall()
        
        if not records:
            print("No records found matching criteria.")
            conn.close()
            return
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        
        # Export to CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"custom_export_{selected_table}_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(column_names)
            
            # Write data
            for record in records:
                writer.writerow(record)
        
        log_audit_event(auth.current_user['id'], 'export_custom_dataset', 'data_export', filename)
        print(f"\nCustom dataset exported successfully to: {filename}")
        print(f"Total records exported: {len(records)}")
        
    except Exception as e:
        print(f"Error executing query or exporting data: {e}")
    
    conn.close()

def restore_from_backup(auth):
    if auth.current_user['role'] != 'admin':
        print("Only administrators can restore from backup.")
        return
    
    import os
    import glob
    import shutil
    
    print("\n⚠️  CRITICAL WARNING ⚠️")
    print("Database restoration will OVERWRITE the current database!")
    print("All current data will be lost!")
    
    # List available backups
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        print("No backup directory found.")
        return
    
    backup_files = glob.glob(os.path.join(backup_dir, "student_records_backup_*.db"))
    backup_files.sort(reverse=True)  # Most recent first
    
    if not backup_files:
        print("No backup files found.")
        return
    
    print("\nAvailable backups:")
    for i, backup_file in enumerate(backup_files[:10]):  # Show last 10 backups
        filename = os.path.basename(backup_file)
        file_size = os.path.getsize(backup_file)
        mod_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
        
        print(f"{i+1}. {filename}")
        print(f"   Size: {file_size:,} bytes")
        print(f"   Date: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    while True:
        choice = input(f"\nSelect backup to restore (1-{len(backup_files[:10])}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(backup_files[:10]):
            selected_backup = backup_files[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    print(f"\nSelected backup: {os.path.basename(selected_backup)}")
    
    # Confirmation
    confirm1 = input("\nType 'RESTORE' to confirm database restoration: ")
    if confirm1 != 'RESTORE':
        print("Restoration cancelled.")
        return
    
    confirm2 = input("Type your username to confirm: ")
    if confirm2 != auth.current_user['username']:
        print("Username mismatch. Restoration cancelled.")
        return
    
    # Create backup of current database before restore
    print("Creating backup of current database...")
    current_backup = f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    current_backup_path = os.path.join(backup_dir, current_backup)
    
    try:
        shutil.copy2(str(DEFAULT_DB_PATH), current_backup_path)
        print(f"Current database backed up to: {current_backup}")
    except Exception as e:
        print(f"Error backing up current database: {e}")
        return
    
    # Restore from selected backup
    try:
        shutil.copy2(selected_backup, str(DEFAULT_DB_PATH))
        
        log_audit_event(auth.current_user['id'], 'restore_from_backup', 'database_restore', 
                       os.path.basename(selected_backup))
        
        print(f"\nDatabase successfully restored from: {os.path.basename(selected_backup)}")
        print("Please restart the application to ensure proper database connection.")
        
    except Exception as e:
        print(f"Error restoring database: {e}")

        # Attempt to restore the pre-restore backup
        try:
            shutil.copy2(current_backup_path, str(DEFAULT_DB_PATH))
            print("Restored original database due to error.")
        except (OSError, IOError):
            print("CRITICAL: Could not restore original database!")

def manage_backup_schedule(auth):
    if auth.current_user['role'] != 'admin':
        print("Only administrators can manage backup schedules.")
        return
    
    print("\n===== Backup Schedule Management =====")
    print("Note: This is a configuration interface.")
    print("Actual scheduling would require system-level cron jobs or task scheduler.")
    
    # Backup schedule options
    schedule_options = [
        'Daily at 2:00 AM',
        'Weekly on Sunday at 3:00 AM',
        'Monthly on 1st at 4:00 AM',
        'Custom schedule'
    ]
    
    print("\nBackup Schedule Options:")
    for i, option in enumerate(schedule_options):
        print(f"{i+1}. {option}")
    
    while True:
        choice = input(f"\nSelect schedule option (1-{len(schedule_options)}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(schedule_options):
            selected_schedule = schedule_options[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    if selected_schedule == 'Custom schedule':
        custom_schedule = input("Enter custom cron expression: ")
        selected_schedule = f"Custom: {custom_schedule}"
    
    # Retention settings
    retention_days = input("Backup retention period (days) [30]: ").strip()
    if not retention_days:
        retention_days = "30"
    
    try:
        retention_days = int(retention_days)
    except ValueError:
        retention_days = 30
        print("Invalid retention period. Using default: 30 days")
    
    # Compression option
    compress_backups = input("Compress backups? (y/n) [y]: ").strip().lower()
    if not compress_backups:
        compress_backups = 'y'
    
    compress_enabled = compress_backups == 'y'
    
    # Save configuration (in a real system, this would be saved to a config file)
    print(f"\n===== Backup Schedule Configuration =====")
    print(f"Schedule: {selected_schedule}")
    print(f"Retention: {retention_days} days")
    print(f"Compression: {'Enabled' if compress_enabled else 'Disabled'}")
    
    # Generate sample cron job
    if selected_schedule == 'Daily at 2:00 AM':
        cron_expression = "0 2 * * *"
    elif selected_schedule == 'Weekly on Sunday at 3:00 AM':
        cron_expression = "0 3 * * 0"
    elif selected_schedule == 'Monthly on 1st at 4:00 AM':
        cron_expression = "0 4 1 * *"
    else:
        cron_expression = "Custom"
    
    print(f"\nSample cron job entry:")
    if cron_expression != "Custom":
        print(f"{cron_expression} /path/to/backup_script.sh")
    else:
        print("Use the custom cron expression you provided")
    
    log_audit_event(auth.current_user['id'], 'configure_backup_schedule', 'backup_config', 0,
                   f"Schedule: {selected_schedule}, Retention: {retention_days} days")
    
    print("\nBackup schedule configuration saved!")
    print("Note: System administrator must implement the actual scheduled task.")

def backup_recovery_menu(auth):
    """System backup and recovery menu"""
    if auth.current_user['role'] != 'admin':
        print("Only administrators can access backup and recovery features.")
        return
    
    while True:
        print("\n===== System Backup & Recovery =====")
        print("1. Create Database Backup")
        print("2. Restore from Backup")
        print("3. Scheduled Backup Settings")
        print("4. Backup History")
        print("5. Data Export")
        print("6. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            create_database_backup(auth)
        elif choice == '2':
            restore_from_backup(auth)
        elif choice == '3':
            manage_backup_schedule(auth)
        elif choice == '4':
            view_backup_history(auth)
        elif choice == '5':
            export_data_menu(auth)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def create_database_backup(auth):
    """Create a database backup"""
    import shutil
    import os
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"student_records_backup_{timestamp}.db"
    backup_dir = "backups"
    
    # Create backup directory if it doesn't exist
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        # Copy the database file
        shutil.copy2(str(DEFAULT_DB_PATH), backup_path)
        
        # Log the backup
        log_audit_event(auth.current_user['id'], 'create_backup', 'database', backup_filename)
        
        print(f"\nDatabase backup created successfully: {backup_path}")
        print(f"Backup size: {os.path.getsize(backup_path)} bytes")
        
    except Exception as e:
        print(f"Error creating backup: {e}")

def view_backup_history(auth):
    """View backup history"""
    import os
    import glob
    
    backup_dir = "backups"
    
    if not os.path.exists(backup_dir):
        print("No backup directory found.")
        return
    
    backup_files = glob.glob(os.path.join(backup_dir, "student_records_backup_*.db"))
    
    if not backup_files:
        print("No backup files found.")
        return
    
    print("\n===== Backup History =====")
    
    backup_files.sort(reverse=True)  # Most recent first
    
    for backup_file in backup_files:
        filename = os.path.basename(backup_file)
        file_size = os.path.getsize(backup_file)
        mod_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
        
        print(f"\nFilename: {filename}")
        print(f"Size: {file_size:,} bytes")
        print(f"Created: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")

def export_data_menu(auth):
    """Data export menu"""
    while True:
        print("\n===== Data Export =====")
        print("1. Export Health Records")
        print("2. Export Vaccination Records")
        print("3. Export Appointment Data")
        print("4. Export Lab Results")
        print("5. Export Custom Dataset")
        print("6. Return to Previous Menu")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            export_health_records(auth)
        elif choice == '2':
            export_vaccination_records(auth)
        elif choice == '3':
            export_appointment_data(auth)
        elif choice == '4':
            export_lab_results(auth)
        elif choice == '5':
            export_custom_dataset(auth)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def export_health_records(auth, format='csv'):
    """Export health records to CSV or JSON format"""
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to export health records.")
        return
    
    print(f"\n===== Export Health Records ({format.upper()}) =====")
    
    # Validate format parameter
    if format.lower() not in ['csv', 'json']:
        print("Error: Format must be 'csv' or 'json'")
        return
    
    # Get export parameters with validation
    student_id = input("Enter student ID (leave blank for all students): ").strip()
    date_from = input("Enter start date (YYYY-MM-DD, leave blank for all): ").strip()
    date_to = input("Enter end date (YYYY-MM-DD, leave blank for all): ").strip()
    include_confidential = input("Include confidential records? (y/N): ").strip().lower() == 'y'
    
    # Validate dates if provided
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
        except ValueError:
            print("Error: Invalid start date format. Use YYYY-MM-DD")
            return
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
        except ValueError:
            print("Error: Invalid end date format. Use YYYY-MM-DD")
            return
    
    # Validate date range
    if date_from and date_to:
        if from_date > to_date:
            print("Error: Start date cannot be after end date")
            return
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if student exists (if specified)
        if student_id:
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone()[0] == 0:
                print(f"Error: Student ID '{student_id}' not found.")
                return
        
        # Build query with proper parameterization
        query = '''
        SELECT hr.id, hr.student_id, s.first_name, s.last_name, hr.record_type,
               hr.record_date, hr.description, hr.provider, hr.confidential, hr.created_at
        FROM health_records hr
        JOIN students s ON hr.student_id = s.student_id
        WHERE 1=1
        '''
        
        params = []
        
        if student_id:
            query += " AND hr.student_id = ?"
            params.append(student_id)
        
        if date_from:
            query += " AND hr.record_date >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND hr.record_date <= ?"
            params.append(date_to)
        
        if not include_confidential:
            query += " AND (hr.confidential = 0 OR hr.confidential IS NULL)"
        
        query += " ORDER BY hr.record_date DESC, hr.student_id, hr.id"
        
        print("\nQuerying database...")
        cursor.execute(query, params)
        records = cursor.fetchall()
        
        if not records:
            print("No records found matching the criteria.")
            return
        
        print(f"Found {len(records)} records to export.")
        
        # Confirm export
        confirm = input(f"Proceed with export? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Export cancelled.")
            return
        
        # Generate filename with descriptive elements
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_parts = ['health_records']
        
        if student_id:
            file_parts.append(f"student_{student_id}")
        else:
            file_parts.append("all_students")
        
        if date_from or date_to:
            date_range = f"{date_from or 'earliest'}_to_{date_to or 'latest'}"
            file_parts.append(date_range)
        
        if include_confidential:
            file_parts.append("including_confidential")
        
        file_parts.append(timestamp)
        filename = f"{'_'.join(file_parts)}.{format.lower()}"
        
        # Ensure we don't overwrite existing files
        counter = 1
        original_filename = filename
        while os.path.exists(filename):
            name_without_ext = original_filename.rsplit('.', 1)[0]
            ext = original_filename.rsplit('.', 1)[1]
            filename = f"{name_without_ext}_{counter}.{ext}"
            counter += 1
        
        # Export based on format
        if format.lower() == 'csv':
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
                    
                    # Write header
                    writer.writerow(['record_id', 'student_id', 'first_name', 'last_name', 
                                   'record_type', 'record_date', 'description', 'provider', 
                                   'confidential', 'created_at'])
                    
                    # Write data with proper handling of None values
                    for record in records:
                        # Convert None values to empty strings and handle confidential boolean
                        cleaned_record = []
                        for i, value in enumerate(record):
                            if value is None:
                                cleaned_record.append('')
                            elif i == 8:  # confidential field
                                cleaned_record.append('true' if value else 'false')
                            else:
                                cleaned_record.append(str(value))
                        writer.writerow(cleaned_record)
                        
            except IOError as e:
                print(f"Error writing CSV file: {e}")
                return
        
        elif format.lower() == 'json':
            try:
                json_data = {
                    'export_info': {
                        'generated_at': datetime.now().isoformat(),
                        'generated_by': auth.current_user.get('username', 'unknown'),
                        'total_records': len(records),
                        'filters': {
                            'student_id': student_id or 'all',
                            'date_from': date_from or 'earliest',
                            'date_to': date_to or 'latest',
                            'include_confidential': include_confidential
                        }
                    },
                    'records': []
                }
                
                for record in records:
                    record_dict = {
                        'record_id': record[0],
                        'student_id': record[1],
                        'first_name': record[2],
                        'last_name': record[3],
                        'record_type': record[4],
                        'record_date': record[5],
                        'description': record[6],
                        'provider': record[7] if record[7] is not None else '',
                        'confidential': bool(record[8]) if record[8] is not None else False,
                        'created_at': record[9]
                    }
                    json_data['records'].append(record_dict)
                
                with open(filename, 'w', encoding='utf-8') as jsonfile:
                    json.dump(json_data, jsonfile, indent=2, ensure_ascii=False, default=str)
                    
            except IOError as e:
                print(f"Error writing JSON file: {e}")
                return
        
        # Verify file was created and get size
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            file_size_mb = file_size / (1024 * 1024)
            
            print(f"\n✅ Export completed successfully!")
            print(f"Records exported: {len(records)}")
            print(f"File saved as: {filename}")
            print(f"File size: {file_size_mb:.2f} MB")
        else:
            print(f"❌ Error: Export file was not created.")
            return
        
        # Log audit event
        try:
            audit_details = {
                'records_count': len(records),
                'filename': filename,
                'format': format,
                'filters': {
                    'student_id': student_id,
                    'date_from': date_from,
                    'date_to': date_to,
                    'include_confidential': include_confidential
                }
            }
            log_audit_event(
                auth.current_user['id'],
                'export_health_records',
                'health_records',
                f"Exported {len(records)} records to {filename}",
                json.dumps(audit_details)
            )
        except Exception as e:
            print(f"Warning: Could not log audit event: {e}")
    
    except Exception as e:
        print(f"Error during export: {e}")
        # Clean up partial file if it exists
        if 'filename' in locals() and os.path.exists(filename):
            try:
                os.remove(filename)
                print("Partial export file removed.")
            except (OSError, IOError):
                pass
    finally:
        if conn:
            conn.close()

def bulk_import_records(auth):
    """Bulk import health records from CSV"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to import records.")
        return
    
    print("\n===== Bulk Import Health Records =====")
    print("CSV format required: student_id,record_type,record_date,description,provider,confidential")
    print("Date format: YYYY-MM-DD")
    print("Confidential: true/false (optional, defaults to false)")
    
    filename = input("Enter CSV filename: ").strip()
    
    # Validate file exists and has .csv extension
    if not filename.endswith('.csv'):
        print("Error: File must have .csv extension.")
        return
    
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found.")
        return
    
    # Ask for confirmation
    print(f"\nAbout to import records from: {filename}")
    confirm = input("Continue? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Import cancelled.")
        return
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Start transaction
        conn.execute('BEGIN TRANSACTION')
        
        with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
            # Detect delimiter
            sample = csvfile.read(1024)
            csvfile.seek(0)
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            
            # Validate headers
            required_fields = ['student_id', 'record_type', 'record_date', 'description']
            optional_fields = ['provider', 'confidential']
            
            if not all(field in reader.fieldnames for field in required_fields):
                missing_fields = [field for field in required_fields if field not in reader.fieldnames]
                print(f"Error: Missing required columns: {', '.join(missing_fields)}")
                print(f"Found columns: {', '.join(reader.fieldnames)}")
                return
            
            imported_count = 0
            error_count = 0
            errors = []
            
            print("\nProcessing records...")
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 since header is row 1
                try:
                    # Clean and validate data
                    student_id = row['student_id'].strip()
                    record_type = row['record_type'].strip()
                    record_date = row['record_date'].strip()
                    description = row['description'].strip()
                    provider = row.get('provider', '').strip()
                    confidential_str = row.get('confidential', 'false').strip().lower()
                    
                    # Validate required fields are not empty
                    if not all([student_id, record_type, record_date, description]):
                        error_msg = f"Row {row_num}: Missing required data"
                        errors.append(error_msg)
                        error_count += 1
                        continue
                    
                    # Validate student exists
                    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
                    if cursor.fetchone()[0] == 0:
                        error_msg = f"Row {row_num}: Student ID '{student_id}' not found"
                        errors.append(error_msg)
                        error_count += 1
                        continue
                    
                    # Validate and parse date
                    try:
                        parsed_date = datetime.strptime(record_date, '%Y-%m-%d')
                        # Check if date is reasonable (not too far in future/past)
                        current_date = datetime.now()
                        if parsed_date.year < 1900 or parsed_date > current_date:
                            error_msg = f"Row {row_num}: Invalid date '{record_date}' - must be between 1900 and today"
                            errors.append(error_msg)
                            error_count += 1
                            continue
                    except ValueError:
                        error_msg = f"Row {row_num}: Invalid date format '{record_date}' - use YYYY-MM-DD"
                        errors.append(error_msg)
                        error_count += 1
                        continue
                    
                    # Validate record type (assuming there are valid types)
                    valid_record_types = ['medical_exam', 'vaccination', 'injury', 'illness', 'mental_health', 'other']
                    if record_type not in valid_record_types:
                        error_msg = f"Row {row_num}: Invalid record type '{record_type}'. Valid types: {', '.join(valid_record_types)}"
                        errors.append(error_msg)
                        error_count += 1
                        continue
                    
                    # Parse confidential flag
                    confidential = confidential_str in ['true', '1', 'yes', 'y']
                    
                    # Check for duplicate records
                    cursor.execute('''
                    SELECT COUNT(*) FROM health_records 
                    WHERE student_id = ? AND record_date = ? AND description = ?
                    ''', (student_id, record_date, description))
                    
                    if cursor.fetchone()[0] > 0:
                        error_msg = f"Row {row_num}: Duplicate record found for student {student_id} on {record_date}"
                        errors.append(error_msg)
                        error_count += 1
                        continue
                    
                    # Insert record
                    cursor.execute('''
                    INSERT INTO health_records 
                    (student_id, record_type, record_date, description, provider, confidential, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, record_type, record_date, description, provider, 
                          confidential, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    
                    imported_count += 1
                    
                    # Progress indicator
                    if imported_count % 100 == 0:
                        print(f"Processed {imported_count} records...")
                    
                except Exception as e:
                    error_msg = f"Row {row_num}: Unexpected error - {str(e)}"
                    errors.append(error_msg)
                    error_count += 1
        
        # Commit transaction if any records were imported
        if imported_count > 0:
            conn.commit()
            
            # Log audit event
            try:
                log_audit_event(
                    auth.current_user['id'], 
                    'bulk_import_records', 
                    'health_records', 
                    f"Imported {imported_count} records from {filename}"
                )
            except Exception as e:
                print(f"Warning: Could not log audit event: {e}")
            
            print(f"\n✅ Import completed successfully!")
        else:
            conn.rollback()
            print(f"\n❌ No records imported due to errors.")
        
        # Display results
        print(f"Records imported: {imported_count}")
        print(f"Errors encountered: {error_count}")
        
        # Show errors if any (limit to first 10 to avoid flooding)
        if errors:
            print(f"\nFirst {min(len(errors), 10)} errors:")
            for error in errors[:10]:
                print(f"  - {error}")
            
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more errors")
            
            # Offer to save error log
            save_errors = input("\nSave error log to file? (y/N): ").strip().lower()
            if save_errors == 'y':
                error_filename = f"import_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                try:
                    with open(error_filename, 'w') as error_file:
                        error_file.write(f"Import errors for {filename}\n")
                        error_file.write(f"Generated: {datetime.now()}\n\n")
                        for error in errors:
                            error_file.write(f"{error}\n")
                    print(f"Error log saved to: {error_filename}")
                except Exception as e:
                    print(f"Could not save error log: {e}")
    
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
    except PermissionError:
        print(f"Error: Permission denied accessing file '{filename}'.")
    except csv.Error as e:
        print(f"Error reading CSV file: {e}")
    except Exception as e:
        print(f"Unexpected error during import: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def preview_csv_import(filename, max_rows=5):
    """Preview CSV file contents before import"""
    try:
        is_valid, message = validate_csv_format(filename)
        if not is_valid:
            print(f"❌ Validation failed: {message}")
            return False
        
        print(f"✅ {message}")
        print(f"\n===== CSV Preview ({filename}) =====")
        
        with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
            # Detect delimiter
            sample = csvfile.read(1024)
            csvfile.seek(0)

            try:
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
            except (csv.Error, Exception):
                delimiter = ','
            
            reader = csv.DictReader(csvfile, delimiter=delimiter)
            
            # Show headers
            print(f"Columns found: {', '.join(reader.fieldnames)}")
            
            # Show sample data
            print(f"\nSample data (first {max_rows} rows):")
            print("-" * 80)
            
            row_count = 0
            for row in reader:
                row_count += 1
                if row_count > max_rows:
                    break
                
                print(f"Row {row_count}:")
                for field, value in row.items():
                    print(f"  {field}: {value}")
                print()
            
            # Count total rows
            csvfile.seek(0)
            total_rows = sum(1 for row in csv.DictReader(csvfile, delimiter=delimiter))
            print(f"Total data rows in file: {total_rows}")
        
        return True
        
    except Exception as e:
        print(f"Error previewing file: {e}")
        return False
