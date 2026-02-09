from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from university_system.infrastructure.shared_context import get_auth
import os
import re
import csv
import pandas as pd
import random
import json
import qrcode
import requests
from datetime import datetime, timedelta
from university_system.modules.shared.constants.paths import QR_CODES_DIR, BACKUP_DIR
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from university_system.infrastructure.email import (
    send_book_checkout_confirmation,
    send_book_return_reminder,
    send_overdue_notification,
)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import uuid
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns
import shutil
from typing import Any, List, Dict, Optional, Tuple
import logging
from university_system.utils.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def enhanced_system_backup():
    """Create comprehensive system backup"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text("library.backup.login_required"))
        return

    if not auth.check_permission('system_config'):
        print(get_text("library.backup.no_permission"))
        return

    print(f"\n{get_text('library.backup.title')}:")
    print("=" * 40)
    print(f"1. {get_text('library.backup.quick_backup')}")
    print(f"2. {get_text('library.backup.full_backup')}")
    print(f"3. {get_text('library.backup.scheduled_setup')}")
    print(f"4. {get_text('library.backup.restore')}")

    choice = input(f"{get_text('common.enter_choice')} (1-4): ").strip()
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = BACKUP_DIR / f"backup_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        if choice in ['1', '2']:
            # Create database backup
            db_backup_path = os.path.join(backup_dir, 'library_database.db')
            shutil.copy2(DATABASE_FILE, db_backup_path)
            print(f"✅ Database backed up to {db_backup_path}")
            
            if choice == '2':
                # Backup additional files
                file_dirs = ['qr_codes', 'digital_library', 'cover_images']
                
                for dir_name in file_dirs:
                    if os.path.exists(dir_name):
                        backup_subdir = os.path.join(backup_dir, dir_name)
                        shutil.copytree(dir_name, backup_subdir)
                        print(f"✅ {dir_name} backed up")
                
            # Create backup manifest
            manifest = {
                'backup_date': datetime.now().isoformat(),
                'backup_type': 'full',
                'created_by': get_current_user_id(),
                'database_size': os.path.getsize(db_backup_path),
                'includes': ['database', 'qr_codes', 'digital_library', 'cover_images']
            }
                
            with open(os.path.join(backup_dir, 'manifest.json'), 'w') as f:
                json.dump(manifest, f, indent=2)
            
            print(f"✅ Backup completed: {backup_dir}")
            
            # FIXED: Log the backup using get_current_user_id() helper function
            log_audit_event(get_current_user_id(), f"Created system backup: {backup_dir}", "system")
            
        elif choice == '3':
            # Setup scheduled backups
            setup_scheduled_backups()
                
        elif choice == '4':
            # Restore from backup
            restore_from_backup()
    
    except Exception as e:
        print(f"Error creating backup: {e}")
        logging.error(f"Backup error: {e}")


def backup_system():
    """Create system backup (calls enhanced version)"""
    enhanced_system_backup()


def auto_backup_scheduler():
   """Automated backup scheduler"""
   auth = get_auth()

   if not auth or not auth.current_user:
       print(get_text("library.backup.login_required"))
       return

   if not auth.check_permission('system_config'):
       print(get_text("library.backup.no_permission"))
       return

   print(f"\n{get_text('library.backup.scheduler_title')}:")
   print("=" * 40)

   # Check current backup settings
   auto_backup_enabled = get_library_settings('auto_backup') == 'true'
   backup_frequency = int(get_library_settings('backup_frequency_hours') or 24)

   status = get_text('common.active') if auto_backup_enabled else get_text('common.inactive')
   print(f"{get_text('library.backup.current_status')}: {status}")
   print(get_text('library.backup.frequency_display').format(hours=backup_frequency))

   print(f"\n{get_text('library.backup.options')}:")
   print(f"1. {get_text('library.backup.toggle_auto')}")
   print(f"2. {get_text('library.backup.change_frequency')}")
   print(f"3. {get_text('library.backup.set_retention')}")
   print(f"4. {get_text('library.backup.test_system')}")
   print(f"5. {get_text('library.backup.view_history')}")
   print(f"6. {get_text('common.return_to_menu')}")

   choice = input(f"{get_text('common.enter_choice')} (1-6): ").strip()
   
   try:
       if choice == '1':
           # Toggle auto backup
           new_status = 'false' if auto_backup_enabled else 'true'
           update_library_setting('auto_backup', new_status)
           
           status_text = 'enabled' if new_status == 'true' else 'disabled'
           print(f"✅ Auto backup {status_text}")
           
           if new_status == 'true':
               print("Note: You'll need to set up the actual scheduler in your system:")
               print("Linux/Mac: Add to crontab")
               print("Windows: Use Task Scheduler")
       
       elif choice == '2':
           # Change frequency
           print("Backup frequency options:")
           print("1. Every 6 hours")
           print("2. Every 12 hours") 
           print("3. Every 24 hours (daily)")
           print("4. Every 168 hours (weekly)")
           print("5. Custom")
           
           freq_choice = input("Select frequency (1-5): ").strip()
           
           frequencies = {'1': 6, '2': 12, '3': 24, '4': 168}
           
           if freq_choice in frequencies:
               new_frequency = frequencies[freq_choice]
           elif freq_choice == '5':
               new_frequency = int(input("Enter custom frequency in hours: "))
           else:
               print("Invalid choice.")
               return
           
           update_library_setting('backup_frequency_hours', str(new_frequency))
           print(f"✅ Backup frequency set to every {new_frequency} hours")
       
       elif choice == '3':
           # Backup retention policy
           print("Backup retention policies:")
           print("1. Keep last 7 backups")
           print("2. Keep last 14 backups")
           print("3. Keep last 30 backups")
           print("4. Keep backups for 90 days")
           print("5. Custom retention")
           
           retention_choice = input("Select retention policy (1-5): ").strip()
           
           retention_policies = {
               '1': 'count:7',
               '2': 'count:14', 
               '3': 'count:30',
               '4': 'days:90'
           }
           
           if retention_choice in retention_policies:
               policy = retention_policies[retention_choice]
           elif retention_choice == '5':
               policy = input("Enter custom policy (e.g., 'count:20' or 'days:60'): ")
           else:
               print("Invalid choice.")
               return
           
           update_library_setting('backup_retention_policy', policy)
           print(f"✅ Backup retention policy set to: {policy}")
       
       elif choice == '4':
           # Test backup
           print("Testing backup system...")
           
           if enhanced_system_backup():
               print("✅ Backup test successful!")
           else:
               print("❌ Backup test failed!")
       
       elif choice == '5':
           # View backup history
           backup_dir = "backups"
           
           if os.path.exists(backup_dir):
               backups = []
               
               for item in os.listdir(backup_dir):
                   backup_path = os.path.join(backup_dir, item)
                   if os.path.isdir(backup_path):
                       try:
                           stat = os.stat(backup_path)
                           size = sum(os.path.getsize(os.path.join(backup_path, f)) 
                                    for f in os.listdir(backup_path) 
                                    if os.path.isfile(os.path.join(backup_path, f)))
                           
                           backups.append({
                               'name': item,
                               'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                               'size': size
                           })
                       except (OSError, IOError, ValueError) as e:
                           logger.warning(f"Failed to process backup {item}: {e}")
                           continue
               
               if backups:
                   backups.sort(key=lambda x: x['created'], reverse=True)
                   
                   print(f"\nBackup History ({len(backups)} backups):")
                   print("-" * 70)
                   print(f"{'Backup Name':<25} {'Created':<20} {'Size':<15}")
                   print("-" * 70)
                   
                   for backup in backups:
                       size_mb = backup['size'] / (1024 * 1024)
                       print(f"{backup['name']:<25} {backup['created']:<20} {size_mb:.1f} MB")
                   
                   print("-" * 70)
               else:
                   print("No backups found.")
           else:
               print("Backup directory not found.")
       
       log_audit_event(get_current_user_id(), f"Modified auto backup settings: choice {choice}", "system")
   
   except Exception as e:
       print(f"Error managing auto backup: {e}")


def setup_scheduled_backups():
    """Setup scheduled backup configuration"""
    print("\nScheduled Backup Setup:")
    print("======================")
    print("This feature would integrate with your system's task scheduler.")
    print("For implementation, you would:")
    print("1. Create a backup script")
    print("2. Configure cron job (Linux/Mac) or Task Scheduler (Windows)")
    print("3. Set up backup rotation and cleanup")
    print("4. Configure backup monitoring and alerts")
    
    # Example backup script creation
    backup_script = f'''#!/bin/bash
# Library System Backup Script
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/backup_$DATE"

mkdir -p "$BACKUP_PATH"

# Backup database
cp {DATABASE_FILE} "$BACKUP_PATH/"

# Backup additional files
cp -r qr_codes "$BACKUP_PATH/" 2>/dev/null || true
cp -r digital_library "$BACKUP_PATH/" 2>/dev/null || true
cp -r cover_images "$BACKUP_PATH/" 2>/dev/null || true

# Create manifest
echo "{{
    \\"backup_date\\": \\"$(date -Iseconds)\\",
    \\"backup_type\\": \\"scheduled\\",
    \\"automated\\": true
}}" > "$BACKUP_PATH/manifest.json"

# Cleanup old backups (keep last 7 days)
find "$BACKUP_DIR" -name "backup_*" -type d -mtime +7 -exec rm -rf {{}} \\;

echo "Backup completed: $BACKUP_PATH"
'''
    
    script_filename = "library_backup.sh"
    with open(script_filename, 'w') as f:
        f.write(backup_script)
    
    print(f"✅ Backup script created: {script_filename}")
    print("To schedule this backup:")
    print("Linux/Mac: Add to crontab with 'crontab -e'")
    print("Example: 0 2 * * * /path/to/library_backup.sh  # Daily at 2 AM")
    print("Windows: Use Task Scheduler to run the script")


def restore_from_backup():
    """Restore system from backup"""
    print("\nRestore from Backup:")
    print("===================")
    print("⚠️  WARNING: This will overwrite current data!")
    
    # List available backups
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        print("No backup directory found.")
        return
    
    backups = []
    for item in os.listdir(backup_dir):
        backup_path = os.path.join(backup_dir, item)
        if os.path.isdir(backup_path) and item.startswith("backup_"):
            manifest_path = os.path.join(backup_path, "manifest.json")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    backups.append((item, backup_path, manifest))
                except (OSError, IOError, json.JSONDecodeError) as e:
                    logger.warning(f"Failed to load manifest for {item}: {e}")
                    backups.append((item, backup_path, {}))
    
    if not backups:
        print("No valid backups found.")
        return
    
    backups.sort(key=lambda x: x[0], reverse=True)
    
    print("Available Backups:")
    for i, (name, path, manifest) in enumerate(backups, 1):
        backup_date = manifest.get('backup_date', 'Unknown')
        backup_type = manifest.get('backup_type', 'Unknown')
        print(f"{i}. {name} - {backup_date} ({backup_type})")
    
    try:
        choice = int(input("Select backup to restore (0 to cancel): "))
        
        if choice == 0:
            print("Restore cancelled.")
            return
        
        if 1 <= choice <= len(backups):
            selected_backup = backups[choice - 1]
            backup_name, backup_path, manifest = selected_backup
            
            print(f"\nSelected backup: {backup_name}")
            confirm = input("Type 'RESTORE' to confirm: ").strip()
            
            if confirm != 'RESTORE':
                print("Restore cancelled.")
                return
            
            # Create current backup before restore
            print("Creating safety backup of current data...")
            safety_backup_dir = BACKUP_DIR / f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            safety_backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DATABASE_FILE, safety_backup_dir)
            
            # Restore database
            backup_db_path = os.path.join(backup_path, 'library_database.db')
            if os.path.exists(backup_db_path):
                shutil.copy2(backup_db_path, DATABASE_FILE)
                print("✅ Database restored")
            
            # Restore additional files
            for dir_name in ['qr_codes', 'digital_library', 'cover_images']:
                backup_subdir = os.path.join(backup_path, dir_name)
                if os.path.exists(backup_subdir):
                    if os.path.exists(dir_name):
                        shutil.rmtree(dir_name)
                    shutil.copytree(backup_subdir, dir_name)
                    print(f"✅ {dir_name} restored")
            
            print(f"✅ System restored from backup: {backup_name}")
            print(f"Safety backup created at: {safety_backup_dir}")
            
        else:
            print("Invalid selection.")
    
    except ValueError:
        print("Invalid input.")
    except Exception as e:
        print(f"Error during restore: {e}")


def library_maintenance():
    """Perform library maintenance tasks"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to perform maintenance.")
        return
    
    if not auth.check_permission('system_config'):
        print("You don't have permission to perform maintenance.")
        return
    
    print("\nLibrary Maintenance:")
    print("===================")
    print("1. Clean up expired reservations")
    print("2. Update overdue status")
    print("3. Calculate fines")
    print("4. Archive old loan records")
    print("5. Optimize database")
    print("6. Check data integrity")
    print("7. Return to menu")
    
    choice = input("Enter your choice (1-7): ").strip()
    
    if choice == '7':
        return
    
    conn = get_db_connection()
    if not conn:
        return
        
    cursor = conn.cursor()
    
    try:
        if choice == '1':
            # Clean expired reservations
            cursor.execute('''
            UPDATE book_reservations 
            SET status = 'expired'
            WHERE status = 'active' AND expiry_date < datetime('now')
            ''')
            
            expired_count = cursor.rowcount
            conn.commit()
            print(f"✅ Cleaned up {expired_count} expired reservations.")
            
        elif choice == '2':
            # Update overdue status
            cursor.execute('''
            UPDATE book_loans 
            SET status = 'overdue'
            WHERE status = 'active' AND due_date < datetime('now')
            ''')
            
            overdue_count = cursor.rowcount
            conn.commit()
            print(f"✅ Updated {overdue_count} loans to overdue status.")
            
        elif choice == '3':
            # Calculate fines
            fine_per_day = float(get_library_settings('fine_per_day') or 0.50)
            
            cursor.execute('''
            UPDATE book_loans 
            SET fine_amount = (julianday('now') - julianday(due_date)) * ?
            WHERE status = 'overdue' AND due_date < datetime('now')
            ''', (fine_per_day,))
            
            fine_count = cursor.rowcount
            conn.commit()
            print(f"✅ Updated fines for {fine_count} overdue loans.")
            
        elif choice == '4':
            # Archive old records (placeholder)
            print("Archive functionality would move old completed loans to archive table.")
            print("This helps maintain performance for active queries.")
            
        elif choice == '5':
            # Optimize database
            cursor.execute('VACUUM')
            cursor.execute('ANALYZE')
            print("✅ Database optimized.")
            
        elif choice == '6':
            # Check data integrity
            validation_results = validate_library_configuration(cursor)
            
            print("\nData Integrity Check:")
            print("-" * 30)
            for result in validation_results:
                status = "✅" if result['valid'] else "❌"
                print(f"{status} {result['check']}: {result['message']}")
        
        # FIXED: Log maintenance action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Performed maintenance task: {choice}", "system")        
    except sqlite3.Error as e:
        print(f"Error during maintenance: {e}")
    
    conn.close()


def cleanup_old_logs():
   """Clean up old log files"""
   auth = get_auth()

   if not auth or not auth.current_user:
       print("You must be logged in to cleanup logs.")
       return
   
   if not auth.check_permission('system_config'):
       print("You don't have permission to cleanup logs.")
       return
   
   print("\nLog Cleanup Utility:")
   print("===================")
   
   try:
       # Define log retention periods
       retention_periods = {
           'audit_log': 90,      # Keep audit logs for 90 days
           'system_logs': 30,    # Keep system logs for 30 days
           'access_logs': 14,    # Keep access logs for 14 days
           'error_logs': 60      # Keep error logs for 60 days
       }
       
       conn = get_db_connection()
       cursor = conn.cursor()
       
       cleanup_summary = {}
       
       # Clean up database logs
       print("Cleaning up database logs...")
       
       # Clean old audit log entries
       cutoff_date = (datetime.now() - timedelta(days=retention_periods['audit_log'])).strftime('%Y-%m-%d')
       
       cursor.execute('SELECT COUNT(*) FROM audit_log WHERE timestamp < ?', (cutoff_date,))
       old_audit_count = cursor.fetchone()[0]
       
       if old_audit_count > 0:
           cursor.execute('DELETE FROM audit_log WHERE timestamp < ?', (cutoff_date,))
           cleanup_summary['audit_log'] = old_audit_count
       
       # Clean old notifications
       notification_cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
       
       cursor.execute('SELECT COUNT(*) FROM notification_queue WHERE sent = 1 AND created_date < ?', (notification_cutoff,))
       old_notification_count = cursor.fetchone()[0]
       
       if old_notification_count > 0:
           cursor.execute('DELETE FROM notification_queue WHERE sent = 1 AND created_date < ?', (notification_cutoff,))
           cleanup_summary['notifications'] = old_notification_count
       
       # Clean old analytics data (keep last 6 months)
       analytics_cutoff = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
       
       cursor.execute('SELECT COUNT(*) FROM usage_analytics WHERE date < ?', (analytics_cutoff,))
       old_analytics_count = cursor.fetchone()[0]
       
       if old_analytics_count > 0:
           cursor.execute('DELETE FROM usage_analytics WHERE date < ?', (analytics_cutoff,))
           cleanup_summary['analytics'] = old_analytics_count
       
       # Clean expired reservations
       cursor.execute('SELECT COUNT(*) FROM book_reservations WHERE status = "expired"')
       expired_reservations = cursor.fetchone()[0]
       
       if expired_reservations > 100:  # Keep some for analysis
           cursor.execute('''
           DELETE FROM book_reservations 
           WHERE status = "expired" 
           AND expiry_date < date('now', '-90 days')
           ''')
           cleanup_summary['expired_reservations'] = cursor.rowcount
       
       conn.commit()
       
       # Clean up log files
       print("Cleaning up log files...")
       
       log_directories = ['logs', 'audit_logs', 'error_logs']
       files_cleaned = 0
       
       for log_dir in log_directories:
           if os.path.exists(log_dir):
               for filename in os.listdir(log_dir):
                   file_path = os.path.join(log_dir, filename)
                   
                   if os.path.isfile(file_path):
                       # Check file age
                       file_age_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))).days
                       
                       # Determine retention period based on file type
                       retention_days = 30  # Default
                       
                       if 'audit' in filename.lower():
                           retention_days = retention_periods['audit_log']
                       elif 'error' in filename.lower():
                           retention_days = retention_periods['error_logs']
                       elif 'access' in filename.lower():
                           retention_days = retention_periods['access_logs']
                       
                       if file_age_days > retention_days:
                           try:
                               os.remove(file_path)
                               files_cleaned += 1
                           except OSError:
                               pass
       
       cleanup_summary['log_files'] = files_cleaned
       
       # Optimize database
       print("Optimizing database...")
       cursor.execute('VACUUM')
       cursor.execute('ANALYZE')
       
       conn.close()
       
       # Display cleanup summary
       print("\n✅ Log cleanup completed!")
       print("Cleanup Summary:")
       print("-" * 30)
       
       for category, count in cleanup_summary.items():
           print(f"{category.replace('_', ' ').title()}: {count} items removed")
       
       if not cleanup_summary:
           print("No old logs found to clean up.")
       
       log_audit_event(get_current_user_id(), 
                      f"Performed log cleanup - removed {sum(cleanup_summary.values())} items",
                      "system")
       
   except Exception as e:
       logging.error(f"Error during log cleanup: {e}")
       print(f"Error during cleanup: {e}")


def quick_system_health_check():
   """Perform quick system health check"""
   print("\nQuick System Health Check:")
   print("=========================")
   
   health_status = []
   
   try:
       # Database connectivity
       conn = get_db_connection()
       if conn:
           cursor = conn.cursor()
           cursor.execute('SELECT COUNT(*) FROM books')
           health_status.append(("Database Connection", "✅ OK"))
           
           # Check for corrupted data
           cursor.execute('PRAGMA integrity_check')
           integrity = cursor.fetchone()[0]
           
           if integrity == 'ok':
               health_status.append(("Database Integrity", "✅ OK"))
           else:
               health_status.append(("Database Integrity", f"❌ {integrity}"))
           
           # Check overdue items
           cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
           overdue_count = cursor.fetchone()[0]
           
           if overdue_count == 0:
               health_status.append(("Overdue Items", "✅ None"))
           elif overdue_count < 10:
               health_status.append(("Overdue Items", f"⚠️  {overdue_count} items"))
           else:
               health_status.append(("Overdue Items", f"❌ {overdue_count} items"))
           
           # Check system errors
           cursor.execute('''
           SELECT COUNT(*) FROM audit_log 
           WHERE success = 0 AND timestamp >= datetime('now', '-24 hours')
           ''')
           error_count = cursor.fetchone()[0]
           
           if error_count == 0:
               health_status.append(("System Errors (24h)", "✅ None"))
           elif error_count < 5:
               health_status.append(("System Errors (24h)", f"⚠️  {error_count} errors"))
           else:
               health_status.append(("System Errors (24h)", f"❌ {error_count} errors"))
           
           conn.close()
       else:
           health_status.append(("Database Connection", "❌ Failed"))
       
       # File system checks
       important_dirs = ['backups', 'qr_codes', 'digital_library']
       
       for directory in important_dirs:
           if os.path.exists(directory):
               health_status.append((f"{directory.title()} Directory", "✅ Exists"))
           else:
               health_status.append((f"{directory.title()} Directory", "⚠️  Missing"))
       
       # Display results
       print("\nHealth Check Results:")
       print("-" * 40)
       
       for check, status in health_status:
           print(f"{check:<25} {status}")
       
       print("-" * 40)
       
       # Overall health assessment
       error_count = len([s for _, s in health_status if s.startswith("❌")])
       warning_count = len([s for _, s in health_status if s.startswith("⚠️")])
       
       if error_count == 0 and warning_count == 0:
           print("Overall Status: ✅ HEALTHY")
       elif error_count == 0:
           print("Overall Status: ⚠️  WARNINGS")
       else:
           print("Overall Status: ❌ ISSUES DETECTED")
       
   except Exception as e:
       print(f"Health check failed: {e}")


def view_audit_log():
    """View system audit log"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to view audit logs.")
        return
    
    if not auth.check_permission('system_config'):
        print("You don't have permission to view audit logs.")
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("\nAudit Log Viewer:")
    print("================")
    print("1. Recent Activities (Last 24 hours)")
    print("2. User Activities")
    print("3. Failed Operations")
    print("4. System Changes")
    print("5. Custom Date Range")
    
    choice = input("Select view option (1-5): ").strip()
    
    try:
        if choice == '1':
            # Recent activities
            cursor.execute('''
            SELECT user_id, action, table_affected, timestamp, success
            FROM audit_log
            WHERE timestamp >= datetime('now', '-1 day')
            ORDER BY timestamp DESC
            LIMIT 50
            ''')
            
            title = "Recent Activities (Last 24 hours)"
            
        elif choice == '2':
            # User activities
            user_id = input("Enter User ID: ").strip()
            
            cursor.execute('''
            SELECT action, table_affected, record_id, timestamp, success
            FROM audit_log
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 50
            ''', (user_id,))
            
            title = f"Activities for User: {user_id}"
            
        elif choice == '3':
            # Failed operations
            cursor.execute('''
            SELECT user_id, action, table_affected, timestamp
            FROM audit_log
            WHERE success = 0
            ORDER BY timestamp DESC
            LIMIT 50
            ''')
            
            title = "Failed Operations"
            
        elif choice == '4':
            # System changes
            cursor.execute('''
            SELECT user_id, action, table_affected, old_values, new_values, timestamp
            FROM audit_log
            WHERE table_affected IN ('library_settings', 'system')
            ORDER BY timestamp DESC
            LIMIT 50
            ''')
            
            title = "System Changes"
            
        elif choice == '5':
            # Custom date range
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            
            cursor.execute('''
            SELECT user_id, action, table_affected, timestamp, success
            FROM audit_log
            WHERE date(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp DESC
            LIMIT 100
            ''', (start_date, end_date))
            
            title = f"Audit Log ({start_date} to {end_date})"
        
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        activities = cursor.fetchall()
        
        if not activities:
            print("No audit records found.")
            conn.close()
            return
        
        print(f"\n{title}")
        print("=" * 80)
        print(f"{'User ID':<12} {'Action':<25} {'Table':<15} {'Timestamp':<20} {'Status':<8}")
        print("-" * 80)
        
        for activity in activities:
            if len(activity) >= 5:
                user_id, action, table, timestamp, success = activity[:5]
                status = "✅" if success else "❌"
                action_display = action[:24] if len(action) > 25 else action
                table_display = table[:14] if table and len(table) > 15 else (table or "N/A")
                
                print(f"{user_id:<12} {action_display:<25} {table_display:<15} {timestamp[:19]:<20} {status:<8}")
            else:
                # Handle different query result formats
                print(f"{str(activity)}")
        
        print("=" * 80)
        print(f"Total records: {len(activities)}")
    
    except sqlite3.Error as e:
        print(f"Error viewing audit log: {e}")
    
    conn.close()


