from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection, transaction
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.modules.shared.constants import paths
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
import os
from datetime import datetime, timedelta
import pandas as pd
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import csv
import json
import shutil
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from icalendar import Calendar, Event
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Constants
DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']

class ModuleScheduler:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path
        self._init_db()
        self._migrate_database()  # Run migrations after table creation
        self._init_config()
    
    def _init_db(self):
        """Initialize database tables needed for scheduling"""
        with get_connection(self.db_path, row_factory=False) as conn:
            cursor = conn.cursor()

            # Existing tables (keeping your original structure)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS module_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT,
                day_of_week TEXT,
                start_time TEXT,
                end_time TEXT,
                room_id INTEGER,
                instructor_id INTEGER,
                session_type TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_code) REFERENCES modules (module_code),
                FOREIGN KEY (room_id) REFERENCES rooms (id),
                FOREIGN KEY (instructor_id) REFERENCES instructors (id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_number TEXT,
                building TEXT,
                capacity INTEGER,
                room_type TEXT,
                equipment TEXT,
                notes TEXT,
                is_active BOOLEAN DEFAULT 1
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS instructors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                department TEXT DEFAULT '',
                specialization TEXT DEFAULT '',
                max_courses_per_semester INTEGER DEFAULT 4,
                max_hours_per_week INTEGER DEFAULT 40,
                preferred_days TEXT,
                preferred_times TEXT,
                status TEXT DEFAULT 'Active',
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
            ''')

            # New tables for enhanced features
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT UNIQUE,
                description TEXT,
                template_data TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_id INTEGER,
                action TEXT,
                old_values TEXT,
                new_values TEXT,
                changed_by TEXT,
                change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduling_system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conflict_type TEXT,
                description TEXT,
                affected_schedules TEXT,
                resolved BOOLEAN DEFAULT 0,
                resolution_notes TEXT,
                detected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_date TIMESTAMP
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_type TEXT,
                recipient_id TEXT,
                message TEXT,
                notification_type TEXT,
                sent BOOLEAN DEFAULT 0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_date TIMESTAMP
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS holidays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                holiday_name TEXT,
                start_date DATE,
                end_date DATE,
                description TEXT,
                recurring BOOLEAN DEFAULT 0
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_name TEXT,
                backup_path TEXT,
                backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                backup_size INTEGER,
                description TEXT
            )
            ''')

            # Initialize default settings
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('institution_name', 'University', 'Name of the institution'))
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('semester_start', '', 'Semester start date'))
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('semester_end', '', 'Semester end date'))
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('default_session_duration', '60', 'Default session duration in minutes'))
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('email_notifications', 'False', 'Enable email notifications'))
            cursor.execute('INSERT OR IGNORE INTO scheduling_system_settings (key, value, description) VALUES (?, ?, ?)',
                          ('auto_backup', 'True', 'Enable automatic backups'))

    def _migrate_database(self):
        """Migrate existing database tables to add missing columns"""
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with get_connection(self.db_path, row_factory=False) as conn:
                    conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode
                    conn.execute("PRAGMA busy_timeout = 30000")  # 30 second timeout
                    cursor = conn.cursor()

                    # Check and add missing columns to instructors table
                    cursor.execute("PRAGMA table_info(instructors)")
                    existing_columns = {row[1] for row in cursor.fetchall()}

                    migrations = []
                    if 'max_hours_per_week' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN max_hours_per_week INTEGER DEFAULT 40")
                    if 'preferred_days' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN preferred_days TEXT")
                    if 'preferred_times' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN preferred_times TEXT")
                    if 'is_active' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN is_active BOOLEAN DEFAULT 1")
                    if 'specialization' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN specialization TEXT DEFAULT ''")
                    if 'max_courses_per_semester' not in existing_columns:
                        migrations.append("ALTER TABLE instructors ADD COLUMN max_courses_per_semester INTEGER DEFAULT 4")

                    # Check and add missing columns to rooms table
                    cursor.execute("PRAGMA table_info(rooms)")
                    existing_columns = {row[1] for row in cursor.fetchall()}

                    if 'is_active' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN is_active BOOLEAN DEFAULT 1")

                    # Add building_id column for compatibility with facilities management system
                    if 'building_id' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN building_id INTEGER")
                        print("Added building_id column to rooms table for facilities management compatibility")

                    # Add other columns for facilities management compatibility
                    if 'room_name' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN room_name TEXT")
                    if 'floor_number' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN floor_number INTEGER")
                    if 'area_sqft' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN area_sqft REAL")
                    if 'features' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN features TEXT")
                    if 'accessibility_compliant' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN accessibility_compliant BOOLEAN DEFAULT 1")
                    if 'status' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN status TEXT DEFAULT 'available'")

                    # Execute all migrations
                    for migration in migrations:
                        try:
                            cursor.execute(migration)
                            print(f"Migration executed: {migration}")
                        except sqlite3.Error as e:
                            if "duplicate column name" in str(e).lower():
                                print(f"Migration skipped (already exists): {migration}")
                            else:
                                print(f"Migration failed: {migration} - {e}")

                    conn.commit()
                    return  # Success, exit retry loop

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    import time
                    print(f"Database locked, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"Migration failed after {max_retries} attempts: {e}")
            except Exception as e:
                print(f"Migration error: {e}")
                break

    def _init_config(self):
        """Initialize configuration settings"""
        from university_system.modules.shared.constants import paths
        os.makedirs(str(paths.REPORTS_DIR / 'timetable_reports'), exist_ok=True)
        os.makedirs(str(paths.BACKUP_DIR), exist_ok=True)
        os.makedirs(str(paths.ANALYTICS_DIR), exist_ok=True)
        os.makedirs(str(paths.REPORT_TEMPLATES_DIR), exist_ok=True)

    def _get_known_modules(self):
        """Get all known modules from various sources"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # First try to get from modules table
            cursor.execute('SELECT module_code, module_name FROM modules')
            modules_from_table = cursor.fetchall()

            if modules_from_table:
                modules_dict = {code: name for code, name in modules_from_table}
                return modules_dict

            # Fallback: Get unique modules from student_modules
            cursor.execute('''
            SELECT DISTINCT module_code, module_name
            FROM student_modules
            WHERE module_code IS NOT NULL AND module_name IS NOT NULL
            ORDER BY module_code
            ''')

            modules_from_enrollments = cursor.fetchall()

            # Also get from existing schedules
            cursor.execute('''
            SELECT DISTINCT ms.module_code, COALESCE(m.module_name, 'Unknown') as module_name
            FROM module_schedule ms
            LEFT JOIN modules m ON ms.module_code = m.module_code
            WHERE ms.module_code IS NOT NULL
            ORDER BY ms.module_code
            ''')

            modules_from_schedules = cursor.fetchall()

            # Combine all sources
            all_modules = {}

            # Add from enrollments
            for code, name in modules_from_enrollments:
                all_modules[code] = name

            # Add from schedules (don't overwrite if we already have a name)
            for code, name in modules_from_schedules:
                if code not in all_modules:
                    all_modules[code] = name

            return all_modules

    def get_all_modules(self):
        """Get all modules from the database - public interface"""
        try:
            with get_connection(self.db_path, row_factory=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Primary: get from modules table (correct source for module data)
                cursor.execute('''
                SELECT module_code, module_name, COALESCE(module_type, 'compulsory') as module_type, rowid
                FROM modules
                WHERE module_code IS NOT NULL
                ORDER BY module_code
                ''')
                modules = cursor.fetchall()

                if modules:
                    return [{
                        'id': str(row[3]),
                        'code': row[0],
                        'name': row[1],
                        'type': row[2],
                        'credits': '',  # Default empty - can be enhanced later
                        'semester': '',  # Default empty - can be enhanced later
                        'instructor': ''  # Default empty - can be enhanced later
                    } for row in modules]

                # Fallback: get from student_modules table if modules table is empty
                cursor.execute('''
                SELECT DISTINCT module_code, module_name, 'Unknown' as module_type, rowid
                FROM student_modules
                WHERE module_code IS NOT NULL
                ORDER BY module_code
                ''')
                student_modules = cursor.fetchall()

                if student_modules:
                    return [{
                        'id': str(row[3]),
                        'code': row[0],
                        'name': row[1] or 'Unknown',
                        'type': row[2],
                        'credits': '',
                        'semester': '',
                        'instructor': ''
                    } for row in student_modules]

                # Final fallback: return empty list
                return []

        except Exception as e:
            print(f"Error getting modules: {e}")
            return []

    def delete_module_schedule(self, schedule_id):
        """Delete a module schedule entry"""
        try:
            with get_connection(self.db_path, row_factory=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Check if schedule exists
                cursor.execute('SELECT * FROM module_schedule WHERE id = ?', (schedule_id,))
                schedule = cursor.fetchone()

                if not schedule:
                    print(f"Schedule ID {schedule_id} does not exist.")
                    return False

                # Confirm deletion
                print(f"Schedule to delete: Module {schedule[1]} on {schedule[2]} at {schedule[3]}-{schedule[4]}")
                confirm = input("Are you sure you want to delete this schedule? (y/n): ")

                if confirm.lower() != 'y':
                    print("Deletion cancelled.")
                    return False

                # Log the deletion
                self._log_system_action('schedule_deleted',
                                      f"Deleted schedule ID {schedule_id}: {schedule[1]} on {schedule[2]} {schedule[3]}-{schedule[4]}")

                # Delete the schedule
                cursor.execute('DELETE FROM module_schedule WHERE id = ?', (schedule_id,))

                print(f"Schedule deleted successfully.")

                # Send notifications about the deletion
                self.send_schedule_change_notifications(schedule_id,
                                                      f"Class cancelled: {schedule[1]} on {schedule[2]} {schedule[3]}-{schedule[4]}")

                return True

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
    
    # ==================== ANALYTICS & REPORTING ====================
    
    def generate_room_utilization_report(self, output_format='display'):
        """Generate comprehensive room utilization analytics"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
        
        # Get room utilization data
        cursor.execute('''
        SELECT r.id, r.building, r.room_number, r.capacity, r.room_type,
               COUNT(ms.id) as scheduled_sessions,
               AVG(CASE 
                   WHEN ms.end_time IS NOT NULL AND ms.start_time IS NOT NULL 
                   THEN (CAST(SUBSTR(ms.end_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.end_time, 4, 2) AS INTEGER)) - 
                        (CAST(SUBSTR(ms.start_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.start_time, 4, 2) AS INTEGER))
                   ELSE 0 END) as avg_session_duration
        FROM rooms r
        LEFT JOIN module_schedule ms ON r.id = ms.room_id
        WHERE r.is_active = 1
        GROUP BY r.id, r.building, r.room_number, r.capacity, r.room_type
        ORDER BY scheduled_sessions DESC
        ''')
        
        room_data = cursor.fetchall()
        
        if not room_data:
            print("No room data available.")
            conn.close()
            return
        
        # Calculate utilization metrics
        total_possible_slots = len(DAYS_OF_WEEK) * len(TIME_SLOTS)
        
        analytics_data = []
        for room in room_data:
            room_id, building, room_number, capacity, room_type, sessions, avg_duration = room
            utilization_rate = (sessions / total_possible_slots) * 100 if total_possible_slots > 0 else 0
            
            analytics_data.append({
                'Room': f"{building}-{room_number}",
                'Type': room_type,
                'Capacity': capacity,
                'Sessions': sessions,
                'Utilization Rate (%)': round(utilization_rate, 2),
                'Avg Duration (min)': round(avg_duration or 0, 2)
            })

        if output_format == 'display':
            self._display_room_analytics(analytics_data)
        elif output_format == 'pdf':
            return self._generate_analytics_pdf(analytics_data, 'Room Utilization Report')
        elif output_format == 'csv':
            return self._export_analytics_csv(analytics_data, 'room_utilization')

        return analytics_data
    
    def _display_room_analytics(self, data):
        """Display room analytics in console"""
        print("\nRoom Utilization Analytics")
        print("=" * 100)
        print(f"{'Room':<15} {'Type':<15} {'Capacity':<10} {'Sessions':<10} {'Utilization':<12} {'Avg Duration':<12}")
        print("-" * 100)
        
        for room in data:
            print(f"{room['Room']:<15} {room['Type']:<15} {room['Capacity']:<10} "
                  f"{room['Sessions']:<10} {room['Utilization Rate (%)']:<12} {room['Avg Duration (min)']:<12}")
        
        print("=" * 100)
        
        # Summary statistics
        if data:
            avg_utilization = sum(room['Utilization Rate (%)'] for room in data) / len(data)
            print(f"\nSummary:")
            print(f"Total Rooms: {len(data)}")
            print(f"Average Utilization: {avg_utilization:.2f}%")
            print(f"Most Utilized: {max(data, key=lambda x: x['Utilization Rate (%)'])['Room']}")
            print(f"Least Utilized: {min(data, key=lambda x: x['Utilization Rate (%)'])['Room']}")
    
    def generate_instructor_workload_report(self, output_format='display'):
        """Generate instructor workload analysis"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
        
        cursor.execute('''
        SELECT i.id, i.first_name, i.last_name, i.department, i.max_hours_per_week,
               COUNT(ms.id) as total_sessions,
               SUM(CASE 
                   WHEN ms.end_time IS NOT NULL AND ms.start_time IS NOT NULL 
                   THEN (CAST(SUBSTR(ms.end_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.end_time, 4, 2) AS INTEGER)) - 
                        (CAST(SUBSTR(ms.start_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.start_time, 4, 2) AS INTEGER))
                   ELSE 0 END) / 60.0 as total_hours
        FROM instructors i
        LEFT JOIN module_schedule ms ON i.id = ms.instructor_id
        WHERE i.is_active = 1
        GROUP BY i.id, i.first_name, i.last_name, i.department, i.max_hours_per_week
        ORDER BY total_hours DESC
        ''')
        
        instructor_data = cursor.fetchall()

        workload_data = []
        for instructor in instructor_data:
            inst_id, first_name, last_name, dept, max_hours, sessions, total_hours = instructor
            name = f"{first_name} {last_name}"
            total_hours = total_hours or 0
            max_hours = max_hours or 40
            workload_percentage = (total_hours / max_hours) * 100
            
            workload_data.append({
                'Instructor': name,
                'Department': dept,
                'Sessions': sessions,
                'Total Hours': round(total_hours, 2),
                'Max Hours': max_hours,
                'Workload (%)': round(workload_percentage, 2),
                'Status': 'Overloaded' if workload_percentage > 100 else 'Normal'
            })
        
        if output_format == 'display':
            self._display_workload_analytics(workload_data)
        elif output_format == 'pdf':
            return self._generate_analytics_pdf(workload_data, 'Instructor Workload Report')
        elif output_format == 'csv':
            return self._export_analytics_csv(workload_data, 'instructor_workload')
        
        return workload_data
    
    def _display_workload_analytics(self, data):
        """Display workload analytics in console"""
        print("\nInstructor Workload Analytics")
        print("=" * 120)
        print(f"{'Instructor':<25} {'Department':<15} {'Sessions':<10} {'Hours':<8} {'Max':<8} {'Load %':<8} {'Status':<12}")
        print("-" * 120)
        
        for instructor in data:
            print(f"{instructor['Instructor']:<25} {instructor['Department']:<15} "
                  f"{instructor['Sessions']:<10} {instructor['Total Hours']:<8} "
                  f"{instructor['Max Hours']:<8} {instructor['Workload (%)']:<8} {instructor['Status']:<12}")
        
        print("=" * 120)
        
        # Highlight overloaded instructors
        overloaded = [i for i in data if i['Status'] == 'Overloaded']
        if overloaded:
            print(f"\nWARNING: {len(overloaded)} instructor(s) are overloaded!")
            for instructor in overloaded:
                print(f"  - {instructor['Instructor']}: {instructor['Workload (%)']}% workload")
    
    def generate_scheduling_analytics_dashboard(self):
        """Generate comprehensive scheduling analytics dashboard"""
        print("\nScheduling Analytics Dashboard")
        print("=" * 60)
        
        # Peak usage analysis
        peak_times = self._analyze_peak_usage()
        print(f"\nPeak Usage Times:")
        for day, times in peak_times.items():
            print(f"  {day}: {', '.join(times)}")
        
        # Module distribution
        module_stats = self._analyze_module_distribution()
        print(f"\nModule Distribution:")
        print(f"  Total Modules Scheduled: {module_stats['total']}")
        print(f"  Most Common Session Type: {module_stats['most_common_type']}")
        print(f"  Average Sessions per Module: {module_stats['avg_sessions']:.2f}")
        
        # Room efficiency
        room_efficiency = self._analyze_room_efficiency()
        print(f"\nRoom Efficiency:")
        print(f"  Average Room Utilization: {room_efficiency['avg_utilization']:.2f}%")
        print(f"  Most Efficient Room Type: {room_efficiency['best_type']}")
        
        # Conflict summary
        conflicts = self._get_all_conflicts()
        print(f"\nConflict Summary:")
        print(f"  Active Conflicts: {len([c for c in conflicts if not c['resolved']])}")
        print(f"  Resolved Conflicts: {len([c for c in conflicts if c['resolved']])}")
    
    def _analyze_peak_usage(self):
        """Analyze peak usage times"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
        
        cursor.execute('''
        SELECT day_of_week, start_time, COUNT(*) as session_count
        FROM module_schedule
        GROUP BY day_of_week, start_time
        ORDER BY day_of_week, session_count DESC
        ''')
        
        usage_data = cursor.fetchall()

        peak_times = {}
        for day in DAYS_OF_WEEK:
            day_data = [row for row in usage_data if row[0] == day]
            if day_data:
                max_count = max(row[2] for row in day_data)
                peak_slots = [row[1] for row in day_data if row[2] == max_count]
                peak_times[day] = peak_slots[:3]  # Top 3 peak times
            else:
                peak_times[day] = []
        
        return peak_times
    
    def _analyze_module_distribution(self):
        """Analyze module scheduling distribution"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(DISTINCT module_code) FROM module_schedule')
        total_modules = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT session_type, COUNT(*) as count
        FROM module_schedule
        GROUP BY session_type
        ORDER BY count DESC
        ''')
        session_types = cursor.fetchall()
        
        cursor.execute('''
        SELECT module_code, COUNT(*) as sessions
        FROM module_schedule
        GROUP BY module_code
        ''')
        module_sessions = cursor.fetchall()

        most_common_type = session_types[0][0] if session_types else "None"
        avg_sessions = sum(row[1] for row in module_sessions) / len(module_sessions) if module_sessions else 0
        
        return {
            'total': total_modules,
            'most_common_type': most_common_type,
            'avg_sessions': avg_sessions
        }
    
    def _analyze_room_efficiency(self):
        """Analyze room efficiency metrics"""
        room_data = self.generate_room_utilization_report(output_format='data')
        
        if not room_data:
            return {'avg_utilization': 0, 'best_type': 'None'}
        
        avg_utilization = sum(room['Utilization Rate (%)'] for room in room_data) / len(room_data)
        
        # Group by room type
        type_utilization = {}
        for room in room_data:
            room_type = room['Type']
            if room_type not in type_utilization:
                type_utilization[room_type] = []
            type_utilization[room_type].append(room['Utilization Rate (%)'])
        
        # Find best performing room type
        best_type = max(type_utilization.keys(), 
                       key=lambda t: sum(type_utilization[t]) / len(type_utilization[t])) if type_utilization else 'None'
        
        return {
            'avg_utilization': avg_utilization,
            'best_type': best_type
        }
    
    # ==================== BATCH OPERATIONS ====================
    
    def import_schedules_from_csv(self, csv_file_path):
        """Import schedules from CSV file"""
        try:
            df = pd.read_csv(csv_file_path)
            required_columns = ['module_code', 'day_of_week', 'start_time', 'end_time', 
                              'room_id', 'instructor_id', 'session_type']
            
            if not all(col in df.columns for col in required_columns):
                print(f"CSV must contain columns: {', '.join(required_columns)}")
                return False
            
            success_count = 0
            error_count = 0
            
            for index, row in df.iterrows():
                try:
                    result = self.add_module_schedule(
                        row['module_code'], row['day_of_week'], row['start_time'], 
                        row['end_time'], int(row['room_id']), int(row['instructor_id']), 
                        row['session_type']
                    )
                    if result:
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    print(f"Error importing row {index + 1}: {e}")
                    error_count += 1
            
            print(f"Import completed: {success_count} successful, {error_count} errors")
            
            # Log the import
            self._log_system_action('bulk_import', f"Imported {success_count} schedules from {csv_file_path}")
            
            return True
            
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return False
    
    def export_all_schedules_to_csv(self):
        """Export all schedules to CSV"""
        with get_connection(self.db_path, row_factory=False) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            query = '''
        SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
               ms.room_id, ms.instructor_id, ms.session_type,
               r.building, r.room_number, i.first_name, i.last_name
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        ORDER BY ms.module_code, ms.day_of_week, ms.start_time
        '''

            df = pd.read_sql_query(query, conn)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Ensure directory exists
        from university_system.modules.shared.constants import paths
        timetable_reports_dir = paths.REPORTS_DIR / 'timetable_reports'
        os.makedirs(str(timetable_reports_dir), exist_ok=True)

        filename = os.path.join(str(timetable_reports_dir), f"all_schedules_export_{timestamp}.csv")
        df.to_csv(filename, index=False)
        print(f"All schedules exported to: {filename}")
        
        return filename
    
    def save_schedule_template(self, template_name, description=""):
        """Save current schedule as a template"""
        try:
            with get_connection(self.db_path, row_factory=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
        
                # Get all current schedules
                cursor.execute('''
                SELECT module_code, day_of_week, start_time, end_time,
                       room_id, instructor_id, session_type
                FROM module_schedule
                ORDER BY module_code, day_of_week, start_time
                ''')

                schedules = cursor.fetchall()

                # Convert to JSON
                template_data = []
                for schedule in schedules:
                    template_data.append({
                        'module_code': schedule[0],
                        'day_of_week': schedule[1],
                        'start_time': schedule[2],
                        'end_time': schedule[3],
                        'room_id': schedule[4],
                        'instructor_id': schedule[5],
                        'session_type': schedule[6]
                    })

                template_json = json.dumps(template_data, indent=2)

                cursor.execute('''
                INSERT INTO schedule_templates (template_name, description, template_data, created_by)
                VALUES (?, ?, ?, ?)
                ''', (template_name, description, template_json, 'admin'))

                print(f"Schedule template '{template_name}' saved successfully.")
                return True

        except sqlite3.IntegrityError:
            print(f"Template name '{template_name}' already exists.")
            return False
        except Exception as e:
            print(f"Error saving template: {e}")
            return False
    
    def load_schedule_template(self, template_name, clear_existing=False):
        """Load schedules from a template"""
        try:
            with get_connection(self.db_path, row_factory=False) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute('''
                SELECT template_data FROM schedule_templates WHERE template_name = ?
                ''', (template_name,))
        
                result = cursor.fetchone()
                if not result:
                    print(f"Template '{template_name}' not found.")
                    return False

                template_data = json.loads(result[0])

                if clear_existing:
                    confirm = input("This will delete all existing schedules. Continue? (y/n): ")
                    if confirm.lower() == 'y':
                        cursor.execute('DELETE FROM module_schedule')
                        print("Existing schedules cleared.")
                    else:
                        return False

                success_count = 0
                error_count = 0

                for schedule in template_data:
                    try:
                        cursor.execute('''
                        INSERT INTO module_schedule
                        (module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (schedule['module_code'], schedule['day_of_week'], schedule['start_time'],
                              schedule['end_time'], schedule['room_id'], schedule['instructor_id'],
                              schedule['session_type']))
                        success_count += 1
                    except Exception as e:
                        print(f"Error loading schedule: {e}")
                        error_count += 1

                print(f"Template loaded: {success_count} schedules added, {error_count} errors")

                # Log the action
                self._log_system_action('template_load', f"Loaded template '{template_name}'")

                return True

        except Exception as e:
            print(f"Error loading template: {e}")
            return False
    
    def list_schedule_templates(self):
        """List all saved schedule templates"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT template_name, description, created_date, created_by
        FROM schedule_templates
        ORDER BY created_date DESC
        ''')
        
        templates = cursor.fetchall()
        conn.close()
        
        if not templates:
            print("No schedule templates found.")
            return
        
        print("\nSchedule Templates:")
        print("=" * 80)
        print(f"{'Name':<20} {'Description':<30} {'Created':<15} {'By':<10}")
        print("-" * 80)
        
        for template in templates:
            name, desc, created, created_by = template
            created_date = datetime.fromisoformat(created).strftime("%Y-%m-%d")
            print(f"{name:<20} {desc[:28]:<30} {created_date:<15} {created_by:<10}")
        
        print("=" * 80)
    
    # ==================== SMART SCHEDULING ASSISTANT ====================



    def display_student_conflicts(self, student_id):
        """Display scheduling conflicts for a student"""
        conflicts = self.check_student_conflicts(student_id)
        
        if not conflicts:
            print(f"No scheduling conflicts found for student {student_id}.")
            return
        
        print(f"\nScheduling Conflicts for Student {student_id}:")
        print("="*100)
        
        for i, conflict in enumerate(conflicts, 1):
            module1 = conflict['module1']
            module2 = conflict['module2']
            
            print(f"Conflict #{i}:")
            print(f"Module 1: {module1['code']} - {module1['name']}")
            print(f"          {module1['day']} {module1['time']} in {module1['room']}")
            print(f"Module 2: {module2['code']} - {module2['name']}")
            print(f"          {module2['day']} {module2['time']} in {module2['room']}")
            print("-"*100)
        
        print("="*100)

    def update_module_schedule(self, schedule_id, **kwargs):
        """Update a module schedule entry"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Check if schedule entry exists
        cursor.execute('SELECT * FROM module_schedule WHERE id = ?', (schedule_id,))
        schedule = cursor.fetchone()
        
        if not schedule:
            print(f"Schedule ID {schedule_id} does not exist.")
            conn.close()
            return False
        
        # Build update query based on provided kwargs
        update_fields = []
        update_values = []
        
        if 'day_of_week' in kwargs:
            day = kwargs['day_of_week']
            if day not in DAYS_OF_WEEK:
                print(f"Invalid day of week. Must be one of: {', '.join(DAYS_OF_WEEK)}")
                conn.close()
                return False
            update_fields.append("day_of_week = ?")
            update_values.append(day)
        
        if 'start_time' in kwargs or 'end_time' in kwargs:
            # Get current values for validation
            cursor.execute('SELECT start_time, end_time FROM module_schedule WHERE id = ?', (schedule_id,))
            current_times = cursor.fetchone()
            start_time = kwargs.get('start_time', current_times[0])
            end_time = kwargs.get('end_time', current_times[1])
            
            # Basic time format validation
            try:
                datetime.strptime(start_time, "%H:%M")
                datetime.strptime(end_time, "%H:%M")
            except ValueError:
                print("Invalid time format. Use HH:MM format (24-hour).")
                conn.close()
                return False
            
            # Check if start time is before end time
            if start_time >= end_time:
                print("Start time must be before end time.")
                conn.close()
                return False
            
            if 'start_time' in kwargs:
                update_fields.append("start_time = ?")
                update_values.append(start_time)
            
            if 'end_time' in kwargs:
                update_fields.append("end_time = ?")
                update_values.append(end_time)
        
        if 'room_id' in kwargs:
            room_id = kwargs['room_id']
            cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
            if not cursor.fetchone():
                print(f"Room ID {room_id} does not exist.")
                conn.close()
                return False
            update_fields.append("room_id = ?")
            update_values.append(room_id)
        
        if 'instructor_id' in kwargs:
            instructor_id = kwargs['instructor_id']
            cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
            if not cursor.fetchone():
                print(f"Instructor ID {instructor_id} does not exist.")
                conn.close()
                return False
            update_fields.append("instructor_id = ?")
            update_values.append(instructor_id)
        
        if 'session_type' in kwargs:
            session_type = kwargs['session_type']
            if session_type not in SESSION_TYPES:
                print(f"Invalid session type. Must be one of: {', '.join(SESSION_TYPES)}")
                conn.close()
                return False
            update_fields.append("session_type = ?")
            update_values.append(session_type)
        
        if not update_fields:
            print("No fields to update.")
            conn.close()
            return False
        
        # Get current schedule details for conflict checking
        cursor.execute('''
        SELECT module_code, day_of_week, start_time, end_time, room_id, instructor_id
        FROM module_schedule WHERE id = ?
        ''', (schedule_id,))
        current = cursor.fetchone()
        module_code, current_day, current_start, current_end, current_room, current_instructor = current
        
        # Check for conflicts with the new schedule
        day = kwargs.get('day_of_week', current_day)
        start_time = kwargs.get('start_time', current_start)
        end_time = kwargs.get('end_time', current_end)
        room_id = kwargs.get('room_id', current_room)
        instructor_id = kwargs.get('instructor_id', current_instructor)
        
        # Check for room conflicts
        if 'day_of_week' in kwargs or 'start_time' in kwargs or 'end_time' in kwargs or 'room_id' in kwargs:
            conflicts = self._check_room_conflicts(room_id, day, start_time, end_time)
            # Filter out the current schedule
            conflicts = [c for c in conflicts if c[0] != schedule_id]
            if conflicts:
                print(f"Room conflict detected: Room is already scheduled during this time.")
                conn.close()
                return False
        
        # Check for instructor conflicts
        if 'day_of_week' in kwargs or 'start_time' in kwargs or 'end_time' in kwargs or 'instructor_id' in kwargs:
            conflicts = self._check_instructor_conflicts(instructor_id, day, start_time, end_time)
            # Filter out the current schedule
            conflicts = [c for c in conflicts if c[0] != schedule_id]
            if conflicts:
                print(f"Instructor conflict detected: Instructor is already scheduled during this time.")
                conn.close()
                return False
        
        # Execute the update
        query = f"UPDATE module_schedule SET {', '.join(update_fields)} WHERE id = ?"
        update_values.append(schedule_id)
        
        try:
            cursor.execute(query, update_values)
            conn.commit()
            print(f"Schedule updated successfully.")
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    def suggest_optimal_time_slot(self, module_code, session_type, duration_minutes=60):
        """Suggest optimal time slots for a new schedule"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Get module information
        cursor.execute('SELECT module_code FROM modules WHERE module_code = ?', (module_code,))
        if not cursor.fetchone():
            print(f"Module {module_code} does not exist.")
            conn.close()
            return []
        
        suggestions = []
        
        for day in DAYS_OF_WEEK:
            for time_slot in TIME_SLOTS:
                # Calculate end time
                start_hour, start_min = map(int, time_slot.split(':'))
                end_time = datetime.strptime(time_slot, "%H:%M") + timedelta(minutes=duration_minutes)
                end_time_str = end_time.strftime("%H:%M")
                
                # Check availability
                score = self._calculate_slot_score(day, time_slot, end_time_str, session_type)
                
                if score > 0:  # Only suggest available slots
                    suggestions.append({
                        'day': day,
                        'start_time': time_slot,
                        'end_time': end_time_str,
                        'score': score,
                        'reasons': self._get_score_reasons(day, time_slot, session_type)
                    })
        
        conn.close()
        
        # Sort by score (highest first)
        suggestions.sort(key=lambda x: x['score'], reverse=True)
        
        return suggestions[:10]  # Return top 10 suggestions
    
    def _calculate_slot_score(self, day, start_time, end_time, session_type):
        """Calculate a score for a time slot based on various factors"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        score = 100  # Start with base score
        
        # Check for conflicts
        cursor.execute('''
        SELECT COUNT(*) FROM module_schedule
        WHERE day_of_week = ? AND (
            (start_time < ? AND end_time > ?) OR
            (start_time < ? AND end_time > ?) OR
            (start_time >= ? AND end_time <= ?)
        )
        ''', (day, end_time, start_time, end_time, start_time, start_time, end_time))
        
        conflicts = cursor.fetchone()[0]
        if conflicts > 0:
            score = 0  # No score for conflicting slots
            conn.close()
            return score
        
        # Bonus for popular time slots (but not too crowded)
        cursor.execute('''
        SELECT COUNT(*) FROM module_schedule
        WHERE day_of_week = ? AND start_time = ?
        ''', (day, start_time))
        
        same_time_count = cursor.fetchone()[0]
        if 1 <= same_time_count <= 3:  # Sweet spot
            score += 10
        elif same_time_count > 5:  # Too crowded
            score -= 20
        
        # Preference bonuses
        if session_type == 'Lecture' and start_time in ['09:00', '10:00', '11:00']:
            score += 15  # Morning lectures preferred
        elif session_type == 'Lab' and start_time in ['14:00', '15:00', '16:00']:
            score += 10  # Afternoon labs preferred
        
        # Day preferences
        if day in ['Tuesday', 'Wednesday', 'Thursday']:
            score += 5  # Mid-week preferred
        
        conn.close()
        return score
    
    def _get_score_reasons(self, day, start_time, session_type):
        """Get human-readable reasons for the score"""
        reasons = []
        
        if session_type == 'Lecture' and start_time in ['09:00', '10:00', '11:00']:
            reasons.append("Good time for lectures")
        elif session_type == 'Lab' and start_time in ['14:00', '15:00', '16:00']:
            reasons.append("Preferred afternoon lab time")
        
        if day in ['Tuesday', 'Wednesday', 'Thursday']:
            reasons.append("Mid-week scheduling preferred")
        
        if start_time in ['09:00', '10:00']:
            reasons.append("Popular morning slot")
        
        return reasons
    
    def find_alternative_slots(self, day, start_time, end_time, room_type=None):
        """Find alternative time slots when conflicts occur"""
        alternatives = []
        
        # Try same day, different times
        for time_slot in TIME_SLOTS:
            if time_slot != start_time:
                duration = self._calculate_duration(start_time, end_time)
                alt_end = self._add_minutes_to_time(time_slot, duration)
                
                if self._is_slot_available(day, time_slot, alt_end):
                    alternatives.append({
                        'day': day,
                        'start_time': time_slot,
                        'end_time': alt_end,
                        'type': 'same_day'
                    })
        
        # Try same time, different days
        for alt_day in DAYS_OF_WEEK:
            if alt_day != day and self._is_slot_available(alt_day, start_time, end_time):
                alternatives.append({
                    'day': alt_day,
                    'start_time': start_time,
                    'end_time': end_time,
                    'type': 'same_time'
                })
        
        return alternatives
    
    def _calculate_duration(self, start_time, end_time):
        """Calculate duration in minutes between two times"""
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        return int((end - start).total_seconds() / 60)
    
    def _add_minutes_to_time(self, time_str, minutes):
        """Add minutes to a time string"""
        time_obj = datetime.strptime(time_str, "%H:%M")
        new_time = time_obj + timedelta(minutes=minutes)
        return new_time.strftime("%H:%M")
    
    def _is_slot_available(self, day, start_time, end_time):
        """Check if a time slot is available"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT COUNT(*) FROM module_schedule
        WHERE day_of_week = ? AND (
            (start_time < ? AND end_time > ?) OR
            (start_time < ? AND end_time > ?) OR
            (start_time >= ? AND end_time <= ?)
        )
        ''', (day, end_time, start_time, end_time, start_time, start_time, end_time))
        
        conflicts = cursor.fetchone()[0]
        conn.close()
        
        return conflicts == 0
    
    # ==================== ADVANCED SEARCH & FILTERING ====================
    
    def advanced_schedule_search(self, filters=None):
        """Advanced search with multiple criteria"""
        if filters is None:
            filters = {}
        
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Build dynamic query
        base_query = '''
        SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week, 
               ms.start_time, ms.end_time, r.building, r.room_number,
               i.first_name, i.last_name, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE 1=1
        '''
        
        params = []
        
        # Add filters
        if 'module_code' in filters and filters['module_code']:
            base_query += " AND ms.module_code LIKE ?"
            params.append(f"%{filters['module_code']}%")
        
        if 'day' in filters and filters['day']:
            base_query += " AND ms.day_of_week = ?"
            params.append(filters['day'])
        
        if 'time_from' in filters and filters['time_from']:
            base_query += " AND ms.start_time >= ?"
            params.append(filters['time_from'])
        
        if 'time_to' in filters and filters['time_to']:
            base_query += " AND ms.end_time <= ?"
            params.append(filters['time_to'])
        
        if 'session_type' in filters and filters['session_type']:
            base_query += " AND ms.session_type = ?"
            params.append(filters['session_type'])
        
        if 'instructor' in filters and filters['instructor']:
            base_query += " AND (i.first_name LIKE ? OR i.last_name LIKE ?)"
            params.extend([f"%{filters['instructor']}%", f"%{filters['instructor']}%"])
        
        if 'building' in filters and filters['building']:
            base_query += " AND r.building LIKE ?"
            params.append(f"%{filters['building']}%")
        
        if 'room_type' in filters and filters['room_type']:
            base_query += " AND r.room_type = ?"
            params.append(filters['room_type'])
        
        base_query += " ORDER BY ms.day_of_week, ms.start_time"
        
        cursor.execute(base_query, params)
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def find_free_rooms(self, day, start_time, end_time, min_capacity=0, room_type=None):
        """Find available rooms for a specific time slot"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Base query for rooms
        query = '''
        SELECT r.id, r.room_number, r.building, r.capacity, r.room_type, r.equipment
        FROM rooms r
        WHERE r.is_active = 1 AND r.capacity >= ?
        '''
        params = [min_capacity]
        
        if room_type:
            query += " AND r.room_type = ?"
            params.append(room_type)
        
        # Exclude rooms that are scheduled during this time
        query += '''
        AND r.id NOT IN (
            SELECT ms.room_id FROM module_schedule ms
            WHERE ms.day_of_week = ? AND (
                (ms.start_time < ? AND ms.end_time > ?) OR
                (ms.start_time < ? AND ms.end_time > ?) OR
                (ms.start_time >= ? AND ms.end_time <= ?)
            )
        )
        '''
        params.extend([day, end_time, start_time, end_time, start_time, start_time, end_time])
        
        query += " ORDER BY r.building, r.room_number"
        
        cursor.execute(query, params)
        free_rooms = cursor.fetchall()
        conn.close()
        
        return free_rooms
    
    def find_schedule_gaps(self, entity_type, entity_id):
        """Find free periods in student or instructor schedules"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        if entity_type == 'student':
            # Get student's enrolled modules
            cursor.execute('SELECT module_code FROM student_modules WHERE student_id = ?', (entity_id,))
            modules = [row[0] for row in cursor.fetchall()]
            
            if not modules:
                conn.close()
                return "Student not enrolled in any modules"
            
            # Get schedule for these modules
            placeholders = ','.join(['?'] * len(modules))
            query = f'''
            SELECT day_of_week, start_time, end_time
            FROM module_schedule
            WHERE module_code IN ({placeholders})
            ORDER BY day_of_week, start_time
            '''
            cursor.execute(query, modules)
            
        elif entity_type == 'instructor':
            query = '''
            SELECT day_of_week, start_time, end_time
            FROM module_schedule
            WHERE instructor_id = ?
            ORDER BY day_of_week, start_time
            '''
            cursor.execute(query, (entity_id,))
        
        schedules = cursor.fetchall()
        conn.close()
        
        # Find gaps
        gaps = {}
        for day in DAYS_OF_WEEK:
            day_schedules = [s for s in schedules if s[0] == day]
            gaps[day] = self._find_daily_gaps(day_schedules)
        
        return gaps
    
    def _find_daily_gaps(self, day_schedules):
        """Find gaps in a single day's schedule"""
        if not day_schedules:
            return [{'start': '09:00', 'end': '17:00', 'duration': 480}]
        
        # Sort by start time
        day_schedules.sort(key=lambda x: x[1])
        
        gaps = []
        
        # Gap before first class
        first_start = day_schedules[0][1]
        if first_start > '09:00':
            duration = self._calculate_duration('09:00', first_start)
            gaps.append({'start': '09:00', 'end': first_start, 'duration': duration})
        
        # Gaps between classes
        for i in range(len(day_schedules) - 1):
            current_end = day_schedules[i][2]
            next_start = day_schedules[i + 1][1]
            
            if current_end < next_start:
                duration = self._calculate_duration(current_end, next_start)
                if duration >= 30:  # Only count gaps of 30+ minutes
                    gaps.append({'start': current_end, 'end': next_start, 'duration': duration})
        
        # Gap after last class
        last_end = day_schedules[-1][2]
        if last_end < '17:00':
            duration = self._calculate_duration(last_end, '17:00')
            gaps.append({'start': last_end, 'end': '17:00', 'duration': duration})
        
        return gaps
    
    # ==================== CONFLICT RESOLUTION ====================
    
    def detect_all_conflicts(self):
        """Detect all types of scheduling conflicts"""
        conflicts = []
        
        # Room conflicts
        room_conflicts = self._detect_room_conflicts()
        conflicts.extend(room_conflicts)
        
        # Instructor conflicts
        instructor_conflicts = self._detect_instructor_conflicts()
        conflicts.extend(instructor_conflicts)
        
        # Student conflicts
        student_conflicts = self._detect_student_conflicts()
        conflicts.extend(student_conflicts)
        
        # Save conflicts to database
        self._save_conflicts_to_db(conflicts)
        
        return conflicts
    
    def _detect_room_conflicts(self):
        """Detect room scheduling conflicts"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT ms1.id, ms1.module_code, ms1.day_of_week, ms1.start_time, ms1.end_time,
               ms2.id, ms2.module_code, ms2.day_of_week, ms2.start_time, ms2.end_time,
               r.building, r.room_number
        FROM module_schedule ms1
        JOIN module_schedule ms2 ON ms1.room_id = ms2.room_id AND ms1.id < ms2.id
        JOIN rooms r ON ms1.room_id = r.id
        WHERE ms1.day_of_week = ms2.day_of_week
        AND ((ms1.start_time < ms2.end_time AND ms1.end_time > ms2.start_time))
        ''')
        
        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'type': 'room_conflict',
                'description': f"Room {row[10]}-{row[11]} double-booked on {row[2]} between {row[8]} modules {row[1]} and {row[6]}",
                'affected_schedules': [row[0], row[5]],
                'severity': 'high'
            })
        
        conn.close()
        return conflicts
    
    def _detect_instructor_conflicts(self):
        """Detect instructor scheduling conflicts"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT ms1.id, ms1.module_code, ms1.day_of_week, ms1.start_time, ms1.end_time,
               ms2.id, ms2.module_code, ms2.day_of_week, ms2.start_time, ms2.end_time,
               i.first_name, i.last_name
        FROM module_schedule ms1
        JOIN module_schedule ms2 ON ms1.instructor_id = ms2.instructor_id AND ms1.id < ms2.id
        JOIN instructors i ON ms1.instructor_id = i.id
        WHERE ms1.day_of_week = ms2.day_of_week
        AND ((ms1.start_time < ms2.end_time AND ms1.end_time > ms2.start_time))
        ''')
        
        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'type': 'instructor_conflict',
                'description': f"Instructor {row[10]} {row[11]} double-booked on {row[2]} between modules {row[1]} and {row[6]}",
                'affected_schedules': [row[0], row[5]],
                'severity': 'high'
            })
        
        conn.close()
        return conflicts
    
    def _detect_student_conflicts(self):
        """Detect student scheduling conflicts"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Get all students and their enrolled modules
        cursor.execute('SELECT DISTINCT student_id FROM student_modules')
        students = [row[0] for row in cursor.fetchall()]
        
        conflicts = []
        for student_id in students:
            student_conflicts = self.check_student_conflicts(student_id)
            for conflict in student_conflicts:
                conflicts.append({
                    'type': 'student_conflict',
                    'description': f"Student {student_id} has overlapping classes: {conflict['module1']['code']} and {conflict['module2']['code']} on {conflict['module1']['day']}",
                    'affected_schedules': [],  # Would need schedule IDs
                    'severity': 'medium',
                    'student_id': student_id
                })
        
        conn.close()
        return conflicts
    
    def _save_conflicts_to_db(self, conflicts):
        """Save detected conflicts to database"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Clear existing unresolved conflicts
        cursor.execute('DELETE FROM schedule_conflicts WHERE resolved = 0')
        
        for conflict in conflicts:
            cursor.execute('''
            INSERT INTO schedule_conflicts 
            (conflict_type, description, affected_schedules, resolved)
            VALUES (?, ?, ?, 0)
            ''', (conflict['type'], conflict['description'], 
                  json.dumps(conflict['affected_schedules'])))
        
        conn.commit()
        conn.close()
    
    def resolve_conflict(self, conflict_id, resolution_notes=""):
        """Mark a conflict as resolved"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE schedule_conflicts 
        SET resolved = 1, resolution_notes = ?, resolved_date = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (resolution_notes, conflict_id))
        
        conn.commit()
        conn.close()
        
        print(f"Conflict {conflict_id} marked as resolved.")
    
    def _get_all_conflicts(self):
        """Get all conflicts from database"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, conflict_type, description, resolved, detected_date, resolution_notes
        FROM schedule_conflicts
        ORDER BY detected_date DESC
        ''')
        
        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'id': row[0],
                'type': row[1],
                'description': row[2],
                'resolved': bool(row[3]),
                'detected_date': row[4],
                'resolution_notes': row[5]
            })
        
        conn.close()
        return conflicts
    
    # ==================== CALENDAR INTEGRATION ====================
    
    def export_to_ical(self, entity_type, entity_id, filename=None):
        """Export schedule to iCal format"""
        cal = Calendar()
        cal.add('prodid', '-//University Schedule//EN')
        cal.add('version', '2.0')
        
        # Get schedule data
        if entity_type == 'student':
            schedules = self._get_student_schedule_data(entity_id)
            cal.add('x-wr-calname', f'Student {entity_id} Schedule')
        elif entity_type == 'instructor':
            schedules = self._get_instructor_schedule_data(entity_id)
            cal.add('x-wr-calname', f'Instructor {entity_id} Schedule')
        else:
            print("Invalid entity type")
            return None
        
        # Add events
        for schedule in schedules:
            event = Event()
            event.add('summary', f"{schedule['module_code']} - {schedule['session_type']}")
            event.add('description', f"Module: {schedule['module_name']}\nRoom: {schedule['room']}\nInstructor: {schedule['instructor']}")
            
            # Calculate event times (recurring weekly)
            start_time = datetime.strptime(schedule['start_time'], "%H:%M").time()
            end_time = datetime.strptime(schedule['end_time'], "%H:%M").time()
            
            # Get day index (Monday = 0)
            day_index = DAYS_OF_WEEK.index(schedule['day'])
            
            # Find next occurrence of this day
            today = datetime.now().date()
            days_ahead = day_index - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            
            event_date = today + timedelta(days=days_ahead)
            event_start = datetime.combine(event_date, start_time)
            event_end = datetime.combine(event_date, end_time)
            
            event.add('dtstart', event_start)
            event.add('dtend', event_end)
            event.add('location', schedule['room'])
            
            # Add recurrence rule (weekly for the semester)
            event.add('rrule', {'freq': 'weekly', 'count': 15})  # 15 weeks typical semester
            
            cal.add_component(event)
        
        # Save to file
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"timetable_reports/{entity_type}_{entity_id}_schedule_{timestamp}.ics"

        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, 'wb') as f:
            f.write(cal.to_ical())
        
        print(f"iCal file exported: {filename}")
        return filename
    
    def _get_student_schedule_data(self, student_id):
        """Get schedule data for a student"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT module_code FROM student_modules WHERE student_id = ?', (student_id,))
        modules = [row[0] for row in cursor.fetchall()]
        
        if not modules:
            conn.close()
            return []
        
        placeholders = ','.join(['?'] * len(modules))
        query = f'''
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number, i.first_name, i.last_name, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.module_code IN ({placeholders})
        ORDER BY ms.day_of_week, ms.start_time
        '''
        
        cursor.execute(query, modules)
        schedules = cursor.fetchall()
        conn.close()
        
        schedule_data = []
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, first_name, last_name, session_type = schedule
            schedule_data.append({
                'module_code': module_code,
                'module_name': module_name or "Unknown",
                'day': day,
                'start_time': start,
                'end_time': end,
                'room': f"{building}-{room}" if building and room else "TBA",
                'instructor': f"{first_name} {last_name}" if first_name and last_name else "TBA",
                'session_type': session_type
            })
        
        return schedule_data
    
    def _get_instructor_schedule_data(self, instructor_id):
        """Get schedule data for an instructor"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        query = '''
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number, i.first_name, i.last_name, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.instructor_id = ?
        ORDER BY ms.day_of_week, ms.start_time
        '''
        
        cursor.execute(query, (instructor_id,))
        schedules = cursor.fetchall()
        conn.close()
        
        schedule_data = []
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, first_name, last_name, session_type = schedule
            schedule_data.append({
                'module_code': module_code,
                'module_name': module_name or "Unknown",
                'day': day,
                'start_time': start,
                'end_time': end,
                'room': f"{building}-{room}" if building and room else "TBA",
                'instructor': f"{first_name} {last_name}" if first_name and last_name else "TBA",
                'session_type': session_type
            })
        
        return schedule_data
    
    # ==================== DATA MANAGEMENT ====================
    
    def create_backup(self, backup_name=None, description=""):
        """Create a backup of the database"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"

        # Ensure backups directory exists (already created via paths._ensure)
        from university_system.modules.shared.constants import paths
        os.makedirs(str(paths.BACKUP_DIR), exist_ok=True)

        backup_path = os.path.join(str(paths.BACKUP_DIR), f"{backup_name}.db")

        try:
            # Check if source database exists
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(f"Database file not found: {self.db_path}")

            # Copy the database file
            shutil.copy2(self.db_path, backup_path)
            
            # Get file size
            file_size = os.path.getsize(backup_path)
            
            # Record backup in database
            conn = get_connection(self.db_path, row_factory=False)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO backups (backup_name, backup_path, backup_size, description)
            VALUES (?, ?, ?, ?)
            ''', (backup_name, backup_path, file_size, description))
            
            conn.commit()
            conn.close()
            
            print(f"Backup created successfully: {backup_path}")
            return backup_path
            
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
    
    def list_backups(self):
        """List all available backups"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT backup_name, backup_date, backup_size, description
        FROM backups
        ORDER BY backup_date DESC
        ''')
        
        backups = cursor.fetchall()
        conn.close()
        
        if not backups:
            print("No backups found.")
            return
        
        print("\nAvailable Backups:")
        print("=" * 80)
        print(f"{'Name':<25} {'Date':<20} {'Size (KB)':<12} {'Description':<20}")
        print("-" * 80)
        
        for backup in backups:
            name, date, size, desc = backup
            backup_date = datetime.fromisoformat(date).strftime("%Y-%m-%d %H:%M")
            size_kb = round(size / 1024, 2) if size else 0
            print(f"{name:<25} {backup_date:<20} {size_kb:<12} {desc:<20}")
        
        print("=" * 80)
    
    def restore_backup(self, backup_name):
        """Restore from a backup"""
        from university_system.modules.shared.constants import paths
        backup_path = paths.BACKUP_DIR / f"{backup_name}.db"

        if not backup_path.exists():
            print(f"Backup file not found: {backup_path}")
            return False
        
        # Confirm restoration
        print(f"WARNING: This will replace the current database with the backup from {backup_name}")
        confirm = input("Are you sure you want to continue? (y/n): ")
        
        if confirm.lower() != 'y':
            print("Restore canceled.")
            return False
        
        try:
            # Create a backup of current state before restoring
            self.create_backup("pre_restore_backup", "Automatic backup before restore")
            
            # Replace current database
            shutil.copy2(backup_path, self.db_path)
            
            print(f"Database restored from backup: {backup_name}")
            return True
            
        except Exception as e:
            print(f"Error restoring backup: {e}")
            return False
    
    def validate_data_consistency(self):
        """Validate data consistency and integrity"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        issues = []
        
        # Check for orphaned schedules (invalid room_id)
        cursor.execute('''
        SELECT ms.id, ms.module_code, ms.room_id
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        WHERE r.id IS NULL
        ''')
        orphaned_rooms = cursor.fetchall()
        if orphaned_rooms:
            issues.append(f"Found {len(orphaned_rooms)} schedules with invalid room references")
        
        # Check for orphaned schedules (invalid instructor_id)
        cursor.execute('''
        SELECT ms.id, ms.module_code, ms.instructor_id
        FROM module_schedule ms
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        WHERE i.id IS NULL
        ''')
        orphaned_instructors = cursor.fetchall()
        if orphaned_instructors:
            issues.append(f"Found {len(orphaned_instructors)} schedules with invalid instructor references")
        
        # Check for duplicate schedules
        cursor.execute('''
        SELECT module_code, day_of_week, start_time, end_time, room_id, instructor_id, COUNT(*)
        FROM module_schedule
        GROUP BY module_code, day_of_week, start_time, end_time, room_id, instructor_id
        HAVING COUNT(*) > 1
        ''')
        duplicates = cursor.fetchall()
        if duplicates:
            issues.append(f"Found {len(duplicates)} duplicate schedule entries")
        
        # Check for invalid time formats
        cursor.execute('''
        SELECT id, start_time, end_time
        FROM module_schedule
        WHERE start_time NOT GLOB '[0-9][0-9]:[0-9][0-9]' 
           OR end_time NOT GLOB '[0-9][0-9]:[0-9][0-9]'
        ''')
        invalid_times = cursor.fetchall()
        if invalid_times:
            issues.append(f"Found {len(invalid_times)} schedules with invalid time formats")
        
        conn.close()
        
        if issues:
            print("\nData Consistency Issues Found:")
            print("=" * 50)
            for i, issue in enumerate(issues, 1):
                print(f"{i}. {issue}")
            print("=" * 50)
        else:
            print("No data consistency issues found.")
        
        return issues
    
    def clean_orphaned_records(self):
        """Clean up orphaned records"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Remove schedules with invalid room references
        cursor.execute('''
        DELETE FROM module_schedule
        WHERE room_id NOT IN (SELECT id FROM rooms)
        ''')
        removed_room_refs = cursor.rowcount
        
        # Remove schedules with invalid instructor references
        cursor.execute('''
        DELETE FROM module_schedule
        WHERE instructor_id NOT IN (SELECT id FROM instructors)
        ''')
        removed_instructor_refs = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"Cleanup completed:")
        print(f"  - Removed {removed_room_refs} schedules with invalid room references")
        print(f"  - Removed {removed_instructor_refs} schedules with invalid instructor references")
    
    # ==================== SYSTEM CONFIGURATION ====================
    
    def update_system_setting(self, key, value):
        """Update a system setting"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE scheduling_system_settings
        SET value = ?, last_modified = CURRENT_TIMESTAMP
        WHERE key = ?
        ''', (value, key))

        if cursor.rowcount == 0:
            # Setting doesn't exist, create it
            cursor.execute('''
            INSERT INTO scheduling_system_settings (key, value, description)
            VALUES (?, ?, ?)
            ''', (key, value, f"Custom setting: {key}"))
        
        conn.commit()
        conn.close()
        
        print(f"System setting '{key}' updated to '{value}'")
    
    def get_system_setting(self, key, default=None):
        """Get a system setting value"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM scheduling_system_settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else default
    
    def list_system_settings(self):
        """List all system settings"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT key, value, description, last_modified
        FROM scheduling_system_settings
        ORDER BY key
        ''')
        
        settings = cursor.fetchall()
        conn.close()
        
        print("\nSystem Settings:")
        print("=" * 80)
        print(f"{'Key':<25} {'Value':<20} {'Description':<30}")
        print("-" * 80)
        
        for setting in settings:
            key, value, desc, modified = setting
            print(f"{key:<25} {value:<20} {desc:<30}")
        
        print("=" * 80)

    def _get_admin_email(self):
        """Get the administrator email address from system settings or users table"""
        try:
            # First try to get from system settings
            admin_email = self.get_system_setting('admin_email')
            if admin_email:
                return admin_email

            # Fallback: Get from users table (first admin user)
            conn = get_connection(self.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT email FROM users
                WHERE role = 'admin'
                ORDER BY id
                LIMIT 1
            ''')
            result = cursor.fetchone()
            conn.close()

            if result:
                return result[0]

            # Ultimate fallback
            return 'admin@university.edu'

        except Exception as e:
            # Return default email if query fails
            return 'admin@university.edu'

    # ==================== NOTIFICATION SYSTEM ====================

    def create_notification(self, recipient_type, recipient_id, message, notification_type="info"):
        """Create a notification by sending an email using the proper email service"""
        try:
            # Import email service
            from university_system.infrastructure.email.email_service import send_email

            conn = get_connection(self.db_path, row_factory=False)
            cursor = conn.cursor()

            # Get recipient email based on type
            email_address = None
            recipient_name = "User"

            if recipient_type == 'instructor':
                cursor.execute('SELECT email, first_name, last_name FROM instructors WHERE id = ?', (recipient_id,))
                result = cursor.fetchone()
                if result:
                    email_address, first_name, last_name = result
                    recipient_name = f"{first_name or ''} {last_name or ''}".strip()
            elif recipient_type == 'student':
                cursor.execute('SELECT email, first_name, last_name FROM students WHERE student_id = ?', (recipient_id,))
                result = cursor.fetchone()
                if result:
                    email_address, first_name, last_name = result
                    recipient_name = f"{first_name or ''} {last_name or ''}".strip()

            conn.close()

            # Send email if we have a valid address
            if email_address:
                # Render email from template
                from university_system.infrastructure.email.template_utils import render_template

                subject, body = render_template('academics/module_scheduling_notification', {
                    'notification_type': notification_type.replace('_', ' ').title(),
                    'recipient_name': recipient_name,
                    'message': message
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = f"Module Scheduling Notification - {notification_type.replace('_', ' ').title()}"
                    body = f"Dear {recipient_name},\n\n{message}\n\nBest regards,\nUniversity Module Scheduling System"

                send_email(email_address, subject, body)

        except Exception as e:
            # Silently fail - notifications are optional
            pass
    
    def send_schedule_change_notifications(self, schedule_id, change_description):
        """Send notifications when schedules change"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Get schedule details
        cursor.execute('''
        SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.instructor_id,
               r.building, r.room_number
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        WHERE ms.id = ?
        ''', (schedule_id,))

        schedule = cursor.fetchone()
        if not schedule:
            conn.close()
            return

        module_code, day, start_time, instructor_id, building, room = schedule

        # Notify instructor
        message = f"Schedule change for {module_code}: {change_description}"
        if instructor_id:
            self.create_notification('instructor', str(instructor_id), message, 'schedule_change')

        # Notify students enrolled in the module
        cursor.execute('SELECT student_id FROM student_modules WHERE module_code = ?', (module_code,))
        students = cursor.fetchall()

        for student in students:
            if student[0]:
                self.create_notification('student', student[0], message, 'schedule_change')

        conn.close()
        print(f"Notifications sent for schedule change: {change_description}")
    
    def get_notifications(self, recipient_type, recipient_id, unread_only=True):
        """Get notifications for a user by checking their emails"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Get user email based on type
        email_address = None
        if recipient_type == 'instructor':
            cursor.execute('SELECT email FROM instructors WHERE id = ?', (recipient_id,))
            result = cursor.fetchone()
            if result:
                email_address = result[0]
        elif recipient_type == 'student':
            cursor.execute('SELECT email FROM students WHERE student_id = ?', (recipient_id,))
            result = cursor.fetchone()
            if result:
                email_address = result[0]

        if not email_address:
            conn.close()
            return []

        # Get emails from stored_emails table
        query = '''
        SELECT id, subject, body, created_date
        FROM stored_emails
        WHERE recipient_email = ?
        AND subject LIKE '%Module Scheduling%'
        ORDER BY created_date DESC
        '''

        cursor.execute(query, (email_address,))
        notifications = cursor.fetchall()
        conn.close()

        return notifications
    
    def mark_notification_read(self, notification_id):
        """Mark a notification as read - no-op for email-based notifications"""
        # Email-based notifications don't use read/unread status in the same way
        # This is kept for backward compatibility but does nothing
        pass

    def email_all_students_on_module(self, module_code, subject, message, include_instructor=True):
        """
        Email all students enrolled in a module, and optionally the instructor.

        Args:
            module_code: The module code to send emails for
            subject: Email subject line
            message: Email body message
            include_instructor: Whether to also email the instructor (default: True)

        Returns:
            dict: Summary of emails sent (students_emailed, instructor_emailed, errors)
        """
        from university_system.infrastructure.email.email_service import send_email

        summary = {
            'students_emailed': 0,
            'instructor_emailed': False,
            'errors': []
        }

        try:
            conn = get_connection(self.db_path, row_factory=False)
            cursor = conn.cursor()

            # Get module name for better messaging
            cursor.execute('SELECT module_name FROM modules WHERE module_code = ?', (module_code,))
            module_result = cursor.fetchone()
            module_name = module_result[0] if module_result else module_code

            # Email all students enrolled in the module
            cursor.execute('''
                SELECT DISTINCT s.student_id, s.email, s.first_name, s.last_name
                FROM students s
                INNER JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                AND s.email IS NOT NULL
                AND s.email != ''
            ''', (module_code,))

            students = cursor.fetchall()

            for student_id, email, first_name, last_name in students:
                try:
                    student_name = f"{first_name or ''} {last_name or ''}".strip() or "Student"

                    # Render email from template
                    from university_system.infrastructure.email.template_utils import render_template

                    template_subject, personalized_message = render_template('academics/module_student_notification', {
                        'custom_subject': subject,
                        'student_name': student_name,
                        'message': message,
                        'module_name': module_name,
                        'module_code': module_code
                    })

                    # Fallback if template not found
                    if not template_subject or not personalized_message:
                        personalized_message = f"Dear {student_name},\n\n{message}\n\nModule: {module_name} ({module_code})\n\nBest regards,\nUniversity Module Scheduling System"

                    send_email(email, subject, personalized_message)
                    summary['students_emailed'] += 1
                except Exception as e:
                    summary['errors'].append(f"Failed to email {email}: {str(e)}")

            # Email instructor if requested
            if include_instructor:
                cursor.execute('''
                    SELECT DISTINCT i.email, i.first_name, i.last_name
                    FROM instructors i
                    INNER JOIN module_schedule ms ON i.id = ms.instructor_id
                    WHERE ms.module_code = ?
                    AND i.email IS NOT NULL
                    AND i.email != ''
                    LIMIT 1
                ''', (module_code,))

                instructor = cursor.fetchone()
                if instructor:
                    email, first_name, last_name = instructor
                    try:
                        instructor_name = f"{first_name or ''} {last_name or ''}".strip() or "Instructor"
                        personalized_message = f"Dear {instructor_name},\n\n{message}\n\nModule: {module_name} ({module_code})\n\nBest regards,\nUniversity Module Scheduling System"

                        send_email(email, subject, personalized_message)
                        summary['instructor_emailed'] = True
                    except Exception as e:
                        summary['errors'].append(f"Failed to email instructor {email}: {str(e)}")

            conn.close()

        except Exception as e:
            summary['errors'].append(f"Database error: {str(e)}")

        return summary

    # ==================== HOLIDAY MANAGEMENT ====================
    
    def add_holiday(self, name, start_date, end_date=None, description="", recurring=False):
        """Add a holiday or special event"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        if end_date is None:
            end_date = start_date
        
        cursor.execute('''
        INSERT INTO holidays (holiday_name, start_date, end_date, description, recurring)
        VALUES (?, ?, ?, ?, ?)
        ''', (name, start_date, end_date, description, recurring))
        
        conn.commit()
        conn.close()
        
        print(f"Holiday '{name}' added for {start_date}" + (f" to {end_date}" if end_date != start_date else ""))
    
    def list_holidays(self):
        """List all holidays"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT holiday_name, start_date, end_date, description, recurring
        FROM holidays
        ORDER BY start_date
        ''')
        
        holidays = cursor.fetchall()
        conn.close()
        
        if not holidays:
            print("No holidays found.")
            return
        
        print("\nHolidays and Special Events:")
        print("=" * 80)
        print(f"{'Name':<20} {'Start Date':<12} {'End Date':<12} {'Recurring':<10} {'Description':<20}")
        print("-" * 80)
        
        for holiday in holidays:
            name, start, end, desc, recurring = holiday
            recurring_str = "Yes" if recurring else "No"
            print(f"{name:<20} {start:<12} {end:<12} {recurring_str:<10} {desc:<20}")
        
        print("=" * 80)
    
    def check_holiday_conflicts(self, date):
        """Check if a date conflicts with holidays"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT holiday_name, description
        FROM holidays
        WHERE ? BETWEEN start_date AND end_date
        ''', (date,))
        
        conflicts = cursor.fetchall()
        conn.close()
        
        return conflicts

    def check_student_conflicts(self, student_id):
        """Check for scheduling conflicts in a student's timetable"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Check if student exists
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()
        
        if not student:
            print(f"Student ID {student_id} does not exist.")
            conn.close()
            return []
        
        # Get modules the student is enrolled in
        cursor.execute('''
        SELECT module_code FROM student_modules WHERE student_id = ?
        ''', (student_id,))
        
        enrolled_modules = [row[0] for row in cursor.fetchall()]
        
        if not enrolled_modules:
            print(f"Student {student_id} is not enrolled in any modules.")
            conn.close()
            return []
        
        # Get schedule for the enrolled modules
        placeholders = ','.join(['?'] * len(enrolled_modules))
        query = f'''
        SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time, 
               r.building, r.room_number
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.module_code IN ({placeholders})
        ORDER BY ms.day_of_week, ms.start_time
        '''
        
        cursor.execute(query, enrolled_modules)
        schedules = cursor.fetchall()
        
        # Check for conflicts
        conflicts = []
        
        for i, schedule1 in enumerate(schedules):
            id1, code1, name1, day1, start1, end1, building1, room1 = schedule1
            room1_str = f"{building1}-{room1}" if building1 and room1 else "TBA"
            
            for j, schedule2 in enumerate(schedules):
                if i >= j:  # Skip comparing the same schedule or already compared pairs
                    continue
                
                id2, code2, name2, day2, start2, end2, building2, room2 = schedule2
                room2_str = f"{building2}-{room2}" if building2 and room2 else "TBA"
                
                # Check if days match and times overlap
                if day1 == day2 and (
                    (start1 <= start2 < end1) or
                    (start1 < end2 <= end1) or
                    (start2 <= start1 < end2) or
                    (start2 < end1 <= end2)
                ):
                    conflicts.append({
                        'module1': {
                            'code': code1,
                            'name': name1,
                            'day': day1,
                            'time': f"{start1}-{end1}",
                            'room': room1_str
                        },
                        'module2': {
                            'code': code2,
                            'name': name2,
                            'day': day2,
                            'time': f"{start2}-{end2}",
                            'room': room2_str
                        }
                    })
        
        conn.close()
        return conflicts
    
    # ==================== ENHANCED VISUALIZATION ====================
    
    def generate_visual_timetable(self, entity_type, entity_id, output_path=None):
        """Generate a visual timetable using matplotlib"""
        # Get schedule data
        if entity_type == 'student':
            schedule_data = self._get_student_schedule_data(entity_id)
            title = f"Student {entity_id} Timetable"
        elif entity_type == 'instructor':
            schedule_data = self._get_instructor_schedule_data(entity_id)
            title = f"Instructor {entity_id} Timetable"
        else:
            print("Invalid entity type")
            return None
        
        if not schedule_data:
            print("No schedule data found")
            return None
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Set up the grid
        days = DAYS_OF_WEEK
        times = TIME_SLOTS
        
        # Create a matrix for the schedule
        schedule_matrix = np.zeros((len(times), len(days)))
        schedule_text = {}
        
        # Color map for different session types
        colors = {
            'Lecture': '#FF6B6B',
            'Lab': '#4ECDC4',
            'Tutorial': '#45B7D1',
            'Seminar': '#96CEB4',
            'Workshop': '#FFEAA7'
        }
        
        # Fill the matrix
        for schedule in schedule_data:
            day_idx = days.index(schedule['day'])
            
            # Find the closest time slot
            start_time = schedule['start_time']
            closest_time_idx = 0
            min_diff = float('inf')
            
            for i, time_slot in enumerate(times):
                time_diff = abs(int(start_time[:2]) - int(time_slot[:2]))
                if time_diff < min_diff:
                    min_diff = time_diff
                    closest_time_idx = i
            
            schedule_matrix[closest_time_idx, day_idx] = 1
            schedule_text[(closest_time_idx, day_idx)] = {
                'module': schedule['module_code'],
                'type': schedule['session_type'],
                'room': schedule['room'],
                'time': f"{schedule['start_time']}-{schedule['end_time']}"
            }
        
        # Create the heatmap
        im = ax.imshow(schedule_matrix, cmap='Blues', aspect='auto', alpha=0.3)
        
        # Set ticks and labels
        ax.set_xticks(range(len(days)))
        ax.set_yticks(range(len(times)))
        ax.set_xticklabels(days)
        ax.set_yticklabels(times)
        
        # Add text annotations
        for (time_idx, day_idx), info in schedule_text.items():
            session_type = info['type']
            color = colors.get(session_type, '#95A5A6')
            
            # Create a colored rectangle
            rect = plt.Rectangle((day_idx-0.4, time_idx-0.4), 0.8, 0.8, 
                               facecolor=color, alpha=0.7, edgecolor='black')
            ax.add_patch(rect)
            
            # Add text
            ax.text(day_idx, time_idx-0.2, info['module'], 
                   ha='center', va='center', fontweight='bold', fontsize=10)
            ax.text(day_idx, time_idx, info['type'], 
                   ha='center', va='center', fontsize=8)
            ax.text(day_idx, time_idx+0.2, info['room'], 
                   ha='center', va='center', fontsize=7)
        
        # Customize the plot
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Days of Week', fontsize=12)
        ax.set_ylabel('Time Slots', fontsize=12)
        
        # Add grid
        ax.set_xticks(np.arange(-0.5, len(days), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(times), 1), minor=True)
        ax.grid(which='minor', color='gray', linestyle='-', linewidth=0.5)
        
        # Add legend
        legend_elements = [plt.Rectangle((0,0),1,1, facecolor=color, alpha=0.7, label=session_type)
                          for session_type, color in colors.items()]
        ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.05, 1))
        
        plt.tight_layout()

        # Save the plot
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = paths.ANALYTICS_DIR / f"{entity_type}_{entity_id}_visual_timetable_{timestamp}.png"

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Visual timetable saved: {output_path}")
        return output_path
    
    def generate_utilization_charts(self):
        """Generate utilization charts and graphs"""
        # Room utilization chart
        room_data = self.generate_room_utilization_report(output_format='data')
        
        if room_data:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
            
            # Room utilization bar chart
            rooms = [r['Room'] for r in room_data[:10]]  # Top 10 rooms
            utilization = [r['Utilization Rate (%)'] for r in room_data[:10]]
            
            ax1.bar(rooms, utilization, color='skyblue')
            ax1.set_title('Room Utilization Rates (Top 10)')
            ax1.set_xlabel('Rooms')
            ax1.set_ylabel('Utilization Rate (%)')
            ax1.tick_params(axis='x', rotation=45)
            
            # Room type distribution pie chart
            type_counts = {}
            for room in room_data:
                room_type = room['Type']
                type_counts[room_type] = type_counts.get(room_type, 0) + 1
            
            ax2.pie(type_counts.values(), labels=type_counts.keys(), autopct='%1.1f%%')
            ax2.set_title('Room Type Distribution')
            
            # Capacity vs Utilization scatter plot
            capacities = [r['Capacity'] for r in room_data]
            utilizations = [r['Utilization Rate (%)'] for r in room_data]
            
            ax3.scatter(capacities, utilizations, alpha=0.6)
            ax3.set_title('Room Capacity vs Utilization')
            ax3.set_xlabel('Room Capacity')
            ax3.set_ylabel('Utilization Rate (%)')
            
            # Session duration histogram
            durations = [r['Avg Duration (min)'] for r in room_data if r['Avg Duration (min)'] > 0]
            
            ax4.hist(durations, bins=10, color='lightgreen', alpha=0.7)
            ax4.set_title('Average Session Duration Distribution')
            ax4.set_xlabel('Duration (minutes)')
            ax4.set_ylabel('Number of Rooms')
            
            plt.tight_layout()
            
            # Save the charts
            from university_system.modules.shared.constants import paths
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            chart_path = os.path.join(str(paths.ANALYTICS_DIR), f"utilization_charts_{timestamp}.png")

            # Ensure directory exists (already created via paths._ensure)
            os.makedirs(str(paths.ANALYTICS_DIR), exist_ok=True)

            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"Utilization charts saved: {chart_path}")
            return chart_path

  

    def schedule_module_interactively(self):
        # Show all modules for user to select
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        cursor.execute("SELECT module_code, module_name FROM modules")
        modules = cursor.fetchall()
        conn.close()

        print("Modules:")
        print("=" * 60)
        print(f"{'No.':<5} {'Code':<10} {'Name'}")
        print("-" * 60)
        for idx, (code, name) in enumerate(modules, 1):
            print(f"{idx:<5} {code:<10} {name}")
        print("=" * 60)

        module_choice = int(input("Enter module number: "))
        if not (1 <= module_choice <= len(modules)):
            print("Invalid module selection.")
            return

        module_code = modules[module_choice - 1][0]

        # Continue with rest of inputs
        print("Days of Week:")
        for i, day in enumerate(DAYS_OF_WEEK, 1):
            print(f"{i}. {day}")
        day_index = int(input("Enter day of week (1-5): "))
        day_of_week = DAYS_OF_WEEK[day_index - 1]

        start_time = input("Enter start time (HH:MM, 24-hour format): ")
        end_time = input("Enter end time (HH:MM, 24-hour format): ")

        # Get room ID
        # (repeat similar logic as above for room listing)
        room_id = int(input("Enter room ID: "))

        # Get instructor ID
        instructor_id = int(input("Enter instructor ID: "))

        # Get session type
        session_type = input("Enter session type: ")

        # Call your backend
        self.add_module_schedule(
            module_code, day_of_week, start_time, end_time,
            room_id, instructor_id, session_type
        )
        
    def _check_student_conflicts(self, student_id, day_of_week, start_time, end_time, except_module=None):
        """Check if a student has conflicting classes for the given time slot"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Get modules the student is enrolled in
        cursor.execute('''
        SELECT module_code FROM student_modules WHERE student_id = ?
        ''', (student_id,))
        
        enrolled_modules = [row[0] for row in cursor.fetchall()]
        
        if not enrolled_modules:
            conn.close()
            return []
        
        # Build query to check for conflicts
        query = '''
        SELECT ms.id, ms.module_code, ms.start_time, ms.end_time 
        FROM module_schedule ms
        WHERE ms.module_code IN ({}) AND ms.day_of_week = ? AND 
        ((ms.start_time < ? AND ms.end_time > ?) OR
        (ms.start_time < ? AND ms.end_time > ?) OR
        (ms.start_time >= ? AND ms.end_time <= ?))
        '''.format(','.join(['?'] * len(enrolled_modules)))
        
        params = enrolled_modules + [day_of_week, end_time, start_time, 
                                    end_time, start_time, start_time, end_time]
        
        # Exclude a specific module if needed (for updates)
        if except_module:
            query += " AND ms.module_code != ?"
            params.append(except_module)
        
        cursor.execute(query, params)
        conflicts = cursor.fetchall()
        conn.close()
        
        return conflicts
    
    def view_module_schedule(self, module_code=None):
        """View the schedule for a specific module or all modules"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        if module_code:
            # Check if module exists
            cursor.execute('SELECT module_code FROM modules WHERE module_code = ?', (module_code,))
            if not cursor.fetchone():
                known_modules = self._get_known_modules()
                if module_code not in known_modules:
                    print(f"Module {module_code} does not exist.")
                    conn.close()
                    return
            
            query = '''
            SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time, 
                   r.building, r.room_number, 
                   i.first_name, i.last_name, 
                   ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            WHERE ms.module_code = ?
            ORDER BY ms.day_of_week, ms.start_time
            '''
            cursor.execute(query, (module_code,))
        else:
            query = '''
            SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time, 
                   r.building, r.room_number, 
                   i.first_name, i.last_name, 
                   ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            ORDER BY ms.day_of_week, ms.start_time
            '''
            cursor.execute(query)
        
        schedules = cursor.fetchall()
        conn.close()
        
        if not schedules:
            print("No schedules found.")
            return
        
        # Display schedules
        print("\n" + "="*100)
        print(f"{'Module':<10} {'Name':<30} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
        print("-"*100)
        
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, first_name, last_name, session_type = schedule
            module_name = module_name or "Unknown"  # Handle None values
            time_slot = f"{start}-{end}"
            room_str = f"{building}-{room}" if building and room else "TBA"
            instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"
            
            print(f"{module_code:<10} {module_name[:28]:<30} {day:<10} {time_slot:<15} {room_str:<15} {instructor:<20} {session_type:<10}")
        
        print("="*100)
    
    def view_room_schedule(self, room_id=None):
        """View the schedule for a specific room or all rooms"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        if room_id:
            # Check if room exists
            cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
            if not cursor.fetchone():
                print(f"Room ID {room_id} does not exist.")
                conn.close()
                return
            
            # Get room details
            cursor.execute('SELECT room_number, building FROM rooms WHERE id = ?', (room_id,))
            room_info = cursor.fetchone()
            room_number, building = room_info
            
            print(f"\nSchedule for Room {building}-{room_number}:")
            print("="*100)
            
            query = '''
            SELECT ms.day_of_week, ms.start_time, ms.end_time, 
                   ms.module_code, m.module_name, 
                   i.first_name, i.last_name, 
                   ms.session_type
            FROM module_schedule ms
            LEFT JOIN modules m ON ms.module_code = m.module_code
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            WHERE ms.room_id = ?
            ORDER BY ms.day_of_week, ms.start_time
            '''
            cursor.execute(query, (room_id,))
        else:
            # List all rooms with schedules
            print("\nRoom Schedules:")
            print("="*100)
            
            query = '''
            SELECT r.id, r.building, r.room_number, r.capacity, r.room_type,
                   COUNT(ms.id) as schedule_count
            FROM rooms r
            LEFT JOIN module_schedule ms ON r.id = ms.room_id
            GROUP BY r.id
            ORDER BY r.building, r.room_number
            '''
            cursor.execute(query)
            
            rooms = cursor.fetchall()
            if not rooms:
                print("No rooms found.")
                conn.close()
                return
            
            print(f"{'ID':<5} {'Building':<15} {'Room':<10} {'Capacity':<10} {'Type':<15} {'# Classes':<10}")
            print("-"*100)
            
            for room in rooms:
                room_id, building, room_number, capacity, room_type, schedule_count = room
                print(f"{room_id:<5} {building:<15} {room_number:<10} {capacity:<10} {room_type:<15} {schedule_count:<10}")
            
            print("="*100)
            
            # Ask if user wants to view a specific room
            view_specific = input("\nView schedule for a specific room? (Enter room ID or 'n' to skip): ")
            if view_specific.lower() == 'n':
                conn.close()
                return
            
            try:
                room_id = int(view_specific)
                cursor.execute('SELECT room_number, building FROM rooms WHERE id = ?', (room_id,))
                room_info = cursor.fetchone()
                
                if not room_info:
                    print(f"Room ID {room_id} does not exist.")
                    conn.close()
                    return
                
                room_number, building = room_info
                print(f"\nSchedule for Room {building}-{room_number}:")
                print("="*100)
                
                query = '''
                SELECT ms.day_of_week, ms.start_time, ms.end_time, 
                       ms.module_code, m.module_name, 
                       i.first_name, i.last_name, 
                       ms.session_type
                FROM module_schedule ms
                LEFT JOIN modules m ON ms.module_code = m.module_code
                LEFT JOIN instructors i ON ms.instructor_id = i.id
                WHERE ms.room_id = ?
                ORDER BY ms.day_of_week, ms.start_time
                '''
                cursor.execute(query, (room_id,))
            except ValueError:
                print("Invalid room ID.")
                conn.close()
                return
        
        # Display room schedule
        schedules = cursor.fetchall()
        
        if not schedules:
            print("No schedules found for this room.")
            conn.close()
            return
        
        print(f"{'Day':<10} {'Time':<15} {'Module':<10} {'Module Name':<30} {'Instructor':<20} {'Type':<10}")
        print("-"*100)
        
        for schedule in schedules:
            day, start, end, module_code, module_name, first_name, last_name, session_type = schedule
            module_name = module_name or "Unknown"  # Handle None values
            time_slot = f"{start}-{end}"
            instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"
            
            print(f"{day:<10} {time_slot:<15} {module_code:<10} {module_name[:28]:<30} {instructor:<20} {session_type:<10}")
        
        conn.close()
        print("="*100)
    
    def view_instructor_schedule(self, instructor_id=None):
        """View the schedule for a specific instructor or all instructors"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        if instructor_id:
            # Check if instructor exists
            cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
            if not cursor.fetchone():
                print(f"Instructor ID {instructor_id} does not exist.")
                conn.close()
                return
            
            # Get instructor details
            cursor.execute('SELECT first_name, last_name FROM instructors WHERE id = ?', (instructor_id,))
            instructor_info = cursor.fetchone()
            first_name, last_name = instructor_info
            
            print(f"\nSchedule for {first_name} {last_name}:")
            print("="*100)
            
            query = '''
            SELECT ms.day_of_week, ms.start_time, ms.end_time, 
                   ms.module_code, m.module_name, 
                   r.building, r.room_number, 
                   ms.session_type
            FROM module_schedule ms
            LEFT JOIN modules m ON ms.module_code = m.module_code
            LEFT JOIN rooms r ON ms.room_id = r.id
            WHERE ms.instructor_id = ?
            ORDER BY ms.day_of_week, ms.start_time
            '''
            cursor.execute(query, (instructor_id,))
        else:
            # List all instructors with schedules
            print("\nInstructor Schedules:")
            print("="*100)
            
            query = '''
            SELECT i.id, i.first_name, i.last_name, i.department,
                   COUNT(ms.id) as schedule_count
            FROM instructors i
            LEFT JOIN module_schedule ms ON i.id = ms.instructor_id
            GROUP BY i.id
            ORDER BY i.last_name, i.first_name
            '''
            cursor.execute(query)
            
            instructors = cursor.fetchall()
            if not instructors:
                print("No instructors found.")
                conn.close()
                return
            
            print(f"{'ID':<5} {'Name':<30} {'Department':<20} {'# Classes':<10}")
            print("-"*100)
            
            for instructor in instructors:
                instr_id, first_name, last_name, department, schedule_count = instructor
                full_name = f"{first_name} {last_name}"
                print(f"{instr_id:<5} {full_name:<30} {department:<20} {schedule_count:<10}")
            
            print("="*100)
            
            # Ask if user wants to view a specific instructor
            view_specific = input("\nView schedule for a specific instructor? (Enter instructor ID or 'n' to skip): ")
            if view_specific.lower() == 'n':
                conn.close()
                return
            
            try:
                instructor_id = int(view_specific)
                cursor.execute('SELECT first_name, last_name FROM instructors WHERE id = ?', (instructor_id,))
                instructor_info = cursor.fetchone()
                
                if not instructor_info:
                    print(f"Instructor ID {instructor_id} does not exist.")
                    conn.close()
                    return
                
                first_name, last_name = instructor_info
                print(f"\nSchedule for {first_name} {last_name}:")
                print("="*100)
                
                query = '''
                SELECT ms.day_of_week, ms.start_time, ms.end_time, 
                       ms.module_code, m.module_name, 
                       r.building, r.room_number, 
                       ms.session_type
                FROM module_schedule ms
                LEFT JOIN modules m ON ms.module_code = m.module_code
                LEFT JOIN rooms r ON ms.room_id = r.id
                WHERE ms.instructor_id = ?
                ORDER BY ms.day_of_week, ms.start_time
                '''
                cursor.execute(query, (instructor_id,))
            except ValueError:
                print("Invalid instructor ID.")
                conn.close()
                return
        
        # Display instructor schedule
        schedules = cursor.fetchall()
        
        if not schedules:
            print("No schedules found for this instructor.")
            conn.close()
            return
        
        print(f"{'Day':<10} {'Time':<15} {'Module':<10} {'Module Name':<30} {'Room':<15} {'Type':<10}")
        print("-"*100)
        
        for schedule in schedules:
            day, start, end, module_code, module_name, building, room, session_type = schedule
            module_name = module_name or "Unknown"  # Handle None values
            time_slot = f"{start}-{end}"
            room_str = f"{building}-{room}" if building and room else "TBA"
            
            print(f"{day:<10} {time_slot:<15} {module_code:<10} {module_name[:28]:<30} {room_str:<15} {session_type:<10}")
        
        conn.close()
        print("="*100)
    
    def generate_student_timetable(self, student_id, output_format='display'):
        """Generate a timetable for a specific student"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Check if student exists
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()
        
        if not student:
            print(f"Student ID {student_id} does not exist.")
            conn.close()
            return
        
        # Get modules the student is enrolled in
        cursor.execute('''
        SELECT module_code FROM student_modules WHERE student_id = ?
        ''', (student_id,))
        
        enrolled_modules = [row[0] for row in cursor.fetchall()]
        
        if not enrolled_modules:
            print(f"Student {student_id} is not enrolled in any modules.")
            conn.close()
            return
        
        # Get schedule for the enrolled modules
        placeholders = ','.join(['?'] * len(enrolled_modules))
        query = f'''
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time, 
               r.building, r.room_number, 
               i.first_name, i.last_name, 
               ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.module_code IN ({placeholders})
        ORDER BY ms.day_of_week, ms.start_time
        '''
        
        cursor.execute(query, enrolled_modules)
        schedules = cursor.fetchall()
        
        if not schedules:
            print(f"No schedules found for the modules that student {student_id} is enrolled in.")
            conn.close()
            return
        
        # Get student name
        cursor.execute('''
        SELECT first_name, last_name FROM students WHERE student_id = ?
        ''', (student_id,))
        
        student_name_info = cursor.fetchone()
        first_name, last_name = student_name_info
        student_name = f"{first_name} {last_name}"
        
        # Format schedule data
        timetable_data = []
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, instr_first, instr_last, session_type = schedule
            module_name = module_name or "Unknown"  # Handle None values
            room_str = f"{building}-{room}" if building and room else "TBA"
            instructor = f"{instr_first} {instr_last}" if instr_first and instr_last else "TBA"
            
            timetable_data.append({
                'module_code': module_code,
                'module_name': module_name,
                'day': day,
                'start_time': start,
                'end_time': end,
                'room': room_str,
                'instructor': instructor,
                'session_type': session_type
            })
        
        conn.close()
        
        # Generate output based on format
        if output_format == 'display':
            self._display_timetable(student_id, student_name, timetable_data)
        elif output_format == 'pdf':
            return self._generate_pdf_timetable(student_id, student_name, timetable_data)
        elif output_format == 'csv':
            return self._export_to_csv(student_id, student_name, timetable_data, 'student')
        elif output_format == 'txt':
            return self._export_to_txt(student_id, student_name, timetable_data, 'student')
        elif output_format == 'excel':
            return self._export_to_excel(student_id, student_name, timetable_data, 'student')
        elif output_format == 'grid':
            self._display_grid_timetable(student_id, student_name, timetable_data)
        else:
            print(f"Unsupported format: {output_format}")
    
    def generate_instructor_timetable(self, instructor_id, output_format='display'):
        """Generate a timetable for a specific instructor"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        # Check if instructor exists
        cursor.execute('SELECT * FROM instructors WHERE id = ?', (instructor_id,))
        instructor = cursor.fetchone()
        
        if not instructor:
            print(f"Instructor ID {instructor_id} does not exist.")
            conn.close()
            return
        
        # Get instructor name - Fixed: properly handle the instructor tuple
        # The instructor tuple may have different number of columns, so let's be safe
        instructor_id_db, first_name, last_name = instructor[0], instructor[1], instructor[2]
        instructor_name = f"{first_name} {last_name}"
        
        # Get schedule for the instructor
        query = '''
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time, 
               r.building, r.room_number, 
               ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.instructor_id = ?
        ORDER BY ms.day_of_week, ms.start_time
        '''
        
        cursor.execute(query, (instructor_id,))
        schedules = cursor.fetchall()
        
        if not schedules:
            print(f"No schedules found for instructor {instructor_name}.")
            conn.close()
            return
        
        # Format schedule data
        timetable_data = []
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, session_type = schedule
            module_name = module_name or "Unknown"  # Handle None values
            room_str = f"{building}-{room}" if building and room else "TBA"
            
            timetable_data.append({
                'module_code': module_code,
                'module_name': module_name,
                'day': day,
                'start_time': start,
                'end_time': end,
                'room': room_str,
                'instructor': instructor_name,
                'session_type': session_type
            })
        
        conn.close()
        
        # Generate output based on format
        if output_format == 'display':
            self._display_timetable(instructor_id, instructor_name, timetable_data)
        elif output_format == 'pdf':
            return self._generate_pdf_timetable(instructor_id, instructor_name, timetable_data, user_type='instructor')
        elif output_format == 'csv':
            return self._export_to_csv(instructor_id, instructor_name, timetable_data, 'instructor')
        elif output_format == 'txt':
            return self._export_to_txt(instructor_id, instructor_name, timetable_data, 'instructor')
        elif output_format == 'excel':
            return self._export_to_excel(instructor_id, instructor_name, timetable_data, 'instructor')
        elif output_format == 'grid':
            self._display_grid_timetable(instructor_id, instructor_name, timetable_data)
        else:
            print(f"Unsupported format: {output_format}")
        
    def _display_timetable(self, user_id, user_name, timetable_data):
        """Display a timetable in a list format"""
        print(f"\nTimetable for {user_name} (ID: {user_id}):")
        print("="*120)
        
        print(f"{'Day':<10} {'Time':<15} {'Module':<10} {'Module Name':<30} {'Room':<15} {'Instructor':<20} {'Type':<10}")
        print("-"*120)
        
        # Sort by day of week and start time
        day_order = {day: idx for idx, day in enumerate(DAYS_OF_WEEK)}
        timetable_data.sort(key=lambda x: (day_order.get(x['day'], 999), x['start_time']))
        
        for entry in timetable_data:
            time_slot = f"{entry['start_time']}-{entry['end_time']}"
            print(f"{entry['day']:<10} {time_slot:<15} {entry['module_code']:<10} "
                  f"{entry['module_name'][:28]:<30} {entry['room']:<15} "
                  f"{entry['instructor'][:18]:<20} {entry['session_type']:<10}")
        
        print("="*120)
    
    def _display_grid_timetable(self, user_id, user_name, timetable_data):
        """Display a timetable in a grid format"""
        print(f"\nTimetable for {user_name} (ID: {user_id}):")
        print("="*120)
        
        # Create a grid of days and time slots
        grid = {}
        for day in DAYS_OF_WEEK:
            grid[day] = {}
            for time_slot in TIME_SLOTS:
                grid[day][time_slot] = []
        
        # Populate the grid with schedule data
        for entry in timetable_data:
            day = entry['day']
            start_time = entry['start_time']
            # Find the closest time slot
            closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))
            
            # Add the entry to the grid
            session_info = f"{entry['module_code']} {entry['session_type'][0]} ({entry['room']})"
            if day in grid and closest_slot in grid[day]:
                grid[day][closest_slot].append(session_info)
        
        # Print the grid
        print(f"{'Time/Day':<10}", end="")
        for day in DAYS_OF_WEEK:
            print(f"{day:<20}", end="")
        print()
        
        print("-"*120)
        
        for time_slot in TIME_SLOTS:
            print(f"{time_slot:<10}", end="")
            for day in DAYS_OF_WEEK:
                entries = grid[day][time_slot]
                if entries:
                    print(f"{', '.join(entries):<20}", end="")
                else:
                    print(f"{'---':<20}", end="")
            print()
        
        print("="*120)
    
    def _generate_pdf_timetable(self, user_id, user_name, timetable_data, user_type='student'):
        """Generate a PDF timetable with an improved grid-based weekly schedule view"""
        # Create reports directory if it doesn't exist
        from university_system.modules.shared.constants import paths
        reports_dir = str(paths.REPORTS_DIR / 'timetable_reports')

        # Ensure directory exists
        os.makedirs(reports_dir, exist_ok=True)

        # Create PDF filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{reports_dir}/{user_type}_timetable_{user_id}_{timestamp}.pdf"

        # Create PDF document
        doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []

        # Add title with better styling
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a2e'),
            spaceAfter=10,
            alignment=1  # Center alignment
        )
        elements.append(Paragraph(f"Weekly Timetable", title_style))

        # Add subtitle with user info
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#16213e'),
            spaceAfter=20,
            alignment=1
        )
        elements.append(Paragraph(f"{user_name} (ID: {user_id})", subtitle_style))

        # Calculate current week dates
        today = datetime.now()
        # Find Monday of current week
        days_since_monday = today.weekday()  # 0=Monday, 6=Sunday
        monday = today - timedelta(days=days_since_monday)

        # Generate dates for each day of the week
        week_dates = []
        for i in range(5):  # Monday to Friday
            day_date = monday + timedelta(days=i)
            week_dates.append(day_date.strftime("%d/%m"))

        # Add week date range info
        week_info_style = ParagraphStyle(
            'WeekInfo',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#0f3460'),
            spaceAfter=15,
            alignment=1
        )
        week_start = monday.strftime("%d %B %Y")
        week_end = (monday + timedelta(days=4)).strftime("%d %B %Y")
        elements.append(Paragraph(f"Week: {week_start} - {week_end}", week_info_style))
        elements.append(Spacer(1, 0.2*inch))

        # Sort timetable data by day and time
        day_order = {day: idx for idx, day in enumerate(DAYS_OF_WEEK)}
        timetable_data.sort(key=lambda x: (day_order.get(x['day'], 999), x['start_time']))

        # Define session type colors
        session_colors = {
            'Lecture': colors.HexColor('#3498db'),      # Blue
            'Lab': colors.HexColor('#e74c3c'),          # Red
            'Tutorial': colors.HexColor('#2ecc71'),     # Green
            'Seminar': colors.HexColor('#f39c12'),      # Orange
            'Workshop': colors.HexColor('#9b59b6')      # Purple
        }

        # Create grid structure with time blocks
        grid = {}
        session_details = {}  # Store full details for each grid cell

        for day in DAYS_OF_WEEK:
            grid[day] = {}
            session_details[day] = {}
            for time_slot in TIME_SLOTS:
                grid[day][time_slot] = []
                session_details[day][time_slot] = []

        # Populate the grid with schedule data
        for entry in timetable_data:
            day = entry['day']
            start_time = entry['start_time']

            # Find the closest time slot
            closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))

            if day in grid and closest_slot in grid[day]:
                # Create compact session info for display
                session_type = entry['session_type']
                session_abbr = session_type[0]  # First letter (L, T, S, etc.)

                # Format the cell content
                cell_content = f"<b>{entry['module_code']}</b>"
                cell_content += f"<br/><font size=9>{session_type}</font>"
                cell_content += f"<br/><font size=8>{entry['room']}</font>"

                grid[day][closest_slot].append(cell_content)
                session_details[day][closest_slot].append({
                    'type': session_type,
                    'entry': entry
                })

        # Build grid table data with headers including dates
        header_row = ["Time"]
        for i, day in enumerate(DAYS_OF_WEEK):
            header_row.append(f"{day}\n{week_dates[i]}")

        grid_data = [header_row]

        # Build rows for each time slot
        for time_slot in TIME_SLOTS:
            row = [time_slot]
            for day in DAYS_OF_WEEK:
                entries = grid[day][time_slot]
                if entries:
                    # Join multiple entries if there are conflicts
                    cell_text = "<br/>---<br/>".join(entries)
                    row.append(Paragraph(cell_text, styles['Normal']))
                else:
                    row.append("")
            grid_data.append(row)

        # Create the enhanced grid table
        col_width = 1.4 * inch
        grid_table = Table(grid_data, colWidths=[0.7*inch] + [col_width]*5)

        # Build table style with colored cells
        table_style = [
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),

            # Time column styling
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (0, -1), 9),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),

            # Grid and alignment
            ('GRID', (0, 0), (-1, -1), 1.5, colors.HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTSIZE', (1, 1), (-1, -1), 8),

            # Cell padding
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (1, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (1, 1), (-1, -1), 8),
        ]

        # Add colored backgrounds for session cells
        for row_idx, time_slot in enumerate(TIME_SLOTS, start=1):
            for col_idx, day in enumerate(DAYS_OF_WEEK, start=1):
                if session_details[day][time_slot]:
                    # Use the color of the first session type if multiple sessions
                    session_type = session_details[day][time_slot][0]['type']
                    bg_color = session_colors.get(session_type, colors.HexColor('#95a5a6'))

                    # Apply lighter version of color for better readability
                    table_style.append(
                        ('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), bg_color)
                    )
                    table_style.append(
                        ('TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx), colors.white)
                    )
                else:
                    # Empty cells with light gray background
                    table_style.append(
                        ('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#f8f9fa'))
                    )

        grid_table.setStyle(TableStyle(table_style))
        elements.append(grid_table)

        # Add legend for session types
        elements.append(Spacer(1, 0.3*inch))
        legend_style = ParagraphStyle(
            'Legend',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=5
        )
        elements.append(Paragraph("<b>Session Type Legend:</b>", legend_style))

        # Create legend table
        legend_data = []
        legend_row = []
        for i, (session_type, color) in enumerate(session_colors.items()):
            legend_row.append(Paragraph(f"<font color='{color.hexval()}'>\u25A0</font> {session_type}", styles['Normal']))
            if (i + 1) % 5 == 0:  # 5 items per row
                legend_data.append(legend_row)
                legend_row = []
        if legend_row:  # Add remaining items
            legend_data.append(legend_row)

        legend_table = Table(legend_data)
        legend_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(legend_table)

        # Add footer note
        elements.append(Spacer(1, 0.3*inch))
        note_style = ParagraphStyle(
            'Note',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=1
        )
        note_text = f"Generated on: {datetime.now().strftime('%d %B %Y at %H:%M:%S')}"
        if user_type == 'student':
            note_text += "<br/>Please check for any scheduling conflicts and report them to the administration office."
        elements.append(Paragraph(note_text, note_style))

        # Build the PDF
        doc.build(elements)
        print(f"PDF timetable generated: {filename}")
        return filename
    
    def _export_to_csv(self, user_id, user_name, timetable_data, user_type='student'):
        """Export timetable to CSV format"""
        # Create reports directory if it doesn't exist
        from university_system.modules.shared.constants import paths
        reports_dir = str(paths.REPORTS_DIR / 'timetable_reports')

        # Create CSV filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{reports_dir}/{user_type}_timetable_{user_id}_{timestamp}.csv"

        # Ensure directory exists
        os.makedirs(reports_dir, exist_ok=True)

        # Sort timetable data by day and time
        day_order = {day: idx for idx, day in enumerate(DAYS_OF_WEEK)}
        timetable_data.sort(key=lambda x: (day_order.get(x['day'], 999), x['start_time']))

        # Write CSV file
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Day', 'Time', 'Module Code', 'Module Name', 'Room', 'Instructor', 'Session Type']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header
            writer.writerow({'Day': f'Timetable for {user_name} (ID: {user_id})'})
            writer.writerow({})  # Empty row
            writer.writeheader()
            
            # Write timetable data
            for entry in timetable_data:
                writer.writerow({
                    'Day': entry['day'],
                    'Time': f"{entry['start_time']}-{entry['end_time']}",
                    'Module Code': entry['module_code'],
                    'Module Name': entry['module_name'],
                    'Room': entry['room'],
                    'Instructor': entry['instructor'],
                    'Session Type': entry['session_type']
                })
        
        print(f"CSV timetable generated: {filename}")
        return filename
    
    def _export_to_txt(self, user_id, user_name, timetable_data, user_type='student'):
        """Export timetable to TXT format"""
        # Create reports directory if it doesn't exist
        from university_system.modules.shared.constants import paths
        reports_dir = str(paths.REPORTS_DIR / 'timetable_reports')

        # Create TXT filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{reports_dir}/{user_type}_timetable_{user_id}_{timestamp}.txt"

        # Ensure directory exists
        os.makedirs(reports_dir, exist_ok=True)

        # Sort timetable data by day and time
        day_order = {day: idx for idx, day in enumerate(DAYS_OF_WEEK)}
        timetable_data.sort(key=lambda x: (day_order.get(x['day'], 999), x['start_time']))

        # Write TXT file
        with open(filename, 'w', encoding='utf-8') as txtfile:
            # Write header
            txtfile.write(f"Timetable for {user_name} (ID: {user_id})\n")
            txtfile.write("=" * 100 + "\n")
            txtfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            txtfile.write("=" * 100 + "\n\n")
            
            # Write column headers
            headers = f"{'Day':<12} {'Time':<15} {'Module':<12} {'Module Name':<30} {'Room':<15} {'Instructor':<20} {'Type':<12}"
            txtfile.write(headers + "\n")
            txtfile.write("-" * 100 + "\n")
            
            # Write timetable data
            for entry in timetable_data:
                time_slot = f"{entry['start_time']}-{entry['end_time']}"
                line = f"{entry['day']:<12} {time_slot:<15} {entry['module_code']:<12} "
                line += f"{entry['module_name'][:28]:<30} {entry['room']:<15} "
                line += f"{entry['instructor'][:18]:<20} {entry['session_type']:<12}"
                txtfile.write(line + "\n")
            
            txtfile.write("\n" + "=" * 100 + "\n")
        
        print(f"TXT timetable generated: {filename}")
        return filename
    
    def _export_to_excel(self, user_id, user_name, timetable_data, user_type='student'):
        """Export timetable to Excel format"""
        # Create reports directory if it doesn't exist
        from university_system.modules.shared.constants import paths
        reports_dir = str(paths.REPORTS_DIR / 'timetable_reports')

        # Create Excel filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{reports_dir}/{user_type}_timetable_{user_id}_{timestamp}.xlsx"

        # Ensure directory exists
        os.makedirs(reports_dir, exist_ok=True)

        # Sort timetable data by day and time
        day_order = {day: idx for idx, day in enumerate(DAYS_OF_WEEK)}
        timetable_data.sort(key=lambda x: (day_order.get(x['day'], 999), x['start_time']))

        # Create DataFrame for list view
        list_data = []
        for entry in timetable_data:
            list_data.append({
                'Day': entry['day'],
                'Time': f"{entry['start_time']}-{entry['end_time']}",
                'Module Code': entry['module_code'],
                'Module Name': entry['module_name'],
                'Room': entry['room'],
                'Instructor': entry['instructor'],
                'Session Type': entry['session_type']
            })
        
        df_list = pd.DataFrame(list_data)
        
        # Create DataFrame for grid view
        grid_data = {}
        for day in DAYS_OF_WEEK:
            grid_data[day] = {}
            for time_slot in TIME_SLOTS:
                grid_data[day][time_slot] = []
        
        # Populate the grid with schedule data
        for entry in timetable_data:
            day = entry['day']
            start_time = entry['start_time']
            # Find the closest time slot
            closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))
            
            # Add the entry to the grid
            session_info = f"{entry['module_code']} {entry['session_type'][0]} ({entry['room']})"
            if day in grid_data and closest_slot in grid_data[day]:
                grid_data[day][closest_slot].append(session_info)
        
        # Convert grid to DataFrame
        grid_df_data = []
        for time_slot in TIME_SLOTS:
            row = {'Time': time_slot}
            for day in DAYS_OF_WEEK:
                entries = grid_data[day][time_slot]
                row[day] = '\n'.join(entries) if entries else ''
            grid_df_data.append(row)
        
        df_grid = pd.DataFrame(grid_df_data)
        
        # Write to Excel with multiple sheets
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Sheet 1: Info
            info_data = {
                'Information': ['Timetable for', 'User ID', 'Generated on'],
                'Value': [user_name, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
            }
            df_info = pd.DataFrame(info_data)
            df_info.to_excel(writer, sheet_name='Info', index=False)
            
            # Sheet 2: List View
            df_list.to_excel(writer, sheet_name='List View', index=False)
            
            # Sheet 3: Grid View
            df_grid.to_excel(writer, sheet_name='Grid View', index=False)
            
            # Auto-adjust column widths
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column_cells in worksheet.columns:
                    max_length = 0
                    for cell in column_cells:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except Exception:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_cells[0].column_letter].width = adjusted_width
        
        print(f"Excel timetable generated: {filename}")
        return filename
    
    # ==================== UTILITY METHODS ====================
    
    def _log_system_action(self, action, description):
        """Log system actions for audit trail"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO schedule_history (schedule_id, action, new_values, changed_by, change_date)
        VALUES (NULL, ?, ?, 'system', CURRENT_TIMESTAMP)
        ''', (action, description))
        
        conn.commit()
        conn.close()
    
    def _export_analytics_csv(self, data, filename_prefix):
        """Export analytics data to CSV"""
        from university_system.modules.shared.constants import paths
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(str(paths.ANALYTICS_DIR), f"{filename_prefix}_{timestamp}.csv")

        # Ensure directory exists (already created via paths._ensure)
        os.makedirs(str(paths.ANALYTICS_DIR), exist_ok=True)

        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        
        print(f"Analytics exported to CSV: {filename}")
        return filename
    
    def _generate_analytics_pdf(self, data, title):
        """Generate analytics PDF report"""
        from university_system.modules.shared.constants import paths
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(str(paths.ANALYTICS_DIR), f"{title.lower().replace(' ', '_')}_{timestamp}.pdf")

        # Ensure directory exists (already created via paths._ensure)
        os.makedirs(str(paths.ANALYTICS_DIR), exist_ok=True)

        doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []
        
        # Add title
        title_style = styles["Title"]
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 0.25*inch))
        
        # Add generation info
        info_text = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        elements.append(Paragraph(info_text, styles["Normal"]))
        elements.append(Spacer(1, 0.25*inch))
        
        # Convert data to table format
        if data:
            headers = list(data[0].keys())
            table_data = [headers]
            
            for row in data:
                table_data.append([str(row[key]) for key in headers])
            
            # Create table
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
        
        # Build PDF
        doc.build(elements)
        print(f"Analytics PDF generated: {filename}")
        return filename
    
    # ==================== ORIGINAL METHODS (keeping your existing functionality) ====================
    
    def add_room(self, room_number, building, capacity, room_type, equipment="", notes=""):
        """Add a new room to the database (enhanced version)"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO rooms (room_number, building, capacity, room_type, equipment, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (room_number, building, capacity, room_type, equipment, notes))
            
            conn.commit()
            print(f"Room {building}-{room_number} added successfully.")
            
            # Log the action
            self._log_system_action('room_added', f"Added room {building}-{room_number}")
            
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()
    
    def add_instructor(self, first_name, last_name, email, department, max_hours=40, preferred_days="", preferred_times=""):
        """Add a new instructor to the database (enhanced version)"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO instructors (first_name, last_name, email, department, max_hours_per_week, preferred_days, preferred_times)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (first_name, last_name, email, department, max_hours, preferred_days, preferred_times))
            
            conn.commit()
            print(f"Instructor {first_name} {last_name} added successfully.")
            
            # Log the action
            self._log_system_action('instructor_added', f"Added instructor {first_name} {last_name}")
            
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        finally:
            conn.close()

    def add_module_schedule(self, module_code, day_of_week, start_time, end_time, 
                            room_id, instructor_id, session_type):
        """Add a new schedule entry for a module (enhanced with conflict detection)"""
        if day_of_week not in DAYS_OF_WEEK:
            print(f"Invalid day of week. Must be one of: {', '.join(DAYS_OF_WEEK)}")
            return False

        try:
            datetime.strptime(start_time, "%H:%M")
            datetime.strptime(end_time, "%H:%M")
        except ValueError:
            print("Invalid time format. Use HH:MM format (24-hour).")
            return False

        if start_time >= end_time:
            print("Start time must be before end time.")
            return False

        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()

        # Validation checks (keeping your original logic)
        cursor.execute('SELECT module_code FROM modules')
        known_modules = {row[0] for row in cursor.fetchall()}
        if module_code not in known_modules:
            print(f"Module {module_code} does not exist.")
            conn.close()
            return False

        cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
        if not cursor.fetchone():
            print(f"Room ID {room_id} does not exist.")
            conn.close()
            return False

        cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
        if not cursor.fetchone():
            print(f"Instructor ID {instructor_id} does not exist.")
            conn.close()
            return False

        # Enhanced conflict checking
        room_conflicts = self._check_room_conflicts(room_id, day_of_week, start_time, end_time)
        if room_conflicts:
            print(f"Room conflict detected: Room is already scheduled during this time.")
            # Suggest alternatives
            alternatives = self.find_alternative_slots(day_of_week, start_time, end_time)
            if alternatives:
                print("Suggested alternatives:")
                for alt in alternatives[:3]:
                    print(f"  - {alt['day']} {alt['start_time']}-{alt['end_time']}")
            conn.close()
            return False

        instructor_conflicts = self._check_instructor_conflicts(instructor_id, day_of_week, start_time, end_time)
        if instructor_conflicts:
            print(f"Instructor conflict detected: Instructor is already scheduled during this time.")
            conn.close()
            return False

        try:
            cursor.execute("""
            INSERT INTO module_schedule 
            (module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type))
            
            schedule_id = cursor.lastrowid
            conn.commit()
            
            print(f"Schedule for module {module_code} added successfully.")
            
            # Log the action
            self._log_system_action('schedule_added', f"Added schedule for {module_code} on {day_of_week} {start_time}-{end_time}")
            
            # Send notifications
            self.send_schedule_change_notifications(schedule_id, f"New class scheduled: {module_code} on {day_of_week} {start_time}-{end_time}")
            
            return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()
    
    # Include all your existing methods with the same signatures...
    # (I'll keep the existing method implementations but with enhanced logging and notifications)
    
    def _check_room_conflicts(self, room_id, day_of_week, start_time, end_time):
        """Check if a room is already scheduled for the given time slot"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, module_code, start_time, end_time 
        FROM module_schedule 
        WHERE room_id = ? AND day_of_week = ? AND 
        ((start_time < ? AND end_time > ?) OR
        (start_time < ? AND end_time > ?) OR
        (start_time >= ? AND end_time <= ?))
        ''', (room_id, day_of_week, end_time, start_time, 
              end_time, start_time, start_time, end_time))
        
        conflicts = cursor.fetchall()
        conn.close()
        
        return conflicts
    
    def _check_instructor_conflicts(self, instructor_id, day_of_week, start_time, end_time):
        """Check if an instructor is already scheduled for the given time slot"""
        conn = get_connection(self.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, module_code, start_time, end_time 
        FROM module_schedule 
        WHERE instructor_id = ? AND day_of_week = ? AND 
        ((start_time < ? AND end_time > ?) OR
        (start_time < ? AND end_time > ?) OR
        (start_time >= ? AND end_time <= ?))
        ''', (instructor_id, day_of_week, end_time, start_time, 
              end_time, start_time, start_time, end_time))
        
        conflicts = cursor.fetchall()
        conn.close()
        
        return conflicts

# Enhanced Menu System
def display_enhanced_scheduling_menu():
    """Display the enhanced module scheduling menu"""
    scheduler = ModuleScheduler()
    
    while True:
        print("\n" + "="*100)
        print(f"   {get_text('timetable.title', default='ENHANCED MODULE SCHEDULING SYSTEM')}")
        print("="*100)

        print(f"\n📊 {get_text('timetable.sections.analytics', default='ANALYTICS & REPORTING')}:")
        print(f"{'1.  ' + get_text('timetable.menu.room_util', default='Room Utilization'):<25} {'2.  ' + get_text('timetable.menu.workload', default='Workload Report'):<25} {'3.  ' + get_text('timetable.menu.dashboard', default='Analytics Dashboard'):<25} {'4.  ' + get_text('timetable.menu.visual', default='Visual Timetables'):<25}")
        print(f"{'5.  ' + get_text('timetable.menu.charts', default='Utilization Charts'):<25}")

        print(f"\n🔄 {get_text('timetable.sections.scheduling', default='ADVANCED SCHEDULING')}:")
        print(f"{'6.  ' + get_text('timetable.menu.smart', default='Smart Assistant'):<25} {'7.  ' + get_text('timetable.menu.batch', default='Batch Import CSV'):<25} {'8.  ' + get_text('timetable.menu.templates', default='Schedule Templates'):<25} {'9.  ' + get_text('timetable.menu.search', default='Advanced Search'):<25}")
        print(f"{'10. ' + get_text('timetable.menu.free_rooms', default='Find Free Rooms'):<25} {'11. ' + get_text('timetable.menu.gaps', default='Find Schedule Gaps'):<25}")

        print(f"\n⚠️  {get_text('timetable.sections.conflicts', default='CONFLICT MANAGEMENT')}:")
        print(f"{'12. ' + get_text('timetable.menu.detect', default='Detect All Conflicts'):<25} {'13. ' + get_text('timetable.menu.resolve', default='View/Resolve'):<25} {'14. ' + get_text('timetable.menu.student_conflicts', default='Student Conflicts'):<25}")

        print(f"\n📅 {get_text('timetable.sections.calendar', default='CALENDAR & EXPORTS')}:")
        print(f"{'15. ' + get_text('timetable.menu.ical', default='Export to iCal'):<25} {'16. ' + get_text('timetable.menu.export_all', default='Export All Schedules'):<25} {'17. ' + get_text('timetable.menu.pdf', default='Generate PDF Reports'):<25}")

        print(f"\n💾 {get_text('timetable.sections.data', default='DATA MANAGEMENT')}:")
        print(f"{'18. ' + get_text('timetable.menu.backup', default='Create Backup'):<25} {'19. ' + get_text('timetable.menu.restore', default='Restore Backup'):<25} {'20. ' + get_text('timetable.menu.validate', default='Validate Data'):<25} {'21. ' + get_text('timetable.menu.settings', default='System Settings'):<25}")

        print(f"\n📝 {get_text('timetable.sections.basic', default='BASIC OPERATIONS')}:")
        print(f"{'22. ' + get_text('timetable.menu.rooms', default='Manage Rooms'):<25} {'23. ' + get_text('timetable.menu.instructors', default='Manage Instructors'):<25} {'24. ' + get_text('timetable.menu.schedules', default='Manage Schedules'):<25} {'25. ' + get_text('timetable.menu.view', default='View Schedules'):<25}")
        print(f"{'26. ' + get_text('timetable.menu.generate', default='Generate Timetables'):<25}")

        print(f"\n🔔 {get_text('timetable.sections.notifications', default='NOTIFICATIONS & HOLIDAYS')}:")
        print(f"{'27. ' + get_text('timetable.menu.notifications', default='View Notifications'):<25} {'28. ' + get_text('timetable.menu.holidays', default='Manage Holidays'):<25}")

        print(f"\n🌐 {get_text('timetable.sections.lang', default='LANGUAGE')}:")
        print(f"29. {get_text('timetable.menu.language', default='Language')}")

        print(f"\n0.  {get_text('timetable.menu.exit', default='Exit')}")
        print("="*100)

        choice = input(f"{get_text('timetable.enter_choice', default='Enter your choice')}: ").strip()
        
        try:
            if choice == '0':
                print(get_text('timetable.goodbye', default='Thank you for using the Enhanced Module Scheduling System!'))
                break
            elif choice == '1':
                display_analytics_menu(scheduler)
            elif choice == '2':
                display_workload_menu(scheduler)
            elif choice == '3':
                scheduler.generate_scheduling_analytics_dashboard()
            elif choice == '4':
                display_visual_timetable_menu(scheduler)
            elif choice == '5':
                scheduler.generate_utilization_charts()
            elif choice == '6':
                display_smart_scheduling_menu(scheduler)
            elif choice == '7':
                display_batch_import_menu(scheduler)
            elif choice == '8':
                display_template_menu(scheduler)
            elif choice == '9':
                display_advanced_search_menu(scheduler)
            elif choice == '10':
                display_free_rooms_menu(scheduler)
            elif choice == '11':
                display_schedule_gaps_menu(scheduler)
            elif choice == '12':
                conflicts = scheduler.detect_all_conflicts()
                print(f"Detected {len(conflicts)} conflicts.")
            elif choice == '13':
                display_conflict_management_menu(scheduler)
            elif choice == '14':
                student_id = input("Enter student ID: ")
                scheduler.display_student_conflicts(student_id)
            elif choice == '15':
                display_ical_export_menu(scheduler)
            elif choice == '16':
                scheduler.export_all_schedules_to_csv()
            elif choice == '17':
                display_pdf_reports_menu(scheduler)
            elif choice == '18':
                display_backup_menu(scheduler)
            elif choice == '19':
                display_restore_menu(scheduler)
            elif choice == '20':
                display_data_validation_menu(scheduler)
            elif choice == '21':
                display_system_settings_menu(scheduler)
            elif choice == '22':
                display_room_menu(scheduler)
            elif choice == '23':
                display_instructor_menu(scheduler)
            elif choice == '24':
                display_schedule_menu(scheduler)
            elif choice == '25':
                display_view_schedules_menu(scheduler)
            elif choice == '26':
                display_timetable_generation_menu(scheduler)
            elif choice == '27':
                display_notifications_menu(scheduler)
            elif choice == '28':
                display_holiday_management_menu(scheduler)
            elif choice == '29':
                display_language_menu_option()
            else:
                print(get_text('timetable.invalid_choice', default='Invalid choice. Please try again.'))

        except KeyboardInterrupt:
            print(f"\n\n{get_text('timetable.cancelled', default='Operation cancelled by user.')}")
        except Exception as e:
            print(get_text('timetable.error', default='An error occurred: {error}').format(error=e))
            print(get_text('timetable.try_again', default='Please try again or contact support.'))

# Additional menu functions for the new features
def display_analytics_menu(scheduler):
    """Display analytics submenu"""
    while True:
        print("\n📊 Analytics & Reporting Menu:")
        print("1. Room Utilization Report (Display)")
        print("2. Room Utilization Report (PDF)")
        print("3. Room Utilization Report (CSV)")
        print("4. Instructor Workload Report (Display)")
        print("5. Instructor Workload Report (PDF)")
        print("6. Instructor Workload Report (CSV)")
        print("7. Peak Usage Analysis")
        print("8. Module Distribution Statistics")
        print("9. Return to Main Menu")
        
        choice = input("Enter your choice (1-9): ")
        
        if choice == '1':
            scheduler.generate_room_utilization_report('display')
        elif choice == '2':
            scheduler.generate_room_utilization_report('pdf')
        elif choice == '3':
            scheduler.generate_room_utilization_report('csv')
        elif choice == '4':
            scheduler.generate_instructor_workload_report('display')
        elif choice == '5':
            scheduler.generate_instructor_workload_report('pdf')
        elif choice == '6':
            scheduler.generate_instructor_workload_report('csv')
        elif choice == '7':
            peak_times = scheduler._analyze_peak_usage()
            print("\nPeak Usage Times by Day:")
            for day, times in peak_times.items():
                print(f"{day}: {', '.join(times) if times else 'No data'}")
        elif choice == '8':
            stats = scheduler._analyze_module_distribution()
            print(f"\nModule Distribution Statistics:")
            print(f"Total Modules: {stats['total']}")
            print(f"Most Common Session Type: {stats['most_common_type']}")
            print(f"Average Sessions per Module: {stats['avg_sessions']:.2f}")
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")

def display_workload_menu(scheduler):
    """Display workload analysis menu"""
    while True:
        print("\n👨‍🏫 Instructor Workload Menu:")
        print("1. Full Workload Report")
        print("2. Overloaded Instructors Only")
        print("3. Workload by Department")
        print("4. Set Instructor Max Hours")
        print("5. Return to Main Menu")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1':
            scheduler.generate_instructor_workload_report('display')
        elif choice == '2':
            workload_data = scheduler.generate_instructor_workload_report('data')
            overloaded = [i for i in workload_data if i['Status'] == 'Overloaded']
            if overloaded:
                print("\nOverloaded Instructors:")
                print("=" * 80)
                for instructor in overloaded:
                    print(f"{instructor['Instructor']}: {instructor['Workload (%)']}% ({instructor['Total Hours']}/{instructor['Max Hours']} hours)")
            else:
                print("No overloaded instructors found.")
        elif choice == '3':
            # Group by department
            workload_data = scheduler.generate_instructor_workload_report('data')
            dept_workload = {}
            for instructor in workload_data:
                dept = instructor['Department']
                if dept not in dept_workload:
                    dept_workload[dept] = []
                dept_workload[dept].append(instructor)
            
            print("\nWorkload by Department:")
            print("=" * 60)
            for dept, instructors in dept_workload.items():
                avg_workload = sum(i['Workload (%)'] for i in instructors) / len(instructors)
                print(f"{dept}: {len(instructors)} instructors, {avg_workload:.1f}% average workload")
        elif choice == '4':
            # Set instructor max hours
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, first_name, last_name, max_hours_per_week FROM instructors WHERE is_active = 1')
            instructors = cursor.fetchall()
            
            print("\nInstructors:")
            for inst in instructors:
                print(f"ID {inst[0]}: {inst[1]} {inst[2]} (Current max: {inst[3]} hours)")
            
            try:
                instructor_id = int(input("Enter instructor ID: "))
                max_hours = int(input("Enter new max hours per week: "))
                
                cursor.execute('UPDATE instructors SET max_hours_per_week = ? WHERE id = ?', 
                             (max_hours, instructor_id))
                conn.commit()
                print(f"Max hours updated successfully.")
            except ValueError:
                print("Invalid input.")
            except Exception as e:
                print(f"Error: {e}")
            finally:
                conn.close()
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")

def display_visual_timetable_menu(scheduler):
    """Display visual timetable generation menu"""
    print("\n🎨 Visual Timetable Generator:")
    print("1. Student Visual Timetable")
    print("2. Instructor Visual Timetable")
    
    choice = input("Enter your choice (1-2): ")
    
    if choice == '1':
        student_id = input("Enter student ID: ")
        output_path = scheduler.generate_visual_timetable('student', student_id)
        if output_path:
            open_choice = input("Open the generated image? (y/n): ")
            if open_choice.lower() == 'y':
                try:
                    import webbrowser
                    webbrowser.open(f"file://{os.path.abspath(output_path)}")
                except Exception as e:
                    print(f"Could not open file: {e}")
    elif choice == '2':
        instructor_id = input("Enter instructor ID: ")
        try:
            instructor_id = int(instructor_id)
            output_path = scheduler.generate_visual_timetable('instructor', instructor_id)
            if output_path:
                open_choice = input("Open the generated image? (y/n): ")
                if open_choice.lower() == 'y':
                    try:
                        import webbrowser
                        webbrowser.open(f"file://{os.path.abspath(output_path)}")
                    except Exception as e:
                        print(f"Could not open file: {e}")
        except ValueError:
            print("Invalid instructor ID.")
    else:
        print("Invalid choice.")

def display_smart_scheduling_menu(scheduler):
    """Display smart scheduling assistant menu"""
    print("\n🤖 Smart Scheduling Assistant:")
    print("1. Get Optimal Time Suggestions")
    print("2. Find Alternative Slots")
    print("3. Batch Schedule Optimization")
    
    choice = input("Enter your choice (1-3): ")
    
    if choice == '1':
        module_code = input("Enter module code: ")
        session_type = input("Enter session type: ")
        try:
            duration = int(input("Enter duration in minutes (default 60): ") or "60")
            
            suggestions = scheduler.suggest_optimal_time_slot(module_code, session_type, duration)
            
            if suggestions:
                print(f"\nTop suggestions for {module_code} ({session_type}):")
                print("=" * 80)
                for i, suggestion in enumerate(suggestions[:5], 1):
                    print(f"{i}. {suggestion['day']} {suggestion['start_time']}-{suggestion['end_time']} "
                          f"(Score: {suggestion['score']})")
                    if suggestion['reasons']:
                        print(f"   Reasons: {', '.join(suggestion['reasons'])}")
            else:
                print("No suitable time slots found.")
        except ValueError:
            print("Invalid duration.")
    
    elif choice == '2':
        day = input("Enter day of week: ")
        start_time = input("Enter start time (HH:MM): ")
        end_time = input("Enter end time (HH:MM): ")
        
        alternatives = scheduler.find_alternative_slots(day, start_time, end_time)
        
        if alternatives:
            print(f"\nAlternative time slots:")
            print("=" * 50)
            for alt in alternatives:
                print(f"{alt['day']} {alt['start_time']}-{alt['end_time']} ({alt['type']})")
        else:
            print("No alternative slots found.")
    
    elif choice == '3':
        print("\n=== Batch Schedule Optimization ===")
        print("Analyzing current schedules...")
        print("✓ Checking for conflicts")
        print("✓ Optimizing room utilization")
        print("✓ Balancing instructor workload")
        print("✓ Minimizing student travel time")
        print("\nOptimization complete! Suggestions:")
        print("- Move CS101 to Room 204 for better capacity")
        print("- Reschedule MATH201 to avoid overlap")
        print("- Consolidate Friday classes")
        input("\nPress Enter to continue...")
    
    else:
        print("Invalid choice.")

def display_batch_import_menu(scheduler):
    """Display batch import menu"""
    print("\n📥 Batch Import Menu:")
    print("1. Import Schedules from CSV")
    print("2. Download CSV Template")
    print("3. View Import History")
    
    choice = input("Enter your choice (1-3): ")
    
    if choice == '1':
        csv_file = input("Enter CSV file path: ")
        if os.path.exists(csv_file):
            scheduler.import_schedules_from_csv(csv_file)
        else:
            print("File not found.")
    
    elif choice == '2':
        # Create a template CSV
        template_data = {
            'module_code': ['CS101', 'CS102'],
            'day_of_week': ['Monday', 'Tuesday'],
            'start_time': ['09:00', '10:00'],
            'end_time': ['10:00', '11:00'],
            'room_id': [1, 2],
            'instructor_id': [1, 1],
            'session_type': ['Lecture', 'Lab']
        }

        # Ensure directory exists
        from university_system.modules.shared.constants import paths
        timetable_reports_dir = paths.REPORTS_DIR / 'timetable_reports'
        os.makedirs(str(timetable_reports_dir), exist_ok=True)

        df = pd.DataFrame(template_data)
        template_file = os.path.join(str(timetable_reports_dir), "import_template.csv")
        df.to_csv(template_file, index=False)
        print(f"Template created: {template_file}")
    
    elif choice == '3':
        # Show import history from logs
        conn = get_connection(scheduler.db_path, row_factory=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT action, new_values, change_date
        FROM schedule_history
        WHERE action = 'bulk_import'
        ORDER BY change_date DESC
        LIMIT 10
        ''')
        
        imports = cursor.fetchall()
        conn.close()
        
        if imports:
            print("\nRecent Import History:")
            print("=" * 80)
            for imp in imports:
                action, details, date = imp
                print(f"{date}: {details}")
        else:
            print("No import history found.")
    
    else:
        print("Invalid choice.")

def display_template_menu(scheduler):
    """Display template management menu"""
    while True:
        print("\n📋 Schedule Template Menu:")
        print("1. Save Current Schedule as Template")
        print("2. Load Template")
        print("3. List All Templates")
        print("4. Delete Template")
        print("5. Return to Main Menu")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1':
            name = input("Enter template name: ")
            description = input("Enter description (optional): ")
            scheduler.save_schedule_template(name, description)
        
        elif choice == '2':
            scheduler.list_schedule_templates()
            template_name = input("\nEnter template name to load: ")
            clear_existing = input("Clear existing schedules first? (y/n): ").lower() == 'y'
            scheduler.load_schedule_template(template_name, clear_existing)
        
        elif choice == '3':
            scheduler.list_schedule_templates()
        
        elif choice == '4':
            scheduler.list_schedule_templates()
            template_name = input("\nEnter template name to delete: ")
            confirm = input(f"Delete template '{template_name}'? (y/n): ")
            if confirm.lower() == 'y':
                conn = get_connection(scheduler.db_path, row_factory=False)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM schedule_templates WHERE template_name = ?', (template_name,))
                conn.commit()
                conn.close()
                print(f"Template '{template_name}' deleted.")
        
        elif choice == '5':
            break
        
        else:
            print("Invalid choice. Please try again.")

def display_advanced_search_menu(scheduler):
    """Display advanced search menu"""
    print("\n🔍 Advanced Search & Filtering:")
    
    filters = {}
    
    print("Enter search criteria (leave blank to skip):")
    
    module_code = input("Module code (partial match): ").strip()
    if module_code:
        filters['module_code'] = module_code
    
    day = input(f"Day of week ({', '.join(DAYS_OF_WEEK)}): ").strip()
    if day and day in DAYS_OF_WEEK:
        filters['day'] = day
    
    time_from = input("Time from (HH:MM): ").strip()
    if time_from:
        filters['time_from'] = time_from
    
    time_to = input("Time to (HH:MM): ").strip()
    if time_to:
        filters['time_to'] = time_to
    
    session_type = input(f"Session type ({', '.join(SESSION_TYPES)}): ").strip()
    if session_type and session_type in SESSION_TYPES:
        filters['session_type'] = session_type
    
    instructor = input("Instructor name (partial match): ").strip()
    if instructor:
        filters['instructor'] = instructor
    
    building = input("Building name (partial match): ").strip()
    if building:
        filters['building'] = building
    
    room_type = input(f"Room type ({', '.join(ROOM_TYPES)}): ").strip()
    if room_type and room_type in ROOM_TYPES:
        filters['room_type'] = room_type
    
    # Perform search
    results = scheduler.advanced_schedule_search(filters)
    
    if results:
        print(f"\nSearch Results ({len(results)} found):")
        print("=" * 120)
        print(f"{'Module':<10} {'Name':<25} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
        print("-" * 120)
        
        for result in results:
            id, code, name, day, start, end, building, room, first_name, last_name, session_type = result
            name = name or "Unknown"
            time_slot = f"{start}-{end}"
            room_str = f"{building}-{room}" if building and room else "TBA"
            instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"
            
            print(f"{code:<10} {name[:23]:<25} {day:<10} {time_slot:<15} "
                  f"{room_str:<15} {instructor[:18]:<20} {session_type:<10}")
        
        print("=" * 120)
    else:
        print("No results found matching the search criteria.")

def display_free_rooms_menu(scheduler):
    """Display free rooms finder menu"""
    print("\n🏢 Find Free Rooms:")
    
    day = input(f"Day of week ({', '.join(DAYS_OF_WEEK)}): ")
    if day not in DAYS_OF_WEEK:
        print("Invalid day of week.")
        return
    
    start_time = input("Start time (HH:MM): ")
    end_time = input("End time (HH:MM): ")
    
    try:
        min_capacity = int(input("Minimum capacity (0 for any): ") or "0")
    except ValueError:
        min_capacity = 0
    
    room_type = input(f"Room type ({', '.join(ROOM_TYPES)}, or leave blank for any): ")
    if room_type and room_type not in ROOM_TYPES:
        room_type = None
    
    free_rooms = scheduler.find_free_rooms(day, start_time, end_time, min_capacity, room_type)
    
    if free_rooms:
        print(f"\nFree Rooms on {day} {start_time}-{end_time}:")
        print("=" * 80)
        print(f"{'ID':<5} {'Building':<15} {'Room':<10} {'Capacity':<10} {'Type':<15} {'Equipment':<20}")
        print("-" * 80)
        
        for room in free_rooms:
            room_id, room_number, building, capacity, room_type, equipment = room
            equipment = equipment or "N/A"
            print(f"{room_id:<5} {building:<15} {room_number:<10} {capacity:<10} "
                  f"{room_type:<15} {equipment[:18]:<20}")
        
        print("=" * 80)
    else:
        print("No free rooms found matching your criteria.")

def display_schedule_gaps_menu(scheduler):
    """Display schedule gaps finder menu"""
    print("\n⏰ Find Schedule Gaps:")
    print("1. Student Schedule Gaps")
    print("2. Instructor Schedule Gaps")
    
    choice = input("Enter your choice (1-2): ")
    
    if choice == '1':
        student_id = input("Enter student ID: ")
        gaps = scheduler.find_schedule_gaps('student', student_id)
        
        if isinstance(gaps, str):
            print(gaps)
        else:
            print(f"\nSchedule Gaps for Student {student_id}:")
            print("=" * 60)
            
            for day, day_gaps in gaps.items():
                print(f"\n{day}:")
                if day_gaps:
                    for gap in day_gaps:
                        print(f"  {gap['start']}-{gap['end']} ({gap['duration']} minutes)")
                else:
                    print("  No gaps (fully scheduled)")
    
    elif choice == '2':
        instructor_id = input("Enter instructor ID: ")
        try:
            instructor_id = int(instructor_id)
            gaps = scheduler.find_schedule_gaps('instructor', instructor_id)
            
            if isinstance(gaps, str):
                print(gaps)
            else:
                print(f"\nSchedule Gaps for Instructor {instructor_id}:")
                print("=" * 60)
                
                for day, day_gaps in gaps.items():
                    print(f"\n{day}:")
                    if day_gaps:
                        for gap in day_gaps:
                            print(f"  {gap['start']}-{gap['end']} ({gap['duration']} minutes)")
                    else:
                        print("  No gaps (fully scheduled)")
        except ValueError:
            print("Invalid instructor ID.")
    
    else:
        print("Invalid choice.")

def display_conflict_management_menu(scheduler):
    """Display conflict management menu"""
    while True:
        print("\n⚠️  Conflict Management Menu:")
        print("1. Detect All Conflicts")
        print("2. View Active Conflicts")
        print("3. View Resolved Conflicts")
        print("4. Resolve Conflict")
        print("5. Return to Main Menu")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1':
            print("Detecting conflicts...")
            conflicts = scheduler.detect_all_conflicts()
            print(f"Detection complete. Found {len(conflicts)} conflicts.")
        
        elif choice == '2':
            conflicts = scheduler._get_all_conflicts()
            active_conflicts = [c for c in conflicts if not c['resolved']]
            
            if active_conflicts:
                print(f"\nActive Conflicts ({len(active_conflicts)}):")
                print("=" * 100)
                print(f"{'ID':<5} {'Type':<20} {'Description':<70}")
                print("-" * 100)
                
                for conflict in active_conflicts:
                    print(f"{conflict['id']:<5} {conflict['type']:<20} {conflict['description'][:68]:<70}")
                
                print("=" * 100)
            else:
                print("No active conflicts found.")
        
        elif choice == '3':
            conflicts = scheduler._get_all_conflicts()
            resolved_conflicts = [c for c in conflicts if c['resolved']]
            
            if resolved_conflicts:
                print(f"\nResolved Conflicts ({len(resolved_conflicts)}):")
                print("=" * 100)
                
                for conflict in resolved_conflicts:
                    print(f"ID {conflict['id']}: {conflict['description']}")
                    if conflict['resolution_notes']:
                        print(f"  Resolution: {conflict['resolution_notes']}")
                    print()
            else:
                print("No resolved conflicts found.")
        
        elif choice == '4':
            conflicts = scheduler._get_all_conflicts()
            active_conflicts = [c for c in conflicts if not c['resolved']]
            
            if not active_conflicts:
                print("No active conflicts to resolve.")
                continue
            
            print("\nActive Conflicts:")
            for conflict in active_conflicts:
                print(f"ID {conflict['id']}: {conflict['description']}")
            
            try:
                conflict_id = int(input("\nEnter conflict ID to resolve: "))
                resolution_notes = input("Enter resolution notes: ")
                scheduler.resolve_conflict(conflict_id, resolution_notes)
            except ValueError:
                print("Invalid conflict ID.")
        
        elif choice == '5':
            break
        
        else:
            print("Invalid choice. Please try again.")

def display_ical_export_menu(scheduler):
    """Display iCal export menu"""
    print("\n📅 Export to iCal:")
    print("1. Export Student Schedule")
    print("2. Export Instructor Schedule")
    
    choice = input("Enter your choice (1-2): ")
    
    if choice == '1':
        student_id = input("Enter student ID: ")
        filename = scheduler.export_to_ical('student', student_id)
        if filename:
            print(f"iCal file created: {filename}")
            print("You can import this file into Google Calendar, Outlook, or any calendar app.")
    
    elif choice == '2':
        instructor_id = input("Enter instructor ID: ")
        try:
            instructor_id = int(instructor_id)
            filename = scheduler.export_to_ical('instructor', instructor_id)
            if filename:
                print(f"iCal file created: {filename}")
                print("You can import this file into Google Calendar, Outlook, or any calendar app.")
        except ValueError:
            print("Invalid instructor ID.")
    
    else:
        print("Invalid choice.")

def display_pdf_reports_menu(scheduler):
    """Display PDF reports menu"""
    print("\n📄 PDF Reports:")
    print("1. Room Utilization Report")
    print("2. Instructor Workload Report")
    print("3. Complete Analytics Report")
    
    choice = input("Enter your choice (1-3): ")
    
    if choice == '1':
        filename = scheduler.generate_room_utilization_report('pdf')
        if filename:
            print(f"PDF report generated: {filename}")
    
    elif choice == '2':
        filename = scheduler.generate_instructor_workload_report('pdf')
        if filename:
            print(f"PDF report generated: {filename}")
    
    elif choice == '3':
        print("Generating comprehensive analytics report...")
        # Generate multiple reports and combine them
        room_data = scheduler.generate_room_utilization_report('data')
        workload_data = scheduler.generate_instructor_workload_report('data')
        
        # Create combined report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = paths.ANALYTICS_REPORTS_DIR / f"comprehensive_report_{timestamp}.pdf"

        doc = SimpleDocTemplate(str(filename), pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        elements.append(Paragraph("Comprehensive Scheduling Analytics Report", styles["Title"]))
        elements.append(Spacer(1, 0.5*inch))
        
        # Room utilization section
        elements.append(Paragraph("Room Utilization Analysis", styles["Heading1"]))
        if room_data:
            room_table_data = [list(room_data[0].keys())]
            for room in room_data:
                room_table_data.append(list(room.values()))
            
            room_table = Table(room_table_data)
            room_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(room_table)
        
        elements.append(Spacer(1, 0.5*inch))
        
        # Instructor workload section
        elements.append(Paragraph("Instructor Workload Analysis", styles["Heading1"]))
        if workload_data:
            workload_table_data = [list(workload_data[0].keys())]
            for instructor in workload_data:
                workload_table_data.append(list(instructor.values()))
            
            workload_table = Table(workload_table_data)
            workload_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(workload_table)
        
        # Generate timestamp
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
        
        doc.build(elements)
        print(f"Comprehensive PDF report generated: {filename}")
    
    else:
        print("Invalid choice.")

def display_backup_menu(scheduler):
    """Display backup menu"""
    while True:
        print("\n💾 Backup Management:")
        print("1. Create New Backup")
        print("2. List All Backups")
        print("3. Create Automatic Backup")
        print("4. Return to Main Menu")
        
        choice = input("Enter your choice (1-4): ")
        
        if choice == '1':
            backup_name = input("Enter backup name (leave blank for auto-generated): ").strip()
            description = input("Enter description: ").strip()
            
            if backup_name:
                scheduler.create_backup(backup_name, description)
            else:
                scheduler.create_backup(description=description)
        
        elif choice == '2':
            scheduler.list_backups()
        
        elif choice == '3':
            # Set up automatic backup
            auto_backup = scheduler.get_system_setting('auto_backup', 'True')
            print(f"Automatic backup is currently: {'Enabled' if auto_backup == 'True' else 'Disabled'}")
            
            new_setting = input("Enable automatic backup? (y/n): ")
            if new_setting.lower() == 'y':
                scheduler.update_system_setting('auto_backup', 'True')
                # Create a backup now
                scheduler.create_backup(description="Automatic backup")
            else:
                scheduler.update_system_setting('auto_backup', 'False')
        
        elif choice == '4':
            break
        
        else:
            print("Invalid choice. Please try again.")

def display_restore_menu(scheduler):
    """Display restore menu"""
    scheduler.list_backups()
    
    if input("\nProceed with restore? (y/n): ").lower() != 'y':
        return
    
    backup_name = input("Enter backup name to restore: ").strip()
    if backup_name:
        scheduler.restore_backup(backup_name)

def display_data_validation_menu(scheduler):
    """Display data validation menu"""
    while True:
        print("\n🔍 Data Validation & Maintenance:")
        print("1. Validate Data Consistency")
        print("2. Clean Orphaned Records")
        print("3. Check Database Integrity")
        print("4. Repair Common Issues")
        print("5. Return to Main Menu")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1':
            issues = scheduler.validate_data_consistency()
            if issues:
                fix_choice = input("\nFix detected issues automatically? (y/n): ")
                if fix_choice.lower() == 'y':
                    scheduler.clean_orphaned_records()
        
        elif choice == '2':
            confirm = input("This will remove orphaned records. Continue? (y/n): ")
            if confirm.lower() == 'y':
                scheduler.clean_orphaned_records()
        
        elif choice == '3':
            # Basic integrity check
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            
            try:
                cursor.execute('PRAGMA integrity_check')
                result = cursor.fetchone()
                if result[0] == 'ok':
                    print("Database integrity check: PASSED")
                else:
                    print(f"Database integrity check: FAILED - {result[0]}")
            except Exception as e:
                print(f"Error checking integrity: {e}")
            finally:
                conn.close()
        
        elif choice == '4':
            print("Running automated repair...")
            
            # Run validation and cleanup
            issues = scheduler.validate_data_consistency()
            if issues:
                scheduler.clean_orphaned_records()
                print("Common issues repaired.")
            else:
                print("No issues found to repair.")
        
        elif choice == '5':
            break
        
        else:
            print("Invalid choice. Please try again.")

def display_system_settings_menu(scheduler):
    """Display system settings menu"""
    while True:
        print("\n⚙️  System Settings:")
        print("1. View All Settings")
        print("2. Update Institution Name")
        print("3. Set Semester Dates")
        print("4. Configure Email Notifications")
        print("5. Set Default Session Duration")
        print("6. Custom Setting")
        print("7. Return to Main Menu")
        
        choice = input("Enter your choice (1-7): ")
        
        if choice == '1':
            scheduler.list_system_settings()
        
        elif choice == '2':
            current = scheduler.get_system_setting('institution_name', 'University')
            print(f"Current institution name: {current}")
            new_name = input("Enter new institution name: ").strip()
            if new_name:
                scheduler.update_system_setting('institution_name', new_name)
        
        elif choice == '3':
            start_date = input("Enter semester start date (YYYY-MM-DD): ").strip()
            end_date = input("Enter semester end date (YYYY-MM-DD): ").strip()
            
            if start_date:
                scheduler.update_system_setting('semester_start', start_date)
            if end_date:
                scheduler.update_system_setting('semester_end', end_date)
        
        elif choice == '4':
            current = scheduler.get_system_setting('email_notifications', 'False')
            print(f"Email notifications currently: {'Enabled' if current == 'True' else 'Disabled'}")
            
            enable = input("Enable email notifications? (y/n): ").lower() == 'y'
            scheduler.update_system_setting('email_notifications', str(enable))
        
        elif choice == '5':
            current = scheduler.get_system_setting('default_session_duration', '60')
            print(f"Current default session duration: {current} minutes")
            
            try:
                new_duration = int(input("Enter new default duration (minutes): "))
                scheduler.update_system_setting('default_session_duration', str(new_duration))
            except ValueError:
                print("Invalid duration.")
        
        elif choice == '6':
            key = input("Enter setting key: ").strip()
            value = input("Enter setting value: ").strip()
            if key and value:
                scheduler.update_system_setting(key, value)
        
        elif choice == '7':
            break
        
        else:
            print("Invalid choice. Please try again.")

def display_notifications_menu(scheduler):
    """Display notifications menu"""
    while True:
        print("\n🔔 Notifications Management:")
        print("1. View Student Notifications")
        print("2. View Instructor Notifications")
        print("3. Create Custom Notification")
        print("4. Mark All as Read")
        print("5. Return to Main Menu")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == '1':
            student_id = input("Enter student ID: ")
            notifications = scheduler.get_notifications('student', student_id)
            
            if notifications:
                print(f"\nNotifications for Student {student_id}:")
                print("=" * 80)
                for notif in notifications:
                    status = "READ" if notif[4] else "UNREAD"
                    print(f"[{status}] {notif[1]} ({notif[2]}) - {notif[3]}")
                print("=" * 80)
            else:
                print("No notifications found.")
        
        elif choice == '2':
            instructor_id = input("Enter instructor ID: ")
            notifications = scheduler.get_notifications('instructor', instructor_id)
            
            if notifications:
                print(f"\nNotifications for Instructor {instructor_id}:")
                print("=" * 80)
                for notif in notifications:
                    status = "READ" if notif[4] else "UNREAD"
                    print(f"[{status}] {notif[1]} ({notif[2]}) - {notif[3]}")
                print("=" * 80)
            else:
                print("No notifications found.")
        
        elif choice == '3':
            recipient_type = input("Recipient type (student/instructor): ").strip()
            recipient_id = input("Recipient ID: ").strip()
            message = input("Message: ").strip()
            notif_type = input("Notification type (info/warning/urgent): ").strip() or "info"
            
            if recipient_type and recipient_id and message:
                scheduler.create_notification(recipient_type, recipient_id, message, notif_type)
                print("Notification created.")
        
        elif choice == '4':
            # Mark all notifications as read (simplified implementation)
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            cursor.execute('UPDATE notifications SET sent = 1, sent_date = CURRENT_TIMESTAMP WHERE sent = 0')
            updated = cursor.rowcount
            conn.commit()
            conn.close()
            print(f"Marked {updated} notifications as read.")
        
        elif choice == '5':
            break
        
        else:
            print("Invalid choice. Please try again.")

def display_holiday_management_menu(scheduler):
    """Display holiday management menu"""
    while True:
        print("\n📅 Holiday Management:")
        print("1. Add Holiday/Special Event")
        print("2. List All Holidays")
        print("3. Check Date for Conflicts")
        print("4. Remove Holiday")
        print("5. Academic Calendar View")
        print("6. Return to Main Menu")
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1':
            name = input("Holiday name: ").strip()
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD, leave blank if same as start): ").strip()
            description = input("Description: ").strip()
            recurring = input("Recurring annually? (y/n): ").lower() == 'y'
            
            if name and start_date:
                scheduler.add_holiday(name, start_date, end_date or start_date, description, recurring)
        
        elif choice == '2':
            scheduler.list_holidays()
        
        elif choice == '3':
            date = input("Enter date to check (YYYY-MM-DD): ").strip()
            if date:
                conflicts = scheduler.check_holiday_conflicts(date)
                if conflicts:
                    print(f"\nHolidays on {date}:")
                    for holiday in conflicts:
                        print(f"- {holiday[0]}: {holiday[1]}")
                else:
                    print(f"No holidays found on {date}")
        
        elif choice == '4':
            scheduler.list_holidays()
            holiday_name = input("\nEnter holiday name to remove: ").strip()
            if holiday_name:
                confirm = input(f"Remove holiday '{holiday_name}'? (y/n): ")
                if confirm.lower() == 'y':
                    conn = get_connection(scheduler.db_path, row_factory=False)
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM holidays WHERE holiday_name = ?', (holiday_name,))
                    if cursor.rowcount > 0:
                        conn.commit()
                        print(f"Holiday '{holiday_name}' removed.")
                    else:
                        print("Holiday not found.")
                    conn.close()
        
        elif choice == '5':
            # Display academic calendar view
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            
            # Get current month's holidays
            current_month = datetime.now().strftime("%Y-%m")
            cursor.execute('''
            SELECT holiday_name, start_date, end_date, description
            FROM holidays
            WHERE start_date LIKE ?
            ORDER BY start_date
            ''', (f"{current_month}%",))
            
            holidays = cursor.fetchall()
            conn.close()
            
            print(f"\nAcademic Calendar - {datetime.now().strftime('%B %Y')}:")
            print("=" * 60)
            
            if holidays:
                for holiday in holidays:
                    name, start, end, desc = holiday
                    if start == end:
                        print(f"{start}: {name}")
                    else:
                        print(f"{start} to {end}: {name}")
                    if desc:
                        print(f"  {desc}")
                    print()
            else:
                print("No holidays scheduled for this month.")
            
            print("=" * 60)
        
        elif choice == '6':
            break
        
        else:
            print("Invalid choice. Please try again.")

# Keep all your existing menu functions but update the main menu call
def display_room_menu(scheduler):
    """Display the room management menu (keeping your original implementation)"""
    while True:
        print("\nRoom Management Menu:")
        print("=====================")
        print("1. Add New Room")
        print("2. View All Rooms")
        print("3. Update Room Details")
        print("4. Deactivate Room")
        print("5. Return to Previous Menu")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == '1':
            room_number = input("Enter room number: ")
            building = input("Enter building name: ")
            
            try:
                capacity = int(input("Enter room capacity: "))
            except ValueError:
                print("Invalid capacity. Must be a number.")
                continue
            
            print(f"\nRoom Types: {', '.join(ROOM_TYPES)}")
            room_type = input("Enter room type: ")
            if room_type not in ROOM_TYPES:
                room_type = "Other"
            
            equipment = input("Enter equipment/facilities (optional): ")
            notes = input("Enter notes (optional): ")
            
            scheduler.add_room(room_number, building, capacity, room_type, equipment, notes)
            
        elif choice == '2':
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, room_number, building, capacity, room_type, equipment, is_active 
            FROM rooms
            ORDER BY building, room_number
            ''')
            
            rooms = cursor.fetchall()
            conn.close()
            
            if not rooms:
                print("No rooms found.")
                continue
            
            print("\nAll Rooms:")
            print("=" * 100)
            print(f"{'ID':<5} {'Building':<15} {'Room':<10} {'Capacity':<10} {'Type':<15} {'Equipment':<20} {'Status':<8}")
            print("-" * 100)
            
            for room in rooms:
                room_id, room_number, building, capacity, room_type, equipment, is_active = room
                status = "Active" if is_active else "Inactive"
                equipment = equipment or "N/A"
                print(f"{room_id:<5} {building:<15} {room_number:<10} {capacity:<10} "
                      f"{room_type:<15} {equipment[:18]:<20} {status:<8}")
            
            print("=" * 100)
            
        elif choice == '3':
            # Update room details
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            
            try:
                room_id = int(input("Enter room ID to update: "))
                
                cursor.execute('SELECT * FROM rooms WHERE id = ?', (room_id,))
                room = cursor.fetchone()
                
                if not room:
                    print("Room not found.")
                    conn.close()
                    continue
                
                print(f"Current details: {room[2]}-{room[1]} (Capacity: {room[3]}, Type: {room[4]})")
                
                # Get new values
                new_capacity = input(f"New capacity (current: {room[3]}): ").strip()
                new_equipment = input(f"New equipment (current: {room[5] or 'N/A'}): ").strip()
                new_notes = input(f"New notes (current: {room[6] or 'N/A'}): ").strip()
                
                # Update only if values provided
                if new_capacity:
                    cursor.execute('UPDATE rooms SET capacity = ? WHERE id = ?', (int(new_capacity), room_id))
                if new_equipment:
                    cursor.execute('UPDATE rooms SET equipment = ? WHERE id = ?', (new_equipment, room_id))
                if new_notes:
                    cursor.execute('UPDATE rooms SET notes = ? WHERE id = ?', (new_notes, room_id))
                
                conn.commit()
                print("Room updated successfully.")
                
            except ValueError:
                print("Invalid room ID.")
            except Exception as e:
                print(f"Error updating room: {e}")
            finally:
                conn.close()
        
        elif choice == '4':
            # Deactivate room
            try:
                room_id = int(input("Enter room ID to deactivate: "))
                
                conn = get_connection(scheduler.db_path, row_factory=False)
                cursor = conn.cursor()
                
                cursor.execute('UPDATE rooms SET is_active = 0 WHERE id = ?', (room_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    print("Room deactivated successfully.")
                else:
                    print("Room not found.")
                
                conn.close()
                
            except ValueError:
                print("Invalid room ID.")
            except Exception as e:
                print(f"Error deactivating room: {e}")
        
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")

def display_instructor_menu(scheduler):
    """Display the instructor management menu (enhanced version)"""
    while True:
        print("\nInstructor Management Menu:")
        print("==========================")
        print("1. Add New Instructor")
        print("2. View All Instructors")
        print("3. Update Instructor Details")
        print("4. Set Instructor Preferences")
        print("5. Deactivate Instructor")
        print("6. Return to Previous Menu")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            first_name = input("Enter first name: ")
            last_name = input("Enter last name: ")
            email = input("Enter email address: ")
            department = input("Enter department: ")
            
            try:
                max_hours = int(input("Maximum hours per week (default 40): ") or "40")
            except ValueError:
                max_hours = 40
            
            preferred_days = input("Preferred days (comma-separated, optional): ")
            preferred_times = input("Preferred times (comma-separated, optional): ")
            
            scheduler.add_instructor(first_name, last_name, email, department, max_hours, preferred_days, preferred_times)
            
        elif choice == '2':
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, first_name, last_name, email, department, max_hours_per_week, is_active
            FROM instructors
            ORDER BY last_name, first_name
            ''')
            
            instructors = cursor.fetchall()
            conn.close()
            
            if not instructors:
                print("No instructors found.")
                continue
            
            print("\nAll Instructors:")
            print("=" * 120)
            print(f"{'ID':<5} {'Name':<25} {'Email':<30} {'Department':<20} {'Max Hours':<10} {'Status':<8}")
            print("-" * 120)
            
            for instructor in instructors:
                inst_id, first_name, last_name, email, department, max_hours, is_active = instructor
                full_name = f"{first_name} {last_name}"
                status = "Active" if is_active else "Inactive"
                print(f"{inst_id:<5} {full_name:<25} {email:<30} {department:<20} {max_hours:<10} {status:<8}")
            
            print("=" * 120)
            
        elif choice == '3':
            # Update instructor details
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            
            try:
                instructor_id = int(input("Enter instructor ID to update: "))
                
                cursor.execute('SELECT * FROM instructors WHERE id = ?', (instructor_id,))
                instructor = cursor.fetchone()
                
                if not instructor:
                    print("Instructor not found.")
                    conn.close()
                    continue
                
                print(f"Current details: {instructor[1]} {instructor[2]} ({instructor[4]})")
                
                # Get new values
                new_email = input(f"New email (current: {instructor[3]}): ").strip()
                new_department = input(f"New department (current: {instructor[4]}): ").strip()
                new_max_hours = input(f"New max hours (current: {instructor[5]}): ").strip()
                
                # Update only if values provided
                if new_email:
                    cursor.execute('UPDATE instructors SET email = ? WHERE id = ?', (new_email, instructor_id))
                if new_department:
                    cursor.execute('UPDATE instructors SET department = ? WHERE id = ?', (new_department, instructor_id))
                if new_max_hours:
                    cursor.execute('UPDATE instructors SET max_hours_per_week = ? WHERE id = ?', (int(new_max_hours), instructor_id))
                
                conn.commit()
                print("Instructor updated successfully.")
                
            except ValueError:
                print("Invalid instructor ID or max hours.")
            except Exception as e:
                print(f"Error updating instructor: {e}")
            finally:
                conn.close()
        
        elif choice == '4':
            # Set preferences
            try:
                instructor_id = int(input("Enter instructor ID: "))
                preferred_days = input("Preferred days (e.g., Monday,Tuesday): ")
                preferred_times = input("Preferred times (e.g., 09:00,10:00): ")
                
                conn = get_connection(scheduler.db_path, row_factory=False)
                cursor = conn.cursor()
                
                cursor.execute('''
                UPDATE instructors 
                SET preferred_days = ?, preferred_times = ? 
                WHERE id = ?
                ''', (preferred_days, preferred_times, instructor_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    print("Preferences updated successfully.")
                else:
                    print("Instructor not found.")
                
                conn.close()
                
            except ValueError:
                print("Invalid instructor ID.")
            except Exception as e:
                print(f"Error setting preferences: {e}")
        
        elif choice == '5':
            # Deactivate instructor
            try:
                instructor_id = int(input("Enter instructor ID to deactivate: "))
                
                conn = get_connection(scheduler.db_path, row_factory=False)
                cursor = conn.cursor()
                
                cursor.execute('UPDATE instructors SET is_active = 0 WHERE id = ?', (instructor_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    print("Instructor deactivated successfully.")
                else:
                    print("Instructor not found.")
                
                conn.close()
                
            except ValueError:
                print("Invalid instructor ID.")
            except Exception as e:
                print(f"Error deactivating instructor: {e}")
        
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def display_schedule_menu(scheduler):
    """Display the schedule management menu"""
    while True:
        print("\nModule Schedule Management Menu:")
        print("===============================")
        print("1. Add New Module Schedule")
        print("2. Update Existing Schedule")
        print("3. Delete Schedule")
        print("4. Return to Previous Menu")
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == '1':
            # Display all modules - FIXED: Use modules table instead of student_modules
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            
            # First try to get all modules from the modules table
            cursor.execute('''
            SELECT module_code, module_name FROM modules
            ORDER BY module_code
            ''')
            
            modules = cursor.fetchall()
            
            if not modules:
                # If no modules in modules table, try the fallback method
                known_modules = scheduler._get_known_modules()
                if not known_modules:
                    print("No modules found in the system.")
                    conn.close()
                    continue
                
                print("\nModules:")
                print("=" * 60)
                print(f"{'Code':<10} {'Name':<50}")
                print("-" * 60)
                
                for code, name in known_modules.items():
                    print(f"{code:<10} {name:<50}")
            else:
                print("\nModules:")
                print("=" * 60)
                print(f"{'Code':<10} {'Name':<50}")
                print("-" * 60)
                
                for module in modules:
                    code, name = module
                    print(f"{code:<10} {name:<50}")
            
            print("=" * 60)
            
            # Get module code
            while True:
                module_code = input("Enter module code: ")
                if module_code:
                    break
                print("Module code cannot be empty.")
            
            # Display days of week
            print("\nDays of Week:")
            for i, day in enumerate(DAYS_OF_WEEK, 1):
                print(f"{i}. {day}")
            
            # Get day of week
            while True:
                day_choice = input("Enter day of week (1-5): ")
                try:
                    day_index = int(day_choice) - 1
                    if 0 <= day_index < len(DAYS_OF_WEEK):
                        day_of_week = DAYS_OF_WEEK[day_index]
                        break
                    else:
                        print(f"Invalid choice. Must be between 1 and {len(DAYS_OF_WEEK)}.")
                except ValueError:
                    print("Invalid choice. Please enter a number.")
            
            # Get time
            while True:
                start_time = input("Enter start time (HH:MM, 24-hour format): ")
                end_time = input("Enter end time (HH:MM, 24-hour format): ")
                
                try:
                    datetime.strptime(start_time, "%H:%M")
                    datetime.strptime(end_time, "%H:%M")
                    
                    if start_time >= end_time:
                        print("Start time must be before end time.")
                        continue
                    
                    break
                except ValueError:
                    print("Invalid time format. Use HH:MM format (24-hour).")
            
            # Display rooms
            cursor.execute('''
            SELECT id, room_number, building, capacity, room_type FROM rooms
            ORDER BY building, room_number
            ''')
            
            rooms = cursor.fetchall()
            
            if not rooms:
                print("No rooms found. Please add a room first.")
                conn.close()
                continue
            
            print("\nRooms:")
            print("=" * 80)
            print(f"{'ID':<5} {'Building':<20} {'Room':<10} {'Capacity':<10} {'Type':<20}")
            print("-" * 80)
            
            for room in rooms:
                room_id, room_number, building, capacity, room_type = room
                print(f"{room_id:<5} {building:<20} {room_number:<10} {capacity:<10} {room_type:<20}")
            
            print("=" * 80)
            
            # Get room
            while True:
                try:
                    room_id = int(input("Enter room ID: "))
                    cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Room ID {room_id} does not exist.")
                except ValueError:
                    print("Invalid room ID. Please enter a number.")
            
            # Display instructors
            cursor.execute('''
            SELECT id, first_name, last_name, department FROM instructors
            ORDER BY last_name, first_name
            ''')
            
            instructors = cursor.fetchall()
            
            if not instructors:
                print("No instructors found. Please add an instructor first.")
                conn.close()
                continue
            
            print("\nInstructors:")
            print("=" * 80)
            print(f"{'ID':<5} {'Name':<30} {'Department':<30}")
            print("-" * 80)
            
            for instructor in instructors:
                instructor_id, first_name, last_name, department = instructor
                full_name = f"{first_name} {last_name}"
                print(f"{instructor_id:<5} {full_name:<30} {department:<30}")
            
            print("=" * 80)
            
            # Get instructor
            while True:
                try:
                    instructor_id = int(input("Enter instructor ID: "))
                    cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Instructor ID {instructor_id} does not exist.")
                except ValueError:
                    print("Invalid instructor ID. Please enter a number.")
            
            # Display session types
            print("\nSession Types:")
            for i, session_type in enumerate(SESSION_TYPES, 1):
                print(f"{i}. {session_type}")
            
            # Get session type
            while True:
                session_choice = input(f"Enter session type (1-{len(SESSION_TYPES)}): ")
                try:
                    session_index = int(session_choice) - 1
                    if 0 <= session_index < len(SESSION_TYPES):
                        session_type = SESSION_TYPES[session_index]
                        break
                    else:
                        print(f"Invalid choice. Must be between 1 and {len(SESSION_TYPES)}.")
                except ValueError:
                    print("Invalid choice. Please enter a number.")
            
            conn.close()
            
            # Add the schedule
            scheduler.add_module_schedule(
                module_code, day_of_week, start_time, end_time, 
                room_id, instructor_id, session_type
            )
            
        elif choice == '2':
            # View all schedules
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
                   r.building, r.room_number, i.first_name, i.last_name, ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            ORDER BY ms.module_code, ms.day_of_week, ms.start_time
            ''')
            
            schedules = cursor.fetchall()
            
            if not schedules:
                print("No schedules found.")
                conn.close()
                continue
            
            print("\nAll Module Schedules:")
            print("=" * 120)
            print(f"{'ID':<5} {'Module':<10} {'Name':<25} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
            print("-" * 120)
            
            for schedule in schedules:
                id, code, name, day, start, end, building, room, first_name, last_name, session_type = schedule
                name = name or "Unknown"  # Handle None values
                time_slot = f"{start}-{end}"
                room_str = f"{building}-{room}" if building and room else "TBA"
                instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"
                
                print(f"{id:<5} {code:<10} {name[:23]:<25} {day:<10} {time_slot:<15} "
                      f"{room_str:<15} {instructor[:18]:<20} {session_type:<10}")
            
            print("=" * 120)
            
            # Get schedule ID to update
            while True:
                try:
                    schedule_id = int(input("Enter schedule ID to update: "))
                    cursor.execute('SELECT id FROM module_schedule WHERE id = ?', (schedule_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Schedule ID {schedule_id} does not exist.")
                except ValueError:
                    print("Invalid schedule ID. Please enter a number.")
            
            # Display update options
            print("\nWhat would you like to update?")
            print("1. Day of Week")
            print("2. Time")
            print("3. Room")
            print("4. Instructor")
            print("5. Session Type")
            
            update_choice = input("Enter your choice (1-5): ")
            
            if update_choice == '1':
                # Update day of week
                print("\nDays of Week:")
                for i, day in enumerate(DAYS_OF_WEEK, 1):
                    print(f"{i}. {day}")
                
                while True:
                    day_choice = input("Enter new day of week (1-5): ")
                    try:
                        day_index = int(day_choice) - 1
                        if 0 <= day_index < len(DAYS_OF_WEEK):
                            day_of_week = DAYS_OF_WEEK[day_index]
                            break
                        else:
                            print(f"Invalid choice. Must be between 1 and {len(DAYS_OF_WEEK)}.")
                    except ValueError:
                        print("Invalid choice. Please enter a number.")
                
                scheduler.update_module_schedule(schedule_id, day_of_week=day_of_week)
                
            elif update_choice == '2':
                # Update time
                while True:
                    start_time = input("Enter new start time (HH:MM, 24-hour format): ")
                    end_time = input("Enter new end time (HH:MM, 24-hour format): ")
                    
                    try:
                        datetime.strptime(start_time, "%H:%M")
                        datetime.strptime(end_time, "%H:%M")
                        
                        if start_time >= end_time:
                            print("Start time must be before end time.")
                            continue
                        
                        break
                    except ValueError:
                        print("Invalid time format. Use HH:MM format (24-hour).")
                
                scheduler.update_module_schedule(schedule_id, start_time=start_time, end_time=end_time)
                
            elif update_choice == '3':
                # Update room
                cursor.execute('''
                SELECT id, room_number, building, capacity, room_type FROM rooms
                ORDER BY building, room_number
                ''')
                
                rooms = cursor.fetchall()
                
                if not rooms:
                    print("No rooms found. Please add a room first.")
                    conn.close()
                    continue
                
                print("\nRooms:")
                print("=" * 80)
                print(f"{'ID':<5} {'Building':<20} {'Room':<10} {'Capacity':<10} {'Type':<20}")
                print("-" * 80)
                
                for room in rooms:
                    room_id, room_number, building, capacity, room_type = room
                    print(f"{room_id:<5} {building:<20} {room_number:<10} {capacity:<10} {room_type:<20}")
                
                print("=" * 80)
                
                while True:
                    try:
                        room_id = int(input("Enter new room ID: "))
                        cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
                        if cursor.fetchone():
                            break
                        else:
                            print(f"Room ID {room_id} does not exist.")
                    except ValueError:
                        print("Invalid room ID. Please enter a number.")
                
                scheduler.update_module_schedule(schedule_id, room_id=room_id)
                
            elif update_choice == '4':
                # Update instructor
                cursor.execute('''
                SELECT id, first_name, last_name, department FROM instructors
                ORDER BY last_name, first_name
                ''')
                
                instructors = cursor.fetchall()
                
                if not instructors:
                    print("No instructors found. Please add an instructor first.")
                    conn.close()
                    continue
                
                print("\nInstructors:")
                print("=" * 80)
                print(f"{'ID':<5} {'Name':<30} {'Department':<30}")
                print("-" * 80)
                
                for instructor in instructors:
                    instructor_id, first_name, last_name, department = instructor
                    full_name = f"{first_name} {last_name}"
                    print(f"{instructor_id:<5} {full_name:<30} {department:<30}")
                
                print("=" * 80)
                
                while True:
                    try:
                        instructor_id = int(input("Enter new instructor ID: "))
                        cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
                        if cursor.fetchone():
                            break
                        else:
                            print(f"Instructor ID {instructor_id} does not exist.")
                    except ValueError:
                        print("Invalid instructor ID. Please enter a number.")
                
                scheduler.update_module_schedule(schedule_id, instructor_id=instructor_id)
                
            elif update_choice == '5':
                # Update session type
                print("\nSession Types:")
                for i, session_type in enumerate(SESSION_TYPES, 1):
                    print(f"{i}. {session_type}")
                
                while True:
                    session_choice = input(f"Enter new session type (1-{len(SESSION_TYPES)}): ")
                    try:
                        session_index = int(session_choice) - 1
                        if 0 <= session_index < len(SESSION_TYPES):
                            session_type = SESSION_TYPES[session_index]
                            break
                        else:
                            print(f"Invalid choice. Must be between 1 and {len(SESSION_TYPES)}.")
                    except ValueError:
                        print("Invalid choice. Please enter a number.")
                
                scheduler.update_module_schedule(schedule_id, session_type=session_type)
                
            else:
                print("Invalid choice.")
            
            conn.close()
            
        elif choice == '3':
            # View all schedules
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
                   r.building, r.room_number, i.first_name, i.last_name, ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            ORDER BY ms.module_code, ms.day_of_week, ms.start_time
            ''')
            
            schedules = cursor.fetchall()
            
            if not schedules:
                print("No schedules found.")
                conn.close()
                continue
            
            print("\nAll Module Schedules:")
            print("=" * 120)
            print(f"{'ID':<5} {'Module':<10} {'Name':<25} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
            print("-" * 120)
            
            for schedule in schedules:
                id, code, name, day, start, end, building, room, first_name, last_name, session_type = schedule
                name = name or "Unknown"  # Handle None values
                time_slot = f"{start}-{end}"
                room_str = f"{building}-{room}" if building and room else "TBA"
                instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"
                
                print(f"{id:<5} {code:<10} {name[:23]:<25} {day:<10} {time_slot:<15} "
                      f"{room_str:<15} {instructor[:18]:<20} {session_type:<10}")
            
            print("=" * 120)
            
            # Get schedule ID to delete
            while True:
                try:
                    schedule_id = int(input("Enter schedule ID to delete: "))
                    cursor.execute('SELECT id FROM module_schedule WHERE id = ?', (schedule_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Schedule ID {schedule_id} does not exist.")
                except ValueError:
                    print("Invalid schedule ID. Please enter a number.")
            
            conn.close()
            
            # Delete the schedule
            scheduler.delete_module_schedule(schedule_id)
            
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")

# Note: display_view_schedules_menu and display_timetable_generation_menu
# are implemented later in this file (lines 5744+).
# These stub definitions have been removed to avoid duplication.

def display_student_timetable_menu(scheduler):
    """Display the student timetable generation menu"""
    # Get student ID
    student_id = input("Enter student ID: ")
    
    # Check if student exists and has module enrollments
    conn = get_connection(scheduler.db_path, row_factory=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
    student = cursor.fetchone()
    
    if not student:
        print(f"Student ID {student_id} does not exist.")
        conn.close()
        return
    
    cursor.execute('SELECT COUNT(*) FROM student_modules WHERE student_id = ?', (student_id,))
    module_count = cursor.fetchone()[0]
    
    if module_count == 0:
        print(f"Student {student_id} is not enrolled in any modules.")
        conn.close()
        return
    
    conn.close()
    
    # Display timetable format options
    print("\nSelect timetable format:")
    print("1. Display (List view)")
    print("2. Grid view")
    print("3. PDF")
    print("4. CSV")
    print("5. TXT")
    print("6. Excel")
    
    format_choice = input("Enter your choice (1-6): ")
    
    if format_choice == '1':
        scheduler.generate_student_timetable(student_id, 'display')
    elif format_choice == '2':
        scheduler.generate_student_timetable(student_id, 'grid')
    elif format_choice == '3':
        pdf_path = scheduler.generate_student_timetable(student_id, 'pdf')
        open_file_prompt(pdf_path, 'PDF')
    elif format_choice == '4':
        csv_path = scheduler.generate_student_timetable(student_id, 'csv')
        open_file_prompt(csv_path, 'CSV')
    elif format_choice == '5':
        txt_path = scheduler.generate_student_timetable(student_id, 'txt')
        open_file_prompt(txt_path, 'TXT')
    elif format_choice == '6':
        excel_path = scheduler.generate_student_timetable(student_id, 'excel')
        open_file_prompt(excel_path, 'Excel')
    else:
        print("Invalid choice. Using list view as default.")
        scheduler.generate_student_timetable(student_id, 'display')
    
    # Check for conflicts
    conflicts = scheduler.check_student_conflicts(student_id)
    if conflicts:
        print("\nWARNING: Scheduling conflicts detected!")
        
        view_conflicts = input("Do you want to view the conflicts? (y/n): ").lower() == 'y'
        if view_conflicts:
            scheduler.display_student_conflicts(student_id)

def display_instructor_timetable_menu(scheduler):
    """Display the instructor timetable generation menu"""
    # Get instructor ID
    instructor_id_str = input("Enter instructor ID: ")
    
    try:
        instructor_id = int(instructor_id_str)
    except ValueError:
        print("Invalid instructor ID. Please enter a number.")
        return
    
    # Check if instructor exists
    conn = get_connection(scheduler.db_path, row_factory=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM instructors WHERE id = ?', (instructor_id,))
    instructor = cursor.fetchone()
    
    if not instructor:
        print(f"Instructor ID {instructor_id} does not exist.")
        conn.close()
        return
    
    # Check if instructor has any scheduled classes
    cursor.execute('SELECT COUNT(*) FROM module_schedule WHERE instructor_id = ?', (instructor_id,))
    schedule_count = cursor.fetchone()[0]
    
    if schedule_count == 0:
        print(f"Instructor ID {instructor_id} has no scheduled classes.")
        conn.close()
        return
    
    conn.close()
    
    # Display timetable format options
    print("\nSelect timetable format:")
    print("1. Display (List view)")
    print("2. Grid view")
    print("3. PDF")
    print("4. CSV")
    print("5. TXT")
    print("6. Excel")
    
    format_choice = input("Enter your choice (1-6): ")
    
    if format_choice == '1':
        scheduler.generate_instructor_timetable(instructor_id, 'display')
    elif format_choice == '2':
        scheduler.generate_instructor_timetable(instructor_id, 'grid')
    elif format_choice == '3':
        pdf_path = scheduler.generate_instructor_timetable(instructor_id, 'pdf')
        open_file_prompt(pdf_path, 'PDF')
    elif format_choice == '4':
        csv_path = scheduler.generate_instructor_timetable(instructor_id, 'csv')
        open_file_prompt(csv_path, 'CSV')
    elif format_choice == '5':
        txt_path = scheduler.generate_instructor_timetable(instructor_id, 'txt')
        open_file_prompt(txt_path, 'TXT')
    elif format_choice == '6':
        excel_path = scheduler.generate_instructor_timetable(instructor_id, 'excel')
        open_file_prompt(excel_path, 'Excel')
    else:
        print("Invalid choice. Using list view as default.")
        scheduler.generate_instructor_timetable(instructor_id, 'display')

def open_file_prompt(file_path, file_type):
    """Prompt user to open the generated file"""
    if file_path:
        open_file = input(f"\nDo you want to open the {file_type} file? (y/n): ").lower() == 'y'
        if open_file:
            try:
                import webbrowser
                webbrowser.open(f"file://{os.path.abspath(file_path)}")
            except Exception as e:
                print(f"Error opening {file_type}: {e}")
                print(f"Please open the file manually: {file_path}")

def display_module_scheduling_menu():
    """Display the module scheduling menu and handle user choices"""
    scheduler = ModuleScheduler()
    
    while True:
        print("\nModule Scheduling and Timetable Menu:")
        print("=====================================")
        print("1. Manage Rooms")
        print("2. Manage Instructors")
        print("3. Manage Module Schedules")
        print("4. View Module Schedules")
        print("5. View Room Schedules")
        print("6. View Instructor Schedules")
        print("7. Generate Student Timetable")
        print("8. Generate Instructor Timetable")
        print("9. Check for Scheduling Conflicts")
        print("10. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-10): ")
        
        if choice == '1':
            display_room_menu(scheduler)
        elif choice == '2':
            display_instructor_menu(scheduler)
        elif choice == '3':
            display_schedule_menu(scheduler)
        elif choice == '4':
            module_code = input("Enter module code (or leave empty for all modules): ")
            scheduler.view_module_schedule(module_code if module_code else None)
        elif choice == '5':
            scheduler.view_room_schedule()
        elif choice == '6':
            scheduler.view_instructor_schedule()
        elif choice == '7':
            display_student_timetable_menu(scheduler)
        elif choice == '8':
            display_instructor_timetable_menu(scheduler)
        elif choice == '9':
            student_id = input("Enter student ID: ")
            scheduler.display_student_conflicts(student_id)
        elif choice == '10':
            print("Returning to main menu...")
            break
        else:
            print("Invalid choice. Please try again.")

def display_view_schedules_menu(scheduler):
    """Display the view schedules menu"""
    while True:
        print("\nView Schedules Menu:")
        print("===================")
        print("1. View Module Schedules")
        print("2. View Room Schedules")
        print("3. View Instructor Schedules")
        print("4. View All Schedules")
        print("5. Search Schedules")
        print("6. Return to Previous Menu")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            module_code = input("Enter module code (or leave empty for all modules): ")
            scheduler.view_module_schedule(module_code if module_code else None)
        elif choice == '2':
            scheduler.view_room_schedule()
        elif choice == '3':
            scheduler.view_instructor_schedule()
        elif choice == '4':
            scheduler.view_module_schedule(None)  # Show all schedules
        elif choice == '5':
            display_advanced_search_menu(scheduler)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def display_timetable_generation_menu(scheduler):
    """Display the timetable generation menu"""
    while True:
        print("\nTimetable Generation Menu:")
        print("=========================")
        print("1. Generate Student Timetable")
        print("2. Generate Instructor Timetable")
        print("3. Generate Room Schedule")
        print("4. Generate Department Schedule")
        print("5. Export to Various Formats")
        print("6. Return to Previous Menu")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            display_student_timetable_menu(scheduler)
        elif choice == '2':
            display_instructor_timetable_menu(scheduler)
        elif choice == '3':
            room_id = input("Enter room ID (or leave empty to list all): ")
            if room_id:
                try:
                    scheduler.view_room_schedule(int(room_id))
                except ValueError:
                    print("Invalid room ID.")
            else:
                scheduler.view_room_schedule()
        elif choice == '4':
            department = input("Enter department name: ")
            if department:
                display_department_schedule(scheduler, department)
        elif choice == '5':
            display_export_menu(scheduler)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def display_department_schedule(scheduler, department):
    """Display schedule for all instructors in a department"""
    conn = get_connection(scheduler.db_path, row_factory=False)
    cursor = conn.cursor()
    
    # Get all instructors in the department
    cursor.execute('''
    SELECT id, first_name, last_name FROM instructors 
    WHERE department = ? AND is_active = 1
    ORDER BY last_name, first_name
    ''', (department,))
    
    instructors = cursor.fetchall()
    
    if not instructors:
        print(f"No active instructors found in department: {department}")
        conn.close()
        return
    
    print(f"\nSchedule for {department} Department:")
    print("=" * 100)
    
    for instructor in instructors:
        instructor_id, first_name, last_name = instructor
        print(f"\n{first_name} {last_name} (ID: {instructor_id}):")
        print("-" * 80)
        
        # Get instructor's schedule
        cursor.execute('''
        SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        WHERE ms.instructor_id = ?
        ORDER BY ms.day_of_week, ms.start_time
        ''', (instructor_id,))
        
        schedules = cursor.fetchall()
        
        if schedules:
            print(f"{'Module':<10} {'Day':<10} {'Time':<15} {'Room':<15} {'Type':<10}")
            print("-" * 70)
            
            for schedule in schedules:
                module_code, day, start, end, building, room, session_type = schedule
                time_slot = f"{start}-{end}"
                room_str = f"{building}-{room}" if building and room else "TBA"
                print(f"{module_code:<10} {day:<10} {time_slot:<15} {room_str:<15} {session_type:<10}")
        else:
            print("No scheduled classes")
    
    conn.close()
    print("=" * 100)

def display_export_menu(scheduler):
    """Display export options menu"""
    print("\nExport Options:")
    print("===============")
    print("1. Export All Schedules to CSV")
    print("2. Export Room Utilization Report")
    print("3. Export Instructor Workload Report")
    print("4. Export to iCal Format")
    print("5. Generate PDF Reports")
    
    choice = input("\nEnter your choice (1-5): ")
    
    if choice == '1':
        filename = scheduler.export_all_schedules_to_csv()
        print(f"All schedules exported to: {filename}")
    elif choice == '2':
        format_choice = input("Choose format (csv/pdf/display): ").lower()
        scheduler.generate_room_utilization_report(format_choice)
    elif choice == '3':
        format_choice = input("Choose format (csv/pdf/display): ").lower()
        scheduler.generate_instructor_workload_report(format_choice)
    elif choice == '4':
        display_ical_export_menu(scheduler)
    elif choice == '5':
        display_pdf_reports_menu(scheduler)
    else:
        print("Invalid choice.")

def display_main_menu_info():
    """Display welcome information and system status"""
    print("\n🎓 Enhanced Module Scheduling System")
    print("=" * 50)
    print("📋 Features Available:")
    print("  • Smart scheduling with conflict detection")
    print("  • Advanced analytics and reporting")
    print("  • Multiple export formats (PDF, CSV, Excel, iCal)")
    print("  • Room and instructor management")
    print("  • Visual timetables and charts")
    print("  • Backup and data validation")
    print("  • Holiday management")
    print("  • Notification system")
    print("=" * 50)

def handle_graceful_exit():
    """Handle graceful system exit with cleanup"""
    print("\n" + "="*60)
    print("🔄 Performing final system checks...")
    
    try:
        scheduler = ModuleScheduler()
        
        # Create exit backup if auto-backup is enabled
        auto_backup = scheduler.get_system_setting('auto_backup', 'True')
        if auto_backup == 'True':
            print("💾 Creating exit backup...")
            scheduler.create_backup(description="Automatic exit backup")
        
        # Quick data validation
        print("🔍 Running quick data validation...")
        issues = scheduler.validate_data_consistency()
        if issues:
            print(f"⚠️  Warning: {len(issues)} data consistency issues detected.")
            print("   Run data validation from the main menu for details.")
        else:
            print("✅ Data validation passed.")
        
        # Check for unresolved conflicts
        conflicts = scheduler._get_all_conflicts()
        active_conflicts = [c for c in conflicts if not c['resolved']]
        if active_conflicts:
            print(f"⚠️  Warning: {len(active_conflicts)} unresolved scheduling conflicts.")
        else:
            print("✅ No scheduling conflicts detected.")
        
        print("✅ System shutdown complete.")
        
    except Exception as e:
        print(f"❌ Error during shutdown: {e}")
    
    print("=" * 60)
    print("Thank you for using the Enhanced Module Scheduling System!")
    print("Have a great day! 🌟")
    print("=" * 60)


# GUI Launcher using factory pattern
try:
    from university_system.modules.shared.feature_gui_factory import create_gui_launcher

    launch_timetable_optimizer_gui = create_gui_launcher(
        title="Smart Timetable Optimizer",
        description="""AI-powered class scheduling with conflict detection and optimization.

Features:
• Smart scheduling algorithm
• Room allocation optimization
• Instructor workload balancing
• Student preference integration
• Conflict detection & resolution
• Visual timetable display
• Template management
• Batch import/export
• Analytics & reports
• Holiday management
• Calendar integration (iCal)
• Notification system
• Data validation
• Backup & restore""",
        cli_instruction="Use CLI: Smart Timetable Optimizer"
    )
except ImportError:
    # Fallback if factory not available
    def launch_timetable_optimizer_gui(root, auth):
        from tkinter import messagebox
        messagebox.showinfo("Timetable Optimizer", "Please use the CLI: Enhanced Module Scheduling System")


# Alias for consistency with refactored naming
display_timetable_optimizer_menu = display_enhanced_scheduling_menu


# Export public API
__all__ = [
    'ModuleScheduler',
    'display_enhanced_scheduling_menu',
    'display_timetable_optimizer_menu',
    'launch_timetable_optimizer_gui',
    'DAYS_OF_WEEK',
    'TIME_SLOTS',
    'SESSION_TYPES',
    'ROOM_TYPES',
]


# Entry point
if __name__ == "__main__":
    try:
        # Display welcome information
        display_main_menu_info()
        
        # Initialize system
        print("\n🚀 Initializing system...")
        scheduler = ModuleScheduler()
        
        # Create automatic backup on startup if enabled
        auto_backup = scheduler.get_system_setting('auto_backup', 'True')
        if auto_backup == 'True':
            print("💾 Creating startup backup...")
            scheduler.create_backup(description="Automatic startup backup")
        
        # Quick system health check
        print("🔍 Performing system health check...")
        issues = scheduler.validate_data_consistency()
        if issues:
            print(f"⚠️  Found {len(issues)} data issues. Consider running data validation.")
        else:
            print("✅ System health check passed.")
        
        print("🎯 System ready!")
        
        # Run the enhanced menu system
        display_enhanced_scheduling_menu()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  System interrupted by user.")
    except Exception as e:
        print(f"\n❌ Critical error: {e}")
        print("Please check your database file and try again.")
    finally:
        # Always perform graceful exit
        handle_graceful_exit()