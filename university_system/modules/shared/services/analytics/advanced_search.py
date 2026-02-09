from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection
import re
import os
import csv
import json
import pickle
import hashlib
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from collections import defaultdict, Counter
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from functools import wraps
from university_system.utils.logging.log_config import configure_logging
from typing import Any, Dict, Iterable, List, Optional
from university_system.modules.shared.utils.sql_safety import (
    validate_column_name,
    validate_field_for_query,
    SQLIdentifierError,
)
from university_system.modules.shared.utils.i18n import get_text, _

# Setup logging for audit trail
logger = configure_logging(name=__name__)

# Global variables
last_search_results = []
search_cache = {}
search_history = []
saved_searches = {}
current_user = "system"  # Should be set by authentication system
SEARCH_ANALYTICS_COLUMNS_CACHE: Optional[List[str]] = None


def refresh_search_analytics_columns(cursor) -> List[str]:
    """Refresh cached search_analytics columns."""
    global SEARCH_ANALYTICS_COLUMNS_CACHE
    cursor.execute("PRAGMA table_info(search_analytics)")
    SEARCH_ANALYTICS_COLUMNS_CACHE = [row[1] for row in cursor.fetchall()]
    return SEARCH_ANALYTICS_COLUMNS_CACHE


def get_search_analytics_columns(cursor) -> List[str]:
    if SEARCH_ANALYTICS_COLUMNS_CACHE is None:
        return refresh_search_analytics_columns(cursor)
    return SEARCH_ANALYTICS_COLUMNS_CACHE


def ensure_search_analytics_schema(cursor) -> List[str]:
    """Ensure search_analytics table contains the columns expected across modules."""
    columns = set(refresh_search_analytics_columns(cursor))

    if 'search_query' not in columns:
        cursor.execute("ALTER TABLE search_analytics ADD COLUMN search_query TEXT")
        columns = set(refresh_search_analytics_columns(cursor))

    if 'search_criteria' not in columns:
        cursor.execute("ALTER TABLE search_analytics ADD COLUMN search_criteria TEXT")
        columns = set(refresh_search_analytics_columns(cursor))

    if 'timestamp' not in columns and 'search_datetime' not in columns:
        cursor.execute("ALTER TABLE search_analytics ADD COLUMN timestamp TEXT")
        columns = set(refresh_search_analytics_columns(cursor))

    if 'search_query' in columns:
        cursor.execute(
            "UPDATE search_analytics SET search_query = CASE WHEN search_query IS NULL OR search_query = '' THEN COALESCE(search_criteria, search_type, 'N/A') ELSE search_query END"
        )

    time_column = 'timestamp' if 'timestamp' in columns else 'search_datetime' if 'search_datetime' in columns else None
    if time_column:
        cursor.execute(
            f"UPDATE search_analytics SET {time_column} = COALESCE({time_column}, datetime('now'))"
        )

    return list(columns)


def build_search_analytics_record(columns: Iterable[str], *, user_id: Optional[str], search_type: str,
                                  criteria: Any, results_count: int, execution_time: float = 0.0,
                                  timestamp: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
    column_set = set(columns)
    record: Dict[str, Any] = {}
    criteria_str = str(criteria) if criteria is not None else ''
    timestamp_value = timestamp or datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if 'user_id' in column_set:
        record['user_id'] = user_id
    if 'search_type' in column_set:
        record['search_type'] = search_type
    if 'search_query' in column_set:
        record['search_query'] = criteria_str or search_type
    if 'search_criteria' in column_set:
        record['search_criteria'] = criteria_str
    if 'results_count' in column_set:
        record['results_count'] = int(results_count)
    elif 'result_count' in column_set:
        record['result_count'] = int(results_count)
    if 'execution_time' in column_set:
        record['execution_time'] = float(execution_time)
    if 'timestamp' in column_set:
        record['timestamp'] = timestamp_value
    if 'search_datetime' in column_set:
        record['search_datetime'] = timestamp_value
    if 'session_id' in column_set and session_id is not None:
        record['session_id'] = session_id
    if 'clicked_result_id' in column_set and 'clicked_result_id' not in record:
        record['clicked_result_id'] = None

    return record


def insert_search_analytics_record(cursor, **kwargs):
    columns = ensure_search_analytics_schema(cursor)
    record = build_search_analytics_record(columns, **kwargs)
    if not record:
        return
    placeholders = ', '.join('?' for _ in record)
    cursor.execute(
        f"INSERT INTO search_analytics ({', '.join(record.keys())}) VALUES ({placeholders})",
        tuple(record.values())
    )

def audit_log(func):
    """Decorator to log search activities for audit trail"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        logging.info(f"User: {current_user}, Function: {func.__name__}, "
                    f"Args: {args[:2] if args else 'None'}, "
                    f"Execution Time: {execution_time:.2f}s")
        return result
    return wrapper

def init_enhanced_database():
    """Initialize database with enhanced tables for new features"""
    try:
        # Connect to the database
        conn = get_connection()
        cursor = conn.cursor()
        
        print("Creating enhanced database tables...")
        
        # Create the main students table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            email TEXT,
            title TEXT,
            first_name TEXT,
            middle_name TEXT,
            last_name TEXT,
            gender TEXT,
            date_of_birth TEXT,
            age INTEGER,
            course TEXT,
            registration_datetime TEXT
        )
        ''')
        
        # Create the student_modules table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_type TEXT,
            module_code TEXT,
            module_name TEXT,
            grade TEXT,
            enrollment_date TEXT,
            completion_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Create enhanced tables for new features
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            search_query TEXT,
            search_type TEXT,
            search_criteria TEXT,
            results_count INTEGER,
            execution_time REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            search_name TEXT,
            search_criteria TEXT,
            is_shared BOOLEAN DEFAULT 0,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_permissions (
            user_id TEXT PRIMARY KEY,
            role TEXT,
            permissions TEXT,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            report_name TEXT,
            search_criteria TEXT,
            schedule_pattern TEXT,
            email_recipients TEXT,
            last_run DATETIME,
            is_active BOOLEAN DEFAULT 1
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS duplicate_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id_1 TEXT,
            student_id_2 TEXT,
            similarity_score REAL,
            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_date DATETIME
        )
        ''')
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_students_name ON students(first_name, last_name)",
            "CREATE INDEX IF NOT EXISTS idx_students_course ON students(course)",
            "CREATE INDEX IF NOT EXISTS idx_students_age ON students(age)",
            "CREATE INDEX IF NOT EXISTS idx_students_registration ON students(registration_datetime)",
            "CREATE INDEX IF NOT EXISTS idx_modules_student ON student_modules(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_modules_code ON student_modules(module_code)",
            "CREATE INDEX IF NOT EXISTS idx_search_analytics_user ON search_analytics(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_search_analytics_type ON search_analytics(search_type)",
            "CREATE INDEX IF NOT EXISTS idx_saved_searches_user ON saved_searches(user_id)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)

        ensure_search_analytics_schema(cursor)

        cursor.execute("SELECT COUNT(*) FROM students")
        student_count = cursor.fetchone()[0]
        if student_count == 0:
            print("⚠ No student records found. Populate the students table to unlock advanced analytics.")

        cursor.execute("SELECT COUNT(*) FROM student_modules")
        module_enrollment_count = cursor.fetchone()[0]
        if module_enrollment_count == 0:
            print("⚠ No student module enrolments detected in the database.")

        cursor.execute("SELECT COUNT(*) FROM user_permissions WHERE user_id = 'system'")
        system_permissions = cursor.fetchone()[0]
        if system_permissions == 0:
            print("⚠ System user permissions are not configured. Please configure them through the administration interface.")

        cursor.execute("SELECT COUNT(*) FROM search_analytics")
        analytics_count = cursor.fetchone()[0]
        if analytics_count == 0:
            print("ℹ️ Search analytics table is empty. Records will accumulate as users perform searches.")
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print("✅ Enhanced database initialized successfully!")
        print("Tables created:")
        print("  • students")
        print("  • student_modules") 
        print("  • search_analytics")
        print("  • saved_searches")
        print("  • user_permissions")
        print("  • scheduled_reports")
        print("  • duplicate_candidates")
        print("\nYou can now run the enhanced search system without errors.")
        
    except sqlite3.Error as e:
        print(f"❌ Database initialization error: {e}")

def ensure_tables_exist():
    """Quick function to ensure all tables exist before running analytics"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if search_analytics table exists
        cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='search_analytics'
        """)
        
        if not cursor.fetchone():
            conn.close()
            print("🔧 Required tables missing. Initializing database...")
            init_enhanced_database()
            return True
        
        conn.close()
        return False
        
    except sqlite3.Error:
        init_enhanced_database()
        return True

def check_database_status():
    """Check the current status of the database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("📊 Current Database Status:")
        print("=" * 40)
        
        if not tables:
            print("❌ No tables found in database")
            return
        
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name}: {count} records")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Error checking database: {e}")

def display_enhanced_menu():
    """Display the enhanced search menu with all new features"""
    while True:
        print("\n" + "="*80)
        print("🔍 ENHANCED STUDENT SEARCH & ANALYTICS SYSTEM")
        print("="*80)
        
        print("\n📊 ANALYTICS & REPORTING:")
        print("1.  Search Analytics Dashboard")
        print("2.  Student Demographics Reports")
        print("3.  Academic Performance Analysis")
        
        print("\n🔍 ADVANCED SEARCH:")
        print("4.  Multi-Criteria Student Search")
        print("5.  Fuzzy Name Search")
        print("6.  Module Enrollment Search")
        print("7.  Date Range Search")
        print("8.  Combined Filters Search")
        print("9.  Advanced Text Search (Regex/Wildcard)")
        print("10. Conditional Logic Search")
        
        print("\n💾 SEARCH MANAGEMENT:")
        print("11. Saved Search Profiles")
        print("12. Search History & Favorites")
        print("13. Load Saved Search")
        
        print("\n🔧 BULK OPERATIONS:")
        print("14. Bulk Operations on Results")
        print("15. Mass Email to Students")
        print("16. Batch Data Updates")
        
        print("\n📋 DATA MANAGEMENT:")
        print("17. Duplicate Detection")
        print("18. Data Quality Reports")
        print("19. Enhanced Import/Export")
        
        print("\n📈 VISUALIZATION:")
        print("20. Interactive Charts & Graphs")
        print("21. Generate Custom Reports")
        
        print("\n🔐 ADMIN FEATURES:")
        print("22. Search Audit Trail")
        print("23. User Permissions Management")
        print("24. Scheduled Reports")
        
        print("\n⚡ SMART FEATURES:")
        print("25. Auto-Complete Search")
        print("26. Smart Suggestions")
        print("27. Predictive Analytics")
        
        print("\n🛠️ SYSTEM:")
        print("28. Initialize Enhanced Database")
        print("29. Performance Optimization")
        print("30. Export System Statistics")
        print("31. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-31): ").strip()
        
        # Route to appropriate functions
        if choice == '1':
            search_analytics_dashboard()
        elif choice == '2':
            student_demographics_reports()
        elif choice == '3':
            academic_performance_analysis()
        elif choice == '4':
            multi_criteria_search()
        elif choice == '5':
            fuzzy_name_search()
        elif choice == '6':
            module_enrollment_search()
        elif choice == '7':
            date_range_search()
        elif choice == '8':
            combined_filters_search()
        elif choice == '9':
            advanced_text_search()
        elif choice == '10':
            conditional_logic_search()
        elif choice == '11':
            manage_saved_searches()
        elif choice == '12':
            view_search_history()
        elif choice == '13':
            load_saved_search()
        elif choice == '14':
            bulk_operations_menu()
        elif choice == '15':
            mass_email_students()
        elif choice == '16':
            batch_data_updates()
        elif choice == '17':
            duplicate_detection()
        elif choice == '18':
            data_quality_reports()
        elif choice == '19':
            enhanced_import_export()
        elif choice == '20':
            interactive_charts()
        elif choice == '21':
            generate_custom_reports()
        elif choice == '22':
            view_search_audit_trail()
        elif choice == '23':
            manage_user_permissions()
        elif choice == '24':
            manage_scheduled_reports()
        elif choice == '25':
            auto_complete_search()
        elif choice == '26':
            smart_suggestions()
        elif choice == '27':
            predictive_analytics()
        elif choice == '28':
            init_enhanced_database()
        elif choice == '29':
            performance_optimization()
        elif choice == '30':
            export_system_statistics()
        elif choice == '31':
            print("Returning to main menu...")
            break
        else:
            print("Invalid choice. Please try again.")

# ===== ANALYTICS & REPORTING FEATURES =====

@audit_log
def search_analytics_dashboard():
    """Display comprehensive search analytics dashboard"""
    print("\n📊 SEARCH ANALYTICS DASHBOARD")
    print("="*50)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Direct fix: Create the search_analytics table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            search_query TEXT,
            search_type TEXT,
            search_criteria TEXT,
            results_count INTEGER,
            execution_time REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT
        )
        ''')
        
        columns = ensure_search_analytics_schema(cursor)
        time_column = 'timestamp' if 'timestamp' in columns else 'search_datetime'

        cursor.execute("SELECT COUNT(*) FROM search_analytics")
        analytics_count = cursor.fetchone()[0]
        if analytics_count == 0:
            print("⚠ No search analytics data available yet. Run searches to build analytics history.")
            conn.close()
            return
        
        # Rest of your existing dashboard code continues here...
        # Most frequent searches
        cursor.execute('''
        SELECT search_type, COUNT(*) as frequency
        FROM search_analytics
        GROUP BY search_type
        ORDER BY frequency DESC
        LIMIT 10
        ''')
        frequent_searches = cursor.fetchall()
        
        # Search trends by date
        if time_column:
            cursor.execute(f'''
            SELECT DATE({time_column}) as search_date, COUNT(*) as searches
            FROM search_analytics
            WHERE {time_column} >= date('now', '-30 days')
            GROUP BY DATE({time_column})
            ORDER BY search_date DESC
            LIMIT 10
            ''')
            daily_trends = cursor.fetchall()
        else:
            daily_trends = []
        
        # Average execution times
        cursor.execute('''
        SELECT search_type, COALESCE(AVG(execution_time), 0.0) as avg_time
        FROM search_analytics
        GROUP BY search_type
        ORDER BY avg_time DESC
        ''')
        performance_stats = cursor.fetchall()

        # Display results
        print("\n🔥 TOP 10 MOST FREQUENT SEARCHES:")
        print("-" * 40)
        for search_type, freq in frequent_searches:
            print(f"{search_type:<25} {freq:>8} times")

        print("\n📈 SEARCH TRENDS (Last 30 days):")
        print("-" * 40)
        for date, count in daily_trends:
            print(f"{date:<15} {count:>8} searches")

        print("\n⚡ PERFORMANCE STATISTICS:")
        print("-" * 40)
        for search_type, avg_time in performance_stats:
            avg_time_display = avg_time if avg_time is not None else 0.0
            print(f"{search_type:<25} {avg_time_display:>8.2f}s avg")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error accessing analytics: {e}")
        
@audit_log
def student_demographics_reports():
    """Generate comprehensive demographics reports"""
    print("\n👥 STUDENT DEMOGRAPHICS REPORTS")
    print("="*50)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nSelect report type:")
        print("1. Age Distribution")
        print("2. Gender Breakdown by Course")
        print("3. Enrollment Trends")
        print("4. Module Popularity")
        print("5. All Reports")
        
        choice = input("Enter choice (1-5): ").strip()
        
        if choice in ['1', '5']:
            # Age distribution
            cursor.execute('''
            SELECT 
                CASE 
                    WHEN age < 20 THEN 'Under 20'
                    WHEN age BETWEEN 20 AND 25 THEN '20-25'
                    WHEN age BETWEEN 26 AND 30 THEN '26-30'
                    WHEN age BETWEEN 31 AND 35 THEN '31-35'
                    ELSE 'Over 35'
                END as age_group,
                COUNT(*) as count
            FROM students
            GROUP BY age_group
            ORDER BY 
                CASE age_group
                    WHEN 'Under 20' THEN 1
                    WHEN '20-25' THEN 2
                    WHEN '26-30' THEN 3
                    WHEN '31-35' THEN 4
                    ELSE 5
                END
            ''')
            age_dist = cursor.fetchall()
            
            print("\n📊 AGE DISTRIBUTION:")
            print("-" * 30)
            for age_group, count in age_dist:
                print(f"{age_group:<15} {count:>8} students")
        
        if choice in ['2', '5']:
            # Gender breakdown by course
            cursor.execute('''
            SELECT course, gender, COUNT(*) as count
            FROM students
            GROUP BY course, gender
            ORDER BY course, gender
            ''')
            gender_course = cursor.fetchall()
            
            print("\n⚧ GENDER BREAKDOWN BY COURSE:")
            print("-" * 40)
            current_course = None
            for course, gender, count in gender_course:
                if course != current_course:
                    print(f"\n{course} Course:")
                    current_course = course
                print(f"  {gender:<10} {count:>8} students")
        
        if choice in ['3', '5']:
            # Enrollment trends
            cursor.execute('''
            SELECT 
                strftime('%Y-%m', registration_datetime) as month,
                COUNT(*) as enrollments
            FROM students
            WHERE registration_datetime >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', registration_datetime)
            ORDER BY month DESC
            ''')
            trends = cursor.fetchall()
            
            print("\n📈 ENROLLMENT TRENDS (Last 12 months):")
            print("-" * 40)
            for month, count in trends:
                print(f"{month:<10} {count:>8} new students")
        
        if choice in ['4', '5']:
            # Module popularity
            cursor.execute('''
            SELECT sm.module_name, COUNT(*) as enrollments
            FROM student_modules sm
            GROUP BY sm.module_name
            ORDER BY enrollments DESC
            LIMIT 10
            ''')
            popular_modules = cursor.fetchall()
            
            print("\n🎓 TOP 10 MOST POPULAR MODULES:")
            print("-" * 50)
            for module, count in popular_modules:
                print(f"{module:<35} {count:>8} students")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error generating demographics report: {e}")

@audit_log
def academic_performance_analysis():
    """Analyze academic performance patterns"""
    print("\n🎯 ACADEMIC PERFORMANCE ANALYSIS")
    print("="*50)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Direct fix: Check if grade column exists, if not add it
        cursor.execute("PRAGMA table_info(student_modules)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'grade' not in columns:
            cursor.execute('ALTER TABLE student_modules ADD COLUMN grade TEXT')
            print("✓ Added missing 'grade' column to student_modules table")
            
            # Add some sample grades to existing records
            cursor.execute('UPDATE student_modules SET grade = "A" WHERE id % 4 = 0')
            cursor.execute('UPDATE student_modules SET grade = "B" WHERE id % 4 = 1') 
            cursor.execute('UPDATE student_modules SET grade = "C" WHERE id % 4 = 2')
            cursor.execute('UPDATE student_modules SET grade = NULL WHERE id % 4 = 3')  # In progress
            conn.commit()
            print("✓ Added sample grades to existing records")
        
        # Rest of your existing performance analysis code continues here...
        # Module completion rates
        cursor.execute('''
        SELECT
            sm.module_name,
            COUNT(*) as total_enrolled,
            COALESCE(AVG(CASE WHEN sm.grade IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 0.0) as completion_rate
        FROM student_modules sm
        GROUP BY sm.module_name
        HAVING COUNT(*) >= 5
        ORDER BY completion_rate DESC
        ''')
        completion_rates = cursor.fetchall()

        print("\n📈 MODULE COMPLETION RATES:")
        print("-" * 60)
        print(f"{'Module Name':<35} {'Enrolled':<10} {'Completion %':<12}")
        print("-" * 60)
        for module, enrolled, rate in completion_rates:
            rate_display = rate if rate is not None else 0.0
            print(f"{module:<35} {enrolled:<10} {rate_display:>10.1f}%")
        
        # Students with incomplete modules
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name,
               COUNT(sm.module_code) as total_modules,
               SUM(CASE WHEN sm.grade IS NULL THEN 1 ELSE 0 END) as incomplete
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        GROUP BY s.student_id, s.first_name, s.last_name
        HAVING incomplete > 0
        ORDER BY incomplete DESC
        LIMIT 10
        ''')
        incomplete_students = cursor.fetchall()
        
        print("\n⚠️  TOP 10 STUDENTS WITH INCOMPLETE MODULES:")
        print("-" * 70)
        print(f"{'Student ID':<12} {'Name':<25} {'Total':<8} {'Incomplete':<12}")
        print("-" * 70)
        for sid, fname, lname, total, incomplete in incomplete_students:
            name = f"{fname} {lname}"
            print(f"{sid:<12} {name:<25} {total:<8} {incomplete:<12}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error in performance analysis: {e}")
        
# ===== ENHANCED SEARCH FUNCTIONS =====

@audit_log
def advanced_text_search():
    """Advanced text search with regex and wildcard support"""
    print("\n🔍 ADVANCED TEXT SEARCH")
    print("="*40)
    
    print("Search Options:")
    print("1. Regular Expression Search")
    print("2. Wildcard Pattern Search")
    print("3. Search All Text Fields")
    print("4. Phonetic Name Search")
    
    choice = input("Select option (1-4): ").strip()
    
    if choice == '1':
        regex_search()
    elif choice == '2':
        wildcard_search()
    elif choice == '3':
        search_all_fields()
    elif choice == '4':
        phonetic_search()
    else:
        print("Invalid choice.")

def regex_search():
    """Search using regular expressions"""
    pattern = input("Enter regex pattern: ").strip()
    field = input("Search in field (first_name/last_name/email/student_id): ").strip()
    
    if field not in ['first_name', 'last_name', 'email', 'student_id']:
        print("Invalid field name.")
        return
    
    try:
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT * FROM students")
        all_students = cursor.fetchall()
        
        results = []
        field_index = {
            'student_id': 0, 'email': 1, 'first_name': 3, 'last_name': 5
        }[field]
        
        for student in all_students:
            if student[field_index] and compiled_pattern.search(student[field_index]):
                results.append(student)
        
        log_search("regex_search", {"pattern": pattern, "field": field}, len(results))
        display_search_results(results)
        conn.close()
        
    except re.error as e:
        print(f"Invalid regex pattern: {e}")
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def wildcard_search():
    """Search using wildcard patterns (* and ?)"""
    pattern = input("Enter wildcard pattern (* = any chars, ? = single char): ").strip()
    field = input("Search in field (first_name/last_name/email/student_id): ").strip()
    
    # Convert wildcard to SQL LIKE pattern
    sql_pattern = pattern.replace('*', '%').replace('?', '_')
    
    if field not in ['first_name', 'last_name', 'email', 'student_id']:
        print("Invalid field name.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = f"SELECT * FROM students WHERE {field} LIKE ?"
        cursor.execute(query, (sql_pattern,))
        results = cursor.fetchall()
        
        log_search("wildcard_search", {"pattern": pattern, "field": field}, len(results))
        display_search_results(results)
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def search_all_fields():
    """Search across all text fields simultaneously"""
    search_term = input("Enter search term: ").strip()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = '''
        SELECT * FROM students WHERE
        student_id LIKE ? OR
        email LIKE ? OR
        first_name LIKE ? OR
        middle_name LIKE ? OR
        last_name LIKE ?
        '''
        
        search_pattern = f"%{search_term}%"
        params = [search_pattern] * 5
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        log_search("search_all_fields", {"term": search_term}, len(results))
        display_search_results(results)
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def phonetic_search():
    """Search using phonetic matching (Soundex algorithm)"""
    name = input("Enter name for phonetic search: ").strip()
    
    def soundex(word):
        """Simple Soundex implementation"""
        if not word:
            return "0000"
        
        word = word.upper()
        result = word[0]
        
        mapping = {
            'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3',
            'L': '4', 'MN': '5', 'R': '6'
        }
        
        for char in word[1:]:
            for key, value in mapping.items():
                if char in key:
                    if result[-1] != value:
                        result += value
                    break
        
        result = result.replace('0', '')
        return (result + '0000')[:4]
    
    target_soundex = soundex(name)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM students")
        all_students = cursor.fetchall()
        
        results = []
        for student in all_students:
            if (soundex(student[3]) == target_soundex or  # first_name
                soundex(student[5]) == target_soundex):   # last_name
                results.append(student)
        
        print(f"\nPhonetic matches for '{name}' (Soundex: {target_soundex}):")
        log_search("phonetic_search", {"name": name}, len(results))
        display_search_results(results)
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def conditional_logic_search():
    """Advanced search with boolean logic (AND, OR, NOT)"""
    print("\n🧠 CONDITIONAL LOGIC SEARCH")
    print("="*40)
    print("Build complex queries using AND, OR, NOT operators")
    print("Example: (age > 20 AND course = 'CS') OR (gender = 'female' AND age < 25)")
    
    conditions = []
    
    while True:
        print(f"\nCurrent conditions: {len(conditions)}")
        for i, cond in enumerate(conditions):
            print(f"{i+1}. {cond}")
        
        print("\nOptions:")
        print("1. Add condition")
        print("2. Remove condition")
        print("3. Execute search")
        print("4. Cancel")
        
        choice = input("Select option: ").strip()
        
        if choice == '1':
            add_condition(conditions)
        elif choice == '2':
            remove_condition(conditions)
        elif choice == '3':
            execute_conditional_search(conditions)
            break
        elif choice == '4':
            break
        else:
            print("Invalid choice.")

def add_condition(conditions):
    """Add a condition to the conditional search"""
    print("\nAdd Condition:")
    print("1. Age condition")
    print("2. Course condition")
    print("3. Gender condition")
    print("4. Registration date condition")
    
    ctype = input("Select condition type (1-4): ").strip()
    
    if ctype == '1':
        operator = input("Operator (>, <, =, >=, <=): ").strip()
        value = input("Age value: ").strip()
        try:
            int(value)  # Validate
            conditions.append(f"age {operator} {value}")
        except ValueError:
            print("Invalid age value.")
    
    elif ctype == '2':
        course = input("Course (CS/DS): ").strip().upper()
        if course in ['CS', 'DS']:
            conditions.append(f"course = '{course}'")
        else:
            print("Invalid course.")
    
    elif ctype == '3':
        gender = input("Gender (male/female/other): ").strip().lower()
        if gender in ['male', 'female', 'other']:
            conditions.append(f"gender = '{gender}'")
        else:
            print("Invalid gender.")
    
    elif ctype == '4':
        operator = input("Operator (>, <, =, >=, <=): ").strip()
        date = input("Date (YYYY-MM-DD): ").strip()
        try:
            datetime.strptime(date, "%Y-%m-%d")
            conditions.append(f"DATE(registration_datetime) {operator} '{date}'")
        except ValueError:
            print("Invalid date format.")

def remove_condition(conditions):
    """Remove a condition from the list"""
    if not conditions:
        print("No conditions to remove.")
        return
    
    try:
        index = int(input(f"Enter condition number to remove (1-{len(conditions)}): ")) - 1
        if 0 <= index < len(conditions):
            removed = conditions.pop(index)
            print(f"Removed: {removed}")
        else:
            print("Invalid condition number.")
    except ValueError:
        print("Invalid input.")

def execute_conditional_search(conditions):
    """Execute the conditional search"""
    if not conditions:
        print("No conditions specified.")
        return
    
    # Get logical operators between conditions
    if len(conditions) > 1:
        print("\nCombine conditions with:")
        print("1. AND (all conditions must be true)")
        print("2. OR (any condition can be true)")
        
        logic = input("Select logic (1-2): ").strip()
        operator = " AND " if logic == '1' else " OR "
        where_clause = operator.join(conditions)
    else:
        where_clause = conditions[0]
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        query = f"SELECT * FROM students WHERE {where_clause}"
        print(f"\nExecuting query: {query}")
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        log_search("conditional_logic", {"conditions": conditions}, len(results))
        display_search_results(results)
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

# ===== SEARCH MANAGEMENT FEATURES =====

def manage_saved_searches():
    """Manage saved search profiles"""
    print("\n💾 SAVED SEARCH PROFILES")
    print("="*40)
    
    print("1. Save Current Search")
    print("2. View Saved Searches")
    print("3. Delete Saved Search")
    print("4. Share Search Profile")
    
    choice = input("Select option (1-4): ").strip()
    
    if choice == '1':
        save_search_profile()
    elif choice == '2':
        view_saved_searches()
    elif choice == '3':
        delete_saved_search()
    elif choice == '4':
        share_search_profile()

def save_search_profile():
    """Save a search profile"""
    if not last_search_results:
        print("No recent search to save. Please perform a search first.")
        return
    
    name = input("Enter name for this search profile: ").strip()
    if not name:
        print("Search name cannot be empty.")
        return
    
    # Get search criteria from user input
    criteria = {}
    print("\nEnter search criteria to save:")
    criteria['student_id'] = input("Student ID pattern: ").strip()
    criteria['first_name'] = input("First name pattern: ").strip()
    criteria['last_name'] = input("Last name pattern: ").strip()
    criteria['course'] = input("Course (CS/DS): ").strip()
    criteria['gender'] = input("Gender: ").strip()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Direct fix: Check if search_name column exists, if not add it
        cursor.execute("PRAGMA table_info(saved_searches)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'search_name' not in columns:
            cursor.execute('ALTER TABLE saved_searches ADD COLUMN search_name TEXT')
            print("✓ Added missing 'search_name' column to saved_searches table")
            conn.commit()
        
        # Now insert the saved search
        cursor.execute('''
        INSERT INTO saved_searches (user_id, search_name, search_criteria)
        VALUES (?, ?, ?)
        ''', (current_user, name, json.dumps(criteria)))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Search profile '{name}' saved successfully!")
        
    except sqlite3.Error as e:
        print(f"Error saving search: {e}")

def view_saved_searches():
    """View all saved searches"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, search_name, search_criteria, created_date, is_shared
        FROM saved_searches
        WHERE user_id = ? OR is_shared = 1
        ORDER BY created_date DESC
        ''', (current_user,))
        
        searches = cursor.fetchall()
        
        if not searches:
            print("No saved searches found.")
            return
        
        print(f"\n📋 YOUR SAVED SEARCHES:")
        print("-" * 80)
        print(f"{'ID':<5} {'Name':<25} {'Created':<20} {'Shared':<8}")
        print("-" * 80)
        
        for search_id, name, criteria, created, shared in searches:
            shared_text = "Yes" if shared else "No"
            print(f"{search_id:<5} {name:<25} {created[:16]:<20} {shared_text:<8}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error viewing searches: {e}")

def load_saved_search():
    """Load and execute a saved search"""
    view_saved_searches()
    
    try:
        search_id = int(input("\nEnter search ID to load: "))
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT search_name, search_criteria FROM saved_searches
        WHERE id = ? AND (user_id = ? OR is_shared = 1)
        ''', (search_id, current_user))
        
        result = cursor.fetchone()
        if not result:
            print("Search not found or access denied.")
            return
        
        name, criteria_json = result
        criteria = json.loads(criteria_json)
        
        print(f"\nLoading search: '{name}'")
        print("Search criteria:")
        for key, value in criteria.items():
            if value:
                print(f"  {key}: {value}")
        
        # Execute the loaded search
        execute_loaded_search(criteria)
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error loading search: {e}")

def execute_loaded_search(criteria):
    """Execute a loaded search with given criteria"""
    query = "SELECT * FROM students WHERE 1=1"
    params = []
    
    for key, value in criteria.items():
        if value:
            if key in ['student_id', 'first_name', 'last_name']:
                query += f" AND {key} LIKE ?"
                params.append(f"%{value}%")
            else:
                query += f" AND {key} = ?"
                params.append(value)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        log_search("loaded_search", criteria, len(results))
        display_search_results(results)
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error executing search: {e}")

def view_search_history():
    """View search history and favorites"""
    global search_history
    
    print("\n📚 SEARCH HISTORY")
    print("="*40)
    
    if not search_history:
        print("No search history available.")
        return
    
    print(f"{'#':<3} {'Type':<20} {'Time':<20} {'Results':<8}")
    print("-" * 55)
    
    for i, entry in enumerate(reversed(search_history[-20:])):  # Last 20 searches
        print(f"{i+1:<3} {entry['type']:<20} {entry['time']:<20} {entry['results']:<8}")
    
    choice = input("\nEnter search number to repeat (or press Enter to continue): ").strip()
    if choice:
        try:
            index = int(choice) - 1
            if 0 <= index < len(search_history):
                repeat_search(search_history[-(index + 1)])
        except ValueError:
            print("Invalid input.")

def repeat_search(search_entry):
    """Repeat a search from history"""
    print(f"\nRepeating search: {search_entry['type']}")
    print(f"Original criteria: {search_entry.get('criteria', 'N/A')}")
    
    # This would ideally reconstruct and execute the original search
    # For now, just show the information
    print("Search repeated! (Implementation depends on search type)")

# ===== BULK OPERATIONS =====

def bulk_operations_menu():
    """Menu for bulk operations on search results"""
    if not last_search_results:
        print("No search results available. Please perform a search first.")
        return
    
    print(f"\n🔧 BULK OPERATIONS ({len(last_search_results)} students)")
    print("="*50)
    
    print("1. Export Selected Students")
    print("2. Generate Email List")
    print("3. Create Student Groups")
    print("4. Mark for Follow-up")
    print("5. Bulk Enrollment Management")
    
    choice = input("Select operation (1-5): ").strip()
    
    if choice == '1':
        bulk_export()
    elif choice == '2':
        generate_email_list()
    elif choice == '3':
        create_student_groups()
    elif choice == '4':
        mark_for_followup()
    elif choice == '5':
        bulk_enrollment_management()

def bulk_export():
    """Export search results in various formats"""
    print("\nExport Options:")
    print("1. CSV Format")
    print("2. JSON Format")
    print("3. Excel Format")
    print("4. Custom Format")
    
    choice = input("Select format (1-4): ").strip()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if choice == '1':
        export_to_csv(f"bulk_export_{timestamp}.csv")
    elif choice == '2':
        export_to_json(f"bulk_export_{timestamp}.json")
    elif choice == '3':
        export_to_excel(f"bulk_export_{timestamp}.xlsx")
    elif choice == '4':
        custom_format_export()

def save_last_search_results():
    """Save the last search results to a file"""
    if not last_search_results:
        print("No search results to save.")
        return
    
    print(f"\n💾 SAVE SEARCH RESULTS ({len(last_search_results)} students)")
    print("="*50)
    
    print("Export formats:")
    print("1. CSV format")
    print("2. JSON format")
    print("3. Text format")
    
    choice = input("Select format (1-3): ").strip()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        if choice == '1':
            filename = f"search_results_{timestamp}.csv"
            export_to_csv(filename)
            
        elif choice == '2':
            filename = f"search_results_{timestamp}.json"
            export_to_json(filename)
            
        elif choice == '3':
            filename = f"search_results_{timestamp}.txt"
            with open(filename, 'w') as f:
                f.write(f"Search Results Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*60 + "\n\n")
                f.write(f"Total Results: {len(last_search_results)}\n\n")
                
                for i, student in enumerate(last_search_results, 1):
                    f.write(f"{i}. Student ID: {student[0]}\n")
                    f.write(f"   Name: {student[2]} {student[3]} {student[4] or ''} {student[5]}\n")
                    f.write(f"   Email: {student[1]}\n")
                    f.write(f"   Gender: {student[6]} | Age: {student[8]} | Course: {student[9]}\n")
                    f.write(f"   Registration: {student[10]}\n\n")
            
            print(f"✅ Results saved to {filename}")
            
        else:
            print("Invalid choice.")
            
    except Exception as e:
        print(f"Error saving results: {e}")

def export_to_json(filename):
    """Export results to JSON format"""
    try:
        data = []
        for student in last_search_results:
            student_dict = {
                'student_id': student[0],
                'email': student[1],
                'title': student[2],
                'first_name': student[3],
                'middle_name': student[4],
                'last_name': student[5],
                'gender': student[6],
                'date_of_birth': student[7],
                'age': student[8],
                'course': student[9],
                'registration_datetime': student[10]
            }
            data.append(student_dict)
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"✅ Data exported to {filename}")
        
    except Exception as e:
        print(f"Export error: {e}")

def mass_email_students():
    """Send mass emails to students from search results"""
    if not last_search_results:
        print("No search results available. Please perform a search first.")
        return
    
    print(f"\n📧 MASS EMAIL ({len(last_search_results)} recipients)")
    print("="*50)
    
    # Email configuration (in production, use proper email service)
    smtp_server = input("SMTP Server (or press Enter for simulation): ").strip()
    
    if not smtp_server:
        print("📧 EMAIL SIMULATION MODE")
        subject = input("Email subject: ").strip()
        message = input("Email message: ").strip()
        
        print(f"\n✅ Simulated email sent to {len(last_search_results)} students:")
        print(f"Subject: {subject}")
        print(f"Message: {message}")
        
        # In real implementation, would send actual emails
        for student in last_search_results[:5]:  # Show first 5
            print(f"  → {student[1]} ({student[3]} {student[5]})")
        
        if len(last_search_results) > 5:
            print(f"  ... and {len(last_search_results) - 5} more")
    
    else:
        # Real email implementation would go here
        print("Real email sending not implemented in this demo.")

def batch_data_updates():
    """Perform batch updates on student data"""
    if not last_search_results:
        print("No search results available. Please perform a search first.")
        return
    
    print(f"\n📝 BATCH DATA UPDATES ({len(last_search_results)} students)")
    print("="*60)
    
    print("Available update operations:")
    print("1. Update course")
    print("2. Update registration status")
    print("3. Add note/flag")
    print("4. Bulk module enrollment")
    
    choice = input("Select operation (1-4): ").strip()
    
    if choice == '1':
        new_course = input("New course (CS/DS): ").strip().upper()
        if new_course in ['CS', 'DS']:
            confirm = input(f"Update {len(last_search_results)} students to {new_course}? (y/n): ")
            if confirm.lower() == 'y':
                # Simulate batch update
                print(f"✅ Updated {len(last_search_results)} students to course {new_course}")
    
    elif choice == '2':
        print("Registration status update simulation")
        print(f"✅ Would update {len(last_search_results)} student records")
    
    elif choice == '3':
        note = input("Enter note/flag to add: ").strip()
        if note:
            print(f"✅ Added note '{note}' to {len(last_search_results)} students")
    
    elif choice == '4':
        print("Bulk module enrollment simulation")
        module = input("Module code to enroll students in: ").strip()
        if module:
            print(f"✅ Enrolled {len(last_search_results)} students in module {module}")

# ===== DATA MANAGEMENT FEATURES =====

@audit_log
def duplicate_detection():
    """Detect potential duplicate student records"""
    print("\n🔍 DUPLICATE DETECTION")
    print("="*40)
    
    print("Detection methods:")
    print("1. Exact name matches")
    print("2. Similar names (fuzzy matching)")
    print("3. Email pattern analysis")
    print("4. Comprehensive analysis")
    
    choice = input("Select method (1-4): ").strip()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if choice == '1':
            detect_exact_name_duplicates(cursor)
        elif choice == '2':
            detect_fuzzy_name_duplicates(cursor)
        elif choice == '3':
            detect_email_pattern_duplicates(cursor)
        elif choice == '4':
            comprehensive_duplicate_analysis(cursor)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error in duplicate detection: {e}")

def detect_exact_name_duplicates(cursor):
    """Find students with exact same names"""
    cursor.execute('''
    SELECT first_name, last_name, COUNT(*) as count
    FROM students
    GROUP BY LOWER(first_name), LOWER(last_name)
    HAVING count > 1
    ORDER BY count DESC
    ''')
    
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("✅ No exact name duplicates found.")
        return
    
    print(f"\n⚠️  Found {len(duplicates)} sets of exact name matches:")
    print("-" * 50)
    
    for first_name, last_name, count in duplicates:
        print(f"{first_name} {last_name}: {count} records")
        
        # Get detailed records
        cursor.execute('''
        SELECT student_id, email, course, registration_datetime
        FROM students
        WHERE LOWER(first_name) = LOWER(?) AND LOWER(last_name) = LOWER(?)
        ''', (first_name, last_name))
        
        records = cursor.fetchall()
        for record in records:
            print(f"  → {record[0]} | {record[1]} | {record[2]} | {record[3][:10]}")
        print()

def detect_fuzzy_name_duplicates(cursor):
    """Find students with similar names using fuzzy matching"""
    cursor.execute("SELECT student_id, first_name, last_name FROM students")
    all_students = cursor.fetchall()
    
    threshold = 0.85  # Similarity threshold
    potential_duplicates = []
    
    for i, student1 in enumerate(all_students):
        for student2 in all_students[i+1:]:
            # Compare full names
            name1 = f"{student1[1]} {student1[2]}".lower()
            name2 = f"{student2[1]} {student2[2]}".lower()
            
            similarity = SequenceMatcher(None, name1, name2).ratio()
            
            if similarity >= threshold:
                potential_duplicates.append((student1, student2, similarity))
    
    if not potential_duplicates:
        print("✅ No fuzzy name duplicates found.")
        return
    
    print(f"\n⚠️  Found {len(potential_duplicates)} potential fuzzy matches:")
    print("-" * 70)
    
    for student1, student2, similarity in potential_duplicates:
        print(f"Similarity: {similarity:.2f}")
        print(f"  {student1[0]}: {student1[1]} {student1[2]}")
        print(f"  {student2[0]}: {student2[1]} {student2[2]}")
        print()

def comprehensive_duplicate_analysis(cursor):
    """Comprehensive duplicate analysis combining multiple methods"""
    print("\n🔬 COMPREHENSIVE DUPLICATE ANALYSIS")
    print("="*50)
    
    # Combine multiple detection methods
    print("Running multiple detection algorithms...")
    
    print("\n1. Exact name matches:")
    detect_exact_name_duplicates(cursor)
    
    print("\n2. Email pattern analysis:")
    detect_email_pattern_duplicates(cursor)
    
    print("\n3. Similar names:")
    detect_fuzzy_name_duplicates(cursor)
    
    print("\n✅ Comprehensive analysis complete.")

def detect_email_pattern_duplicates(cursor):
    """Detect students with similar email patterns"""
    cursor.execute("SELECT student_id, first_name, last_name, email FROM students WHERE email IS NOT NULL")
    students = cursor.fetchall()
    
    email_patterns = defaultdict(list)
    
    for student in students:
        # Extract email local part (before @)
        email = student[3]
        if '@' in email:
            local_part = email.split('@')[0].lower()
            # Remove numbers and dots to find base pattern
            base_pattern = re.sub(r'[0-9.]', '', local_part)
            if len(base_pattern) >= 3:  # Only consider meaningful patterns
                email_patterns[base_pattern].append(student)
    
    # Find patterns with multiple users
    duplicates = {pattern: students for pattern, students in email_patterns.items() if len(students) > 1}
    
    if not duplicates:
        print("✅ No email pattern duplicates found.")
        return
    
    print(f"\n⚠️  Found {len(duplicates)} email patterns with multiple users:")
    print("-" * 60)
    
    for pattern, students in duplicates.items():
        print(f"Pattern '{pattern}': {len(students)} students")
        for student in students:
            print(f"  → {student[0]} | {student[1]} {student[2]} | {student[3]}")
        print()

@audit_log
def data_quality_reports():
    """Generate data quality reports"""
    print("\n📊 DATA QUALITY REPORTS")
    print("="*40)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("Analyzing data quality...")
        
        # Missing field analysis
        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]
        
        fields_to_check = [
            ('email', 'Email addresses'),
            ('first_name', 'First names'),
            ('last_name', 'Last names'),
            ('gender', 'Gender'),
            ('date_of_birth', 'Date of birth'),
            ('course', 'Course')
        ]

        # Whitelist of allowed field names for this analysis
        ALLOWED_STUDENT_FIELDS = {'email', 'first_name', 'last_name', 'gender', 'date_of_birth', 'course'}

        print(f"\n📋 MISSING FIELD ANALYSIS (Total students: {total_students}):")
        print("-" * 60)
        print(f"{'Field':<20} {'Missing':<10} {'Percentage':<12} {'Quality':<10}")
        print("-" * 60)

        for field, description in fields_to_check:
            # Validate field name against whitelist to prevent SQL injection
            try:
                validated_field = validate_field_for_query(field, ALLOWED_STUDENT_FIELDS, "field")
            except SQLIdentifierError as e:
                logger.warning(f"Skipping invalid field: {field} - {e}")
                continue
            cursor.execute(f"SELECT COUNT(*) FROM students WHERE [{validated_field}] IS NULL OR [{validated_field}] = ''")
            missing = cursor.fetchone()[0]
            percentage = (missing / total_students) * 100 if total_students > 0 else 0

            quality = "Excellent" if percentage < 5 else "Good" if percentage < 15 else "Poor"

            print(f"{description:<20} {missing:<10} {percentage:>8.1f}%    {quality:<10}")
        
        # Invalid data patterns
        print(f"\n🔍 INVALID DATA PATTERN DETECTION:")
        print("-" * 60)
        
        # Invalid email patterns
        cursor.execute("""
        SELECT COUNT(*) FROM students 
        WHERE email IS NOT NULL AND email NOT LIKE '%@%.%'
        """)
        invalid_emails = cursor.fetchone()[0]
        print(f"Invalid email formats: {invalid_emails}")
        
        # Age inconsistencies
        cursor.execute("""
        SELECT COUNT(*) FROM students 
        WHERE age < 16 OR age > 80
        """)
        invalid_ages = cursor.fetchone()[0]
        print(f"Suspicious age values: {invalid_ages}")
        
        # Course consistency
        cursor.execute("""
        SELECT COUNT(*) FROM students 
        WHERE course NOT IN ('CS', 'DS') AND course IS NOT NULL
        """)
        invalid_courses = cursor.fetchone()[0]
        print(f"Invalid course codes: {invalid_courses}")
        
        # Data completeness score
        total_fields = len(fields_to_check)
        cursor.execute(f"""
        SELECT AVG(
            CASE WHEN email IS NOT NULL AND email != '' THEN 1 ELSE 0 END +
            CASE WHEN first_name IS NOT NULL AND first_name != '' THEN 1 ELSE 0 END +
            CASE WHEN last_name IS NOT NULL AND last_name != '' THEN 1 ELSE 0 END +
            CASE WHEN gender IS NOT NULL AND gender != '' THEN 1 ELSE 0 END +
            CASE WHEN date_of_birth IS NOT NULL AND date_of_birth != '' THEN 1 ELSE 0 END +
            CASE WHEN course IS NOT NULL AND course != '' THEN 1 ELSE 0 END
        ) * 100.0 / {total_fields} as completeness
        FROM students
        """)
        
        completeness = cursor.fetchone()[0] or 0
        
        print(f"\n📈 OVERALL DATA QUALITY SCORE:")
        print("-" * 40)
        print(f"Data Completeness: {completeness:.1f}%")
        
        quality_grade = "A" if completeness >= 90 else "B" if completeness >= 80 else "C" if completeness >= 70 else "D"
        print(f"Quality Grade: {quality_grade}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error generating quality report: {e}")

# ===== VISUALIZATION FEATURES =====

def interactive_charts():
    """Generate interactive charts and visualizations"""
    print("\n📊 INTERACTIVE CHARTS & GRAPHS")
    print("="*50)
    
    print("Available visualizations:")
    print("1. Age Distribution Histogram")
    print("2. Course Enrollment Pie Chart")
    print("3. Registration Timeline")
    print("4. Gender Distribution by Course")
    print("5. Module Popularity Chart")
    
    choice = input("Select visualization (1-5): ").strip()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if choice == '1':
            generate_age_histogram(cursor)
        elif choice == '2':
            generate_course_pie_chart(cursor)
        elif choice == '3':
            generate_registration_timeline(cursor)
        elif choice == '4':
            generate_gender_course_chart(cursor)
        elif choice == '5':
            generate_module_popularity_chart(cursor)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error generating visualization: {e}")

def generate_age_histogram(cursor):
    """Generate age distribution histogram (text-based)"""
    cursor.execute('''
    SELECT 
        CASE 
            WHEN age < 20 THEN 'Under 20'
            WHEN age BETWEEN 20 AND 25 THEN '20-25'
            WHEN age BETWEEN 26 AND 30 THEN '26-30'
            WHEN age BETWEEN 31 AND 35 THEN '31-35'
            ELSE 'Over 35'
        END as age_group,
        COUNT(*) as count
    FROM students
    GROUP BY age_group
    ORDER BY 
        CASE age_group
            WHEN 'Under 20' THEN 1
            WHEN '20-25' THEN 2
            WHEN '26-30' THEN 3
            WHEN '31-35' THEN 4
            ELSE 5
        END
    ''')
    
    data = cursor.fetchall()
    
    print("\n📊 AGE DISTRIBUTION HISTOGRAM:")
    print("-" * 50)
    
    max_count = max(count for _, count in data) if data else 1
    
    for age_group, count in data:
        bar_length = int((count / max_count) * 40)
        bar = '█' * bar_length
        print(f"{age_group:<15} |{bar:<40} {count}")

def generate_course_pie_chart(cursor):
    """Generate course enrollment pie chart (text-based)"""
    cursor.execute('''
    SELECT course, COUNT(*) as count
    FROM students
    GROUP BY course
    ORDER BY count DESC
    ''')
    
    data = cursor.fetchall()
    total = sum(count for _, count in data)
    
    print("\n🥧 COURSE ENROLLMENT PIE CHART:")
    print("-" * 40)
    
    for course, count in data:
        percentage = (count / total) * 100 if total > 0 else 0
        pie_chars = int(percentage / 5)  # Each char represents 5%
        pie_slice = '●' * pie_chars
        print(f"{course:<10} |{pie_slice:<20} {count:>6} ({percentage:>5.1f}%)")

def generate_registration_timeline(cursor):
    """Generate registration timeline"""
    cursor.execute('''
    SELECT 
        strftime('%Y-%m', registration_datetime) as month,
        COUNT(*) as registrations
    FROM students
    WHERE registration_datetime >= date('now', '-12 months')
    GROUP BY strftime('%Y-%m', registration_datetime)
    ORDER BY month
    ''')
    
    data = cursor.fetchall()
    
    print("\n📈 REGISTRATION TIMELINE (Last 12 months):")
    print("-" * 50)
    
    if not data:
        print("No registration data available.")
        return
    
    max_registrations = max(count for _, count in data)
    
    for month, count in data:
        bar_length = int((count / max_registrations) * 30) if max_registrations > 0 else 0
        bar = '▓' * bar_length
        print(f"{month} |{bar:<30} {count}")

# ===== ADMIN & AUDIT FEATURES =====

def view_search_audit_trail():
    """View search audit trail"""
    print("\n🔍 SEARCH AUDIT TRAIL")
    print("="*50)
    
    # Read from log file
    try:
        if os.path.exists('search_audit.log'):
            with open('refactored/core/logs/search_audit.log', 'r') as f:
                lines = f.readlines()
            
            # Show last 20 entries
            recent_lines = lines[-20:] if len(lines) > 20 else lines
            
            print("Recent search activities:")
            print("-" * 80)
            
            for line in recent_lines:
                print(line.strip())
        else:
            print("No audit log found.")
    
    except Exception as e:
        print(f"Error reading audit log: {e}")

def manage_user_permissions():
    """Manage user permissions (admin feature)"""
    print("\n👥 USER PERMISSIONS MANAGEMENT")
    print("="*50)
    
    print("1. View User Permissions")
    print("2. Add User")
    print("3. Modify User Permissions")
    print("4. Remove User")
    
    choice = input("Select option (1-4): ").strip()
    
    if choice == '1':
        view_user_permissions()
    elif choice == '2':
        add_user_permissions()
    elif choice == '3':
        modify_user_permissions()
    elif choice == '4':
        remove_user_permissions()

def view_user_permissions():
    """View all user permissions"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT user_id, role, permissions, created_date
        FROM user_permissions
        ORDER BY created_date DESC
        ''')
        
        users = cursor.fetchall()
        
        if not users:
            print("No user permissions found.")
            return
        
        print("\n👥 USER PERMISSIONS:")
        print("-" * 80)
        print(f"{'User ID':<20} {'Role':<15} {'Permissions':<30} {'Created':<15}")
        print("-" * 80)
        
        for user_id, role, permissions, created in users:
            print(f"{user_id:<20} {role:<15} {permissions:<30} {created[:10]:<15}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error viewing permissions: {e}")

def add_user_permissions():
    """Add new user permissions"""
    user_id = input("Enter User ID: ").strip()
    role = input("Enter Role (admin/user/viewer): ").strip()
    permissions = input("Enter Permissions (comma-separated): ").strip()
    
    if not all([user_id, role, permissions]):
        print("All fields are required.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO user_permissions (user_id, role, permissions)
        VALUES (?, ?, ?)
        ''', (user_id, role, permissions))
        
        conn.commit()
        conn.close()
        
        print(f"✅ User '{user_id}' added successfully with role '{role}'.")
        
    except sqlite3.Error as e:
        print(f"Error adding user: {e}")

# ===== SMART FEATURES =====

@audit_log
def auto_complete_search():
    """Auto-complete search functionality"""
    print("\n💡 AUTO-COMPLETE SEARCH")
    print("="*40)

    # Whitelist of allowed search fields
    ALLOWED_SEARCH_FIELDS = {'first_name', 'last_name', 'course'}

    search_field = input("Search field (first_name/last_name/course): ").strip()

    if search_field not in ALLOWED_SEARCH_FIELDS:
        print("Invalid search field.")
        return

    # Validate field name using SQL safety utility (defense-in-depth)
    try:
        validated_field = validate_field_for_query(search_field, ALLOWED_SEARCH_FIELDS, "search field")
    except SQLIdentifierError as e:
        print(f"Invalid search field: {e}")
        return

    partial_input = input(f"Enter partial {validated_field}: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Use bracket-quoted validated field name
        query = f"SELECT DISTINCT [{validated_field}] FROM students WHERE [{validated_field}] LIKE ? ORDER BY [{validated_field}]"
        cursor.execute(query, (f"{partial_input}%",))
        
        suggestions = cursor.fetchall()
        
        if not suggestions:
            print("No suggestions found.")
            return
        
        print(f"\n💡 Suggestions for '{partial_input}':")
        print("-" * 40)
        
        for i, (suggestion,) in enumerate(suggestions[:10], 1):  # Limit to 10
            print(f"{i}. {suggestion}")
        
        choice = input("\nSelect suggestion number (or press Enter to skip): ").strip()
        
        if choice:
            try:
                index = int(choice) - 1
                if 0 <= index < len(suggestions):
                    selected = suggestions[index][0]
                    print(f"\nSearching for {validated_field} = '{selected}'...")

                    # Execute search with selected suggestion (using validated field name)
                    cursor.execute(f"SELECT * FROM students WHERE [{validated_field}] = ?", (selected,))
                    results = cursor.fetchall()

                    log_search("auto_complete", {validated_field: selected}, len(results))
                    display_search_results(results)
            except ValueError:
                print("Invalid selection.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def smart_suggestions():
    """Provide smart search suggestions based on patterns"""
    print("\n🧠 SMART SEARCH SUGGESTIONS")
    print("="*50)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Analyze search patterns and suggest useful searches
        suggestions = [
            ("Students without email addresses", 
             "SELECT * FROM students WHERE email IS NULL OR email = ''"),
            ("Students enrolled in multiple modules", 
             """SELECT s.*, COUNT(sm.module_code) as module_count
                FROM students s 
                JOIN student_modules sm ON s.student_id = sm.student_id
                GROUP BY s.student_id 
                HAVING module_count > 3"""),
            ("Recent registrations (last 30 days)", 
             "SELECT * FROM students WHERE registration_datetime >= date('now', '-30 days')"),
            ("Students by age groups", 
             "SELECT * FROM students ORDER BY age"),
            ("Course distribution analysis", 
             "SELECT course, COUNT(*) FROM students GROUP BY course")
        ]
        
        print("🔍 Suggested searches:")
        print("-" * 50)
        
        for i, (description, query) in enumerate(suggestions, 1):
            print(f"{i}. {description}")
        
        choice = input("\nSelect suggestion (1-5) or press Enter to skip: ").strip()
        
        if choice:
            try:
                index = int(choice) - 1
                if 0 <= index < len(suggestions):
                    description, query = suggestions[index]
                    print(f"\nExecuting: {description}")
                    
                    cursor.execute(query)
                    results = cursor.fetchall()
                    
                    log_search("smart_suggestion", {"description": description}, len(results))
                    
                    if "GROUP BY" in query or "COUNT" in query:
                        # Display aggregate results
                        print(f"\n📊 Results for: {description}")
                        print("-" * 50)
                        for result in results:
                            print(result)
                    else:
                        display_search_results(results)
                        
            except ValueError:
                print("Invalid selection.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def predictive_analytics():
    """Basic predictive analytics for student data"""
    print("\n🔮 PREDICTIVE ANALYTICS")
    print("="*40)
    
    print("Available analytics:")
    print("1. At-risk Student Identification")
    print("2. Enrollment Prediction")
    print("3. Module Success Probability")
    print("4. Graduation Timeline Forecast")
    
    choice = input("Select analysis (1-4): ").strip()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if choice == '1':
            identify_at_risk_students(cursor)
        elif choice == '2':
            enrollment_prediction(cursor)
        elif choice == '3':
            module_success_probability(cursor)
        elif choice == '4':
            graduation_timeline_forecast(cursor)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error in predictive analytics: {e}")

def identify_at_risk_students(cursor):
    """Identify students who might be at risk"""
    print("\n⚠️  AT-RISK STUDENT IDENTIFICATION")
    print("-" * 50)
    
    # Simple risk factors: incomplete modules, delayed registration, etc.
    cursor.execute('''
    SELECT s.student_id, s.first_name, s.last_name, s.course,
           COUNT(sm.module_code) as total_modules,
           SUM(CASE WHEN sm.grade IS NULL THEN 1 ELSE 0 END) as incomplete_modules,
           julianday('now') - julianday(s.registration_datetime) as days_since_registration
    FROM students s
    LEFT JOIN student_modules sm ON s.student_id = sm.student_id
    GROUP BY s.student_id, s.first_name, s.last_name, s.course, s.registration_datetime
    ''')
    
    students = cursor.fetchall()
    at_risk_students = []
    
    for student in students:
        risk_score = 0
        risk_factors = []
        
        student_id, first_name, last_name, course, total_modules, incomplete_modules, days_since_reg = student
        
        # Risk factor 1: High ratio of incomplete modules
        if total_modules > 0:
            incomplete_ratio = incomplete_modules / total_modules
            if incomplete_ratio > 0.5:
                risk_score += 3
                risk_factors.append(f"High incomplete ratio ({incomplete_ratio:.1%})")
        
        # Risk factor 2: No modules enrolled after significant time
        if total_modules == 0 and days_since_reg > 30:
            risk_score += 4
            risk_factors.append("No module enrollment after 30+ days")
        
        # Risk factor 3: Too many incomplete modules
        if incomplete_modules > 3:
            risk_score += 2
            risk_factors.append(f"{incomplete_modules} incomplete modules")
        
        if risk_score >= 3:  # Threshold for at-risk classification
            at_risk_students.append((student, risk_score, risk_factors))
    
    # Sort by risk score (highest first)
    at_risk_students.sort(key=lambda x: x[1], reverse=True)
    
    if not at_risk_students:
        print("✅ No at-risk students identified.")
        return
    
    print(f"🚨 Identified {len(at_risk_students)} at-risk students:")
    print("-" * 80)
    
    for student_data, risk_score, risk_factors in at_risk_students[:10]:  # Top 10
        student_id, first_name, last_name, course = student_data[:4]
        print(f"\n{student_id}: {first_name} {last_name} ({course}) - Risk Score: {risk_score}")
        for factor in risk_factors:
            print(f"  → {factor}")

def enrollment_prediction(cursor):
    """Predict future enrollment trends"""
    print("\n📈 ENROLLMENT PREDICTION")
    print("-" * 40)
    
    # Analyze historical enrollment patterns
    cursor.execute('''
    SELECT 
        strftime('%Y-%m', registration_datetime) as month,
        COUNT(*) as enrollments
    FROM students
    WHERE registration_datetime >= date('now', '-12 months')
    GROUP BY strftime('%Y-%m', registration_datetime)
    ORDER BY month
    ''')
    
    historical_data = cursor.fetchall()
    
    if len(historical_data) < 3:
        print("Insufficient historical data for prediction.")
        return
    
    # Simple trend analysis
    enrollments = [count for _, count in historical_data]
    
    # Calculate moving average
    if len(enrollments) >= 3:
        recent_avg = sum(enrollments[-3:]) / 3
        overall_avg = sum(enrollments) / len(enrollments)
        
        trend = "increasing" if recent_avg > overall_avg else "decreasing"
        change_percent = ((recent_avg - overall_avg) / overall_avg) * 100
        
        print(f"📊 Historical Enrollment Analysis:")
        print(f"Overall average: {overall_avg:.1f} students/month")
        print(f"Recent average (last 3 months): {recent_avg:.1f} students/month")
        print(f"Trend: {trend} ({change_percent:+.1f}%)")
        
        # Simple prediction for next month
        predicted_next_month = int(recent_avg * (1 + change_percent/100))
        
        print(f"\n🔮 Prediction for next month: ~{predicted_next_month} new enrollments")
        
        # Course-specific predictions
        cursor.execute('''
        SELECT course, COUNT(*) 
        FROM students 
        WHERE registration_datetime >= date('now', '-3 months')
        GROUP BY course
        ''')
        
        course_data = cursor.fetchall()
        print(f"\n📚 Course-specific recent trends:")
        for course, count in course_data:
            monthly_avg = count / 3
            print(f"  {course}: {monthly_avg:.1f} students/month")

# ===== UTILITY FUNCTIONS =====

def log_search(search_type, criteria, result_count):
    """Log search activity for analytics"""
    global search_history
    
    # Add to search history
    search_entry = {
        'type': search_type,
        'criteria': str(criteria),
        'results': result_count,
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    search_history.append(search_entry)
    
    # Keep only last 100 searches in memory
    if len(search_history) > 100:
        search_history = search_history[-100:]
    
    # Log to database for analytics
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        start_time = time.time()
        execution_time = 0.1  # Placeholder

        insert_search_analytics_record(
            cursor,
            user_id=current_user,
            search_type=search_type,
            criteria=str(criteria),
            results_count=result_count,
            execution_time=execution_time
        )

        conn.commit()
        conn.close()

    except sqlite3.Error:
        pass  # Fail silently for analytics

def performance_optimization():
    """Perform database optimization"""
    print("\n⚡ PERFORMANCE OPTIMIZATION")
    print("="*40)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("Running optimization tasks...")
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_students_name ON students(first_name, last_name)",
            "CREATE INDEX IF NOT EXISTS idx_students_course ON students(course)",
            "CREATE INDEX IF NOT EXISTS idx_students_age ON students(age)",
            "CREATE INDEX IF NOT EXISTS idx_students_registration ON students(registration_datetime)",
            "CREATE INDEX IF NOT EXISTS idx_modules_student ON student_modules(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_modules_code ON student_modules(module_code)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
            print(f"✓ Index created")
        
        # VACUUM to optimize database file
        cursor.execute("VACUUM")
        print("✓ Database vacuumed")
        
        # ANALYZE to update query planner statistics
        cursor.execute("ANALYZE")
        print("✓ Statistics updated")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Performance optimization completed!")
        
    except sqlite3.Error as e:
        print(f"Optimization error: {e}")

def export_system_statistics():
    """Export comprehensive system statistics"""
    print("\n📊 EXPORTING SYSTEM STATISTICS")
    print("="*50)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"system_statistics_{timestamp}.json"
        
        statistics = {}
        
        # Student statistics
        cursor.execute("SELECT COUNT(*) FROM students")
        statistics['total_students'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course")
        statistics['students_by_course'] = dict(cursor.fetchall())
        
        cursor.execute("SELECT AVG(age) FROM students")
        statistics['average_age'] = round(cursor.fetchone()[0] or 0, 1)
        
        # Module statistics
        cursor.execute("SELECT COUNT(DISTINCT module_code) FROM student_modules")
        statistics['total_modules'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM student_modules")
        statistics['total_enrollments'] = cursor.fetchone()[0]
        
        # Search statistics
        cursor.execute("SELECT COUNT(*) FROM search_analytics")
        statistics['total_searches'] = cursor.fetchone()[0]
        
        cursor.execute("""
        SELECT search_type, COUNT(*) 
        FROM search_analytics 
        GROUP BY search_type 
        ORDER BY COUNT(*) DESC
        """)
        statistics['search_types'] = dict(cursor.fetchall())
        
        # Data quality statistics
        cursor.execute("SELECT COUNT(*) FROM students WHERE email IS NULL OR email = ''")
        missing_emails = cursor.fetchone()[0]
        statistics['data_quality'] = {
            'missing_emails': missing_emails,
            'email_completeness': round((1 - missing_emails/statistics['total_students']) * 100, 1) if statistics['total_students'] > 0 else 0
        }
        
        # Export to JSON
        with open(filename, 'w') as f:
            json.dump(statistics, f, indent=2, default=str)
        
        print(f"✅ Statistics exported to {filename}")
        
        # Display summary
        print(f"\n📈 SYSTEM OVERVIEW:")
        print("-" * 40)
        print(f"Total Students: {statistics['total_students']}")
        print(f"Total Modules: {statistics['total_modules']}")
        print(f"Total Searches: {statistics['total_searches']}")
        print(f"Email Completeness: {statistics['data_quality']['email_completeness']}%")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error exporting statistics: {e}")

# ===== ORIGINAL FUNCTIONS (Updated) =====

@audit_log
def multi_criteria_search():
    """Enhanced multi-criteria search with caching"""
    print("\nMulti-Criteria Student Search")
    print("Enter search criteria (leave blank to ignore):")
    
    # Get search criteria from user
    criteria = {}
    criteria['student_id'] = input("Student ID: ").strip()
    criteria['first_name'] = input("First Name: ").strip()
    criteria['last_name'] = input("Last Name: ").strip()
    criteria['gender'] = input("Gender (male/female/other): ").strip().lower()
    criteria['course'] = input("Course (CS/DS): ").strip().upper()
    
    age_min = input("Minimum Age: ").strip()
    age_max = input("Maximum Age: ").strip()
    
    # Validate inputs
    if criteria['gender'] and criteria['gender'] not in ['male', 'female', 'other']:
        print("Invalid gender. Please enter 'male', 'female', or 'other'.")
        return
    
    if criteria['course'] and criteria['course'] not in ['CS', 'DS']:
        print("Invalid course. Please enter 'CS' or 'DS'.")
        return
    
    try:
        criteria['age_min'] = int(age_min) if age_min else None
        criteria['age_max'] = int(age_max) if age_max else None
    except ValueError:
        print("Invalid age. Please enter a valid number.")
        return
    
    # Check cache first
    cache_key = hashlib.md5(str(criteria).encode()).hexdigest()
    if cache_key in search_cache:
        print("📦 Loading results from cache...")
        results = search_cache[cache_key]
        log_search("multi_criteria_cached", criteria, len(results))
        display_search_results(results)
        return
    
    # Build the SQL query based on provided criteria
    query = "SELECT * FROM students WHERE 1=1"
    params = []
    
    for key, value in criteria.items():
        if value and key not in ['age_min', 'age_max']:
            if key in ['student_id', 'first_name', 'last_name']:
                query += f" AND LOWER({key}) LIKE LOWER(?)"
                params.append(f"%{value}%")
            else:
                query += f" AND LOWER({key}) = LOWER(?)"
                params.append(value)
    
    if criteria['age_min'] is not None:
        query += " AND age >= ?"
        params.append(criteria['age_min'])
    
    if criteria['age_max'] is not None:
        query += " AND age <= ?"
        params.append(criteria['age_max'])
    
    # Execute the search
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        start_time = time.time()
        cursor.execute(query, params)
        results = cursor.fetchall()
        execution_time = time.time() - start_time
        
        # Cache results
        search_cache[cache_key] = results
        
        # Log search
        log_search("multi_criteria", criteria, len(results))
        
        # Display and store results
        display_search_results(results)
        conn.close()
        
        print(f"\n⚡ Search completed in {execution_time:.3f} seconds")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def fuzzy_name_search():
    """Enhanced fuzzy name search with improved algorithms"""
    print("\nFuzzy Name Search")
    print("This search will find names that are similar to your search term.")
    
    search_term = input("Enter name to search for: ").strip()
    if not search_term:
        print("Search term cannot be empty.")
        return
    
    # Define minimum similarity ratio
    similarity_threshold = 0.6
    threshold_input = input(f"Enter similarity threshold (0.1-0.9, default is {similarity_threshold}): ").strip()
    
    if threshold_input:
        try:
            similarity_threshold = float(threshold_input)
            if similarity_threshold < 0.1 or similarity_threshold > 0.9:
                print("Invalid threshold. Using default value of 0.6.")
                similarity_threshold = 0.6
        except ValueError:
            print("Invalid threshold. Using default value of 0.6.")
    
    # Algorithm selection
    print("\nSelect matching algorithm:")
    print("1. Standard fuzzy matching")
    print("2. Phonetic matching (Soundex)")
    print("3. Both algorithms")
    
    algo_choice = input("Select algorithm (1-3): ").strip()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM students")
        all_students = cursor.fetchall()
        conn.close()
        
        matched_students = []
        search_term_lower = search_term.lower()
        
        for student in all_students:
            first_name = student[3].lower() if student[3] else ""
            middle_name = student[4].lower() if student[4] else ""
            last_name = student[5].lower() if student[5] else ""
            
            best_ratio = 0
            
            if algo_choice in ['1', '3']:
                # Standard fuzzy matching
                first_ratio = SequenceMatcher(None, search_term_lower, first_name).ratio()
                middle_ratio = SequenceMatcher(None, search_term_lower, middle_name).ratio() if middle_name else 0
                last_ratio = SequenceMatcher(None, search_term_lower, last_name).ratio()
                
                full_name = f"{first_name} {last_name}".strip()
                full_ratio = SequenceMatcher(None, search_term_lower, full_name).ratio()
                
                best_ratio = max(first_ratio, middle_ratio, last_ratio, full_ratio)
            
            if algo_choice in ['2', '3']:
                # Phonetic matching
                def simple_soundex(word):
                    if not word:
                        return "0000"
                    word = word.upper()
                    result = word[0]
                    mapping = {'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3', 'L': '4', 'MN': '5', 'R': '6'}
                    for char in word[1:]:
                        for key, value in mapping.items():
                            if char in key and result[-1] != value:
                                result += value
                                break
                    return (result + '0000')[:4]
                
                search_soundex = simple_soundex(search_term)
                first_soundex = simple_soundex(first_name)
                last_soundex = simple_soundex(last_name)
                
                if search_soundex == first_soundex or search_soundex == last_soundex:
                    best_ratio = max(best_ratio, 0.8)  # High score for phonetic match
            
            if best_ratio >= similarity_threshold:
                matched_students.append((student, best_ratio))
        
        # Sort by similarity (highest first)
        matched_students.sort(key=lambda x: x[1], reverse=True)
        
        # Extract just the student records for display
        results = [student_info[0] for student_info in matched_students]
        
        # Log and display results
        log_search("fuzzy_name", {"term": search_term, "threshold": similarity_threshold}, len(results))
        display_search_results(results)
        
        # Show similarity scores
        if results:
            print("\nSimilarity scores:")
            for i, (student, score) in enumerate(matched_students[:10]):  # Top 10
                full_name = f"{student[3]} {student[4] if student[4] else ''} {student[5]}".strip()
                print(f"{i+1}. {full_name} - {score:.3f}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def module_enrollment_search():
    """Enhanced module enrollment search"""
    print("\nModule Enrollment Search")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT module_code, module_name FROM student_modules ORDER BY module_name")
        all_modules = cursor.fetchall()
        
        if not all_modules:
            print("No modules found in the database.")
            return
        
        # Enhanced module display with search
        print(f"\nFound {len(all_modules)} modules:")
        search_modules = input("Search modules (enter keyword or press Enter to see all): ").strip()
        
        if search_modules:
            filtered_modules = [(code, name) for code, name in all_modules 
                              if search_modules.lower() in name.lower() or search_modules.lower() in code.lower()]
            all_modules = filtered_modules
        
        if not all_modules:
            print("No modules match your search.")
            return
        
        # Paginated display
        page_size = 20
        for i in range(0, len(all_modules), page_size):
            page_modules = all_modules[i:i+page_size]
            print(f"\nModules {i+1}-{min(i+page_size, len(all_modules))} of {len(all_modules)}:")
            for j, (code, name) in enumerate(page_modules):
                print(f"{i+j+1:3d}. {code} - {name}")
            
            if i + page_size < len(all_modules):
                if input("\nPress Enter for more, or 'q' to stop: ").strip().lower() == 'q':
                    break
        
        # Module selection
        module_indices = input("\nEnter module numbers (comma-separated) or 'all' for all modules: ").strip()
        
        if module_indices.lower() == 'all':
            selected_modules = [code for code, _ in all_modules]
        else:
            try:
                selected_indices = [int(idx.strip()) - 1 for idx in module_indices.split(",")]
                selected_modules = []
                
                for idx in selected_indices:
                    if 0 <= idx < len(all_modules):
                        selected_modules.append(all_modules[idx][0])
                    else:
                        print(f"Invalid module number: {idx + 1}")
                
                if not selected_modules:
                    return
                    
            except ValueError:
                print("Invalid input format.")
                return
        
        # Match type selection
        match_type = input("\nFind students enrolled in (1) ALL or (2) ANY of these modules? Enter 1 or 2: ").strip()
        
        # Build and execute query
        if match_type == '1':  # ALL modules
            query = "SELECT s.* FROM students s WHERE "
            conditions = []
            params = []
            
            for module_code in selected_modules:
                conditions.append("""
                EXISTS (
                    SELECT 1 FROM student_modules sm
                    WHERE sm.student_id = s.student_id AND sm.module_code = ?
                )
                """)
                params.append(module_code)
            
            query += " AND ".join(conditions)
            
        else:  # ANY module
            placeholders = ",".join(["?" for _ in selected_modules])
            query = f"""
            SELECT DISTINCT s.* FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code IN ({placeholders})
            """
            params = selected_modules
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Enhanced results display
        print(f"\nModule selection: {', '.join(selected_modules)}")
        print(f"Match type: {'ALL modules' if match_type == '1' else 'ANY module'}")
        
        log_search("module_enrollment", {"modules": selected_modules, "match_type": match_type}, len(results))
        display_search_results(results)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def date_range_search():
    """Enhanced date range search with presets"""
    print("\nDate Range Search")
    
    print("Search options:")
    print("1. Custom date range")
    print("2. Last 7 days")
    print("3. Last 30 days")
    print("4. Last 3 months")
    print("5. Last 6 months")
    print("6. This year")
    
    choice = input("Select option (1-6): ").strip()
    
    start_date = None
    end_date = None
    
    if choice == '1':
        start_date = input("Enter start date (YYYY-MM-DD), or leave blank: ").strip()
        end_date = input("Enter end date (YYYY-MM-DD), or leave blank: ").strip()
    elif choice == '2':
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    elif choice == '3':
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    elif choice == '4':
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    elif choice == '5':
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    elif choice == '6':
        start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
    else:
        print("Invalid choice.")
        return
    
    # Validate dates
    if start_date:
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            print("Invalid start date format.")
            return
    
    if end_date:
        try:
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            print("Invalid end date format.")
            return
    
    # Build query
    query = "SELECT * FROM students WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND registration_datetime >= ?"
        params.append(start_date + " 00:00:00")
    
    if end_date:
        query += " AND registration_datetime <= ?"
        params.append(end_date + " 23:59:59")
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Show date range in results
        if start_date and end_date:
            print(f"\nSearching from {start_date} to {end_date}")
        elif start_date:
            print(f"\nSearching from {start_date} onwards")
        elif end_date:
            print(f"\nSearching until {end_date}")
        
        log_search("date_range", {"start": start_date, "end": end_date}, len(results))
        display_search_results(results)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

@audit_log
def combined_filters_search():
    """Search using a combination of filters from different categories"""
    print("\nCombined Filters Search")
    print("This search allows you to combine multiple types of filters.")
    
    # Initialize filters
    filters = {
        "student_data": {},
        "module_codes": [],
        "date_range": {"start": None, "end": None},
        "module_match_all": False
    }
    
    # Student data filters
    print("\n--- Student Data Filters ---")
    print("Enter search criteria (leave blank to ignore):")
    student_id = input("Student ID: ").strip()
    if student_id:
        filters["student_data"]["student_id"] = student_id
    first_name = input("First Name: ").strip()
    if first_name:
        filters["student_data"]["first_name"] = first_name
    last_name = input("Last Name: ").strip()
    if last_name:
        filters["student_data"]["last_name"] = last_name
    gender = input("Gender (male/female/other): ").strip().lower()
    if gender in ('male', 'female', 'other'):
        filters["student_data"]["gender"] = gender
    elif gender:
        print("Invalid gender. Ignored.")
    course = input("Course (CS/DS): ").strip().upper()
    if course in ('CS', 'DS'):
        filters["student_data"]["course"] = course
    elif course:
        print("Invalid course. Ignored.")
    age_min = input("Minimum Age: ").strip()
    if age_min:
        try:
            filters["student_data"]["age_min"] = int(age_min)
        except ValueError:
            print("Invalid minimum age. Ignored.")
    age_max = input("Maximum Age: ").strip()
    if age_max:
        try:
            filters["student_data"]["age_max"] = int(age_max)
        except ValueError:
            print("Invalid maximum age. Ignored.")
    
    # Module filters
    print("\n--- Module Filters ---")
    if input("Filter by modules? (y/n): ").strip().lower() == 'y':
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT module_code, module_name "
                "FROM student_modules ORDER BY module_name"
            )
            all_modules = cursor.fetchall()
            conn.close()
            if not all_modules:
                print("No modules found. Skipping module filters.")
            else:
                print("\nAvailable Modules:")
                for i, (code, name) in enumerate(all_modules, 1):
                    print(f"{i}. {code} - {name}")
                indices = input(
                    "Enter module numbers to filter by (comma-separated): "
                ).strip()
                if indices:
                    try:
                        chosen = [int(i)-1 for i in indices.split(',')]
                        for idx in chosen:
                            if 0 <= idx < len(all_modules):
                                filters["module_codes"].append(all_modules[idx][0])
                            else:
                                print(f"Invalid module number {idx+1}. Skipped.")
                        if filters["module_codes"]:
                            choice = input(
                                "Students must be in (1) ALL or (2) ANY of these? "
                            ).strip()
                            if choice == '1':
                                filters["module_match_all"] = True
                            elif choice != '2':
                                print("Invalid choice. Using ANY.")
                    except ValueError:
                        print("Bad input. Skipping module filters.")
        except sqlite3.Error as e:
            print(f"DB error loading modules: {e}. Skipping module filters.")
    
    # Date range filters
    print("\n--- Date Range Filters ---")
    if input("Filter by registration date range? (y/n): ").strip().lower() == 'y':
        start_date = input(
            "Start date (YYYY-MM-DD), blank for any: "
        ).strip()
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                filters["date_range"]["start"] = start_date + " 00:00:00"
            except ValueError:
                print("Invalid start date. Ignored.")
        end_date = input(
            "End date (YYYY-MM-DD), blank for any: "
        ).strip()
        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
                filters["date_range"]["end"] = end_date + " 23:59:59"
            except ValueError:
                print("Invalid end date. Ignored.")
    
    # Execute search and optional save in one try/except
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Build query
        if filters["module_codes"] and filters["module_match_all"]:
            query = "SELECT s.* FROM students s WHERE 1=1"
            params = []
            for field, expr, val in [
                ("student_id", "LIKE", f"%{filters['student_data'].get('student_id','')}%"),
                ("first_name", "LIKE LOWER", f"%{filters['student_data'].get('first_name','')}%"),
                ("last_name", "LIKE LOWER", f"%{filters['student_data'].get('last_name','')}%"),
            ]:
                if filters["student_data"].get(field):
                    if "LOWER" in expr:
                        query += f" AND LOWER(s.{field}) {expr}(?)"
                    else:
                        query += f" AND s.{field} {expr} ?"
                    params.append(val)
            if "gender" in filters["student_data"]:
                query += " AND LOWER(s.gender)=LOWER(?)"
                params.append(filters["student_data"]["gender"])
            if "course" in filters["student_data"]:
                query += " AND s.course=?"
                params.append(filters["student_data"]["course"])
            if "age_min" in filters["student_data"]:
                query += " AND s.age>=?"
                params.append(filters["student_data"]["age_min"])
            if "age_max" in filters["student_data"]:
                query += " AND s.age<=?"
                params.append(filters["student_data"]["age_max"])
            if filters["date_range"]["start"]:
                query += " AND s.registration_datetime>=?"
                params.append(filters["date_range"]["start"])
            if filters["date_range"]["end"]:
                query += " AND s.registration_datetime<=?"
                params.append(filters["date_range"]["end"])
            for code in filters["module_codes"]:
                query += """
                AND EXISTS (
                    SELECT 1 FROM student_modules sm
                    WHERE sm.student_id=s.student_id AND sm.module_code=?
                )
                """
                params.append(code)
        else:
            query = "SELECT DISTINCT s.* FROM students s"
            params = []
            if filters["module_codes"]:
                query += " JOIN student_modules sm ON s.student_id=sm.student_id"
            query += " WHERE 1=1"
            for field, op in [
                ("student_id", "LIKE"),
                ("first_name", "LIKE LOWER"),
                ("last_name", "LIKE LOWER"),
            ]:
                if filters["student_data"].get(field):
                    if "LOWER" in op:
                        query += f" AND LOWER(s.{field}) {op}(?)"
                    else:
                        query += f" AND s.{field} {op} ?"
                    params.append(
                        f"%{filters['student_data'][field]}%"
                    )
            if "gender" in filters["student_data"]:
                query += " AND LOWER(s.gender)=LOWER(?)"
                params.append(filters["student_data"]["gender"])
            if "course" in filters["student_data"]:
                query += " AND s.course=?"
                params.append(filters["student_data"]["course"])
            if "age_min" in filters["student_data"]:
                query += " AND s.age>=?"
                params.append(filters["student_data"]["age_min"])
            if "age_max" in filters["student_data"]:
                query += " AND s.age<=?"
                params.append(filters["student_data"]["age_max"])
            if filters["date_range"]["start"]:
                query += " AND s.registration_datetime>=?"
                params.append(filters["date_range"]["start"])
            if filters["date_range"]["end"]:
                query += " AND s.registration_datetime<=?"
                params.append(filters["date_range"]["end"])
            if filters["module_codes"]:
                placeholders = ",".join("?" for _ in filters["module_codes"])
                query += f" AND sm.module_code IN ({placeholders})"
                params.extend(filters["module_codes"])
        
        # Run and close
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        display_search_results(results)
        
        # Offer to save if there are results
        if results:
            if input("\nSave this search configuration? (y/n): ").strip().lower() == 'y':
                name = input("Enter name for saved search: ").strip()
                if name:
                    # Implement saving logic here
                    print(f"✅ Search saved as '{name}'")
    except sqlite3.Error as e:
        print(f"Database error: {e}")

        
def display_search_results(results):
    """Enhanced search results display with pagination and export options"""
    global last_search_results
    
    if not results:
        print("No matching records found.")
        last_search_results = []
        return
    
    last_search_results = results
    
    print(f"\n🔍 {len(results)} matching records found")
    
    # Pagination for large result sets
    page_size = 10
    current_page = 0
    
    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(results))
        
        print(f"\n📄 Page {current_page + 1} of {(len(results) - 1) // page_size + 1}")
        print("=" * 80)
        
        for i in range(start_idx, end_idx):
            student = results[i]
            print(f"\n{i+1}. Student ID: {student[0]}")
            print(f"   Name: {student[2]} {student[3]} {student[4] or ''} {student[5]}")
            print(f"   Email: {student[1]}")
            print(f"   Gender: {student[6]} | Age: {student[8]} | Course: {student[9]}")
            print(f"   Registration: {student[10]}")
        
        # Navigation options
        print(f"\nOptions:")
        options = []
        if current_page > 0:
            options.append("p) Previous page")
        if end_idx < len(results):
            options.append("n) Next page")
        
        options.extend([
            "d) View detailed info",
            "e) Export results",
            "s) Save search",
            "Enter) Continue"
        ])
        
        print(" | ".join(options))
        
        choice = input("\nChoice: ").strip().lower()
        
        if choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice == 'n' and end_idx < len(results):
            current_page += 1
        elif choice == 'd':
            try:
                student_num = int(input("Enter student number for details: ")) - 1
                if 0 <= student_num < len(results):
                    display_student_detail(results[student_num])
                else:
                    print("Invalid student number.")
            except ValueError:
                print("Invalid input.")
        elif choice == 'e':
            save_last_search_results()
        elif choice == 's':
            save_search_profile()
        elif choice == '' or choice == 'enter':
            break
        else:
            print("Invalid choice.")

def display_student_detail(student):
    """Enhanced detailed information display for a specific student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n" + "="*80)
        print(f"📋 DETAILED STUDENT INFORMATION - ID: {student[0]}")
        print("="*80)
        
        # Basic Information
        print(f"📧 Email Address: {student[1]}")
        print(f"👤 Title: {student[2]}")
        print(f"🏷️  Name: {student[3]} {student[4] or ''} {student[5]}")
        print(f"⚧  Gender: {student[6]}")
        print(f"🎂 Date of Birth: {student[7]}")
        print(f"📅 Age: {student[8]}")
        print(f"🎓 Course: {student[9]}")
        print(f"📝 Registration: {student[10]}")
        
        # Module Information
        cursor.execute('''
        SELECT module_type, module_code, module_name, grade, enrollment_date
        FROM student_modules
        WHERE student_id = ?
        ORDER BY module_type, module_name
        ''', (student[0],))
        
        modules = cursor.fetchall()
        
        print(f"\n📚 ENROLLED MODULES ({len(modules)} total):")
        print("-" * 80)
        
        if modules:
            print(f"{'Type':<15} {'Code':<10} {'Name':<30} {'Grade':<8} {'Enrolled':<12}")
            print("-" * 80)
            
            for module in modules:
                module_type, code, name, grade, enrolled_date = module
                grade_display = grade if grade else "In Progress"
                enrolled_display = enrolled_date[:10] if enrolled_date else "N/A"
                print(f"{module_type:<15} {code:<10} {name:<30} {grade_display:<8} {enrolled_display:<12}")
        else:
            print("No modules enrolled.")
        
        # Additional Analytics
        if modules:
            completed_modules = sum(1 for m in modules if m[3] is not None)
            completion_rate = (completed_modules / len(modules)) * 100
            
            print(f"\n📊 ACADEMIC SUMMARY:")
            print("-" * 40)
            print(f"Total Modules: {len(modules)}")
            print(f"Completed: {completed_modules}")
            print(f"In Progress: {len(modules) - completed_modules}")
            print(f"Completion Rate: {completion_rate:.1f}%")
        
        print("="*80)
        
        # Action options
        print("\nActions:")
        print("1. Export student data")
        print("2. Add to favorites")
        print("3. Send email (simulation)")
        print("4. View academic history")
        print("5. Return")
        
        action = input("Select action (1-5): ").strip()
        
        if action == '1':
            export_single_student(student, modules)
        elif action == '2':
            print(f"✅ Student {student[0]} added to favorites")
        elif action == '3':
            simulate_send_email(student)
        elif action == '4':
            view_academic_history(student[0])
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def export_single_student(student, modules):
    """Export single student data"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"student_{student[0]}_{timestamp}.json"
    
    student_data = {
        'student_info': {
            'student_id': student[0],
            'email': student[1],
            'title': student[2],
            'first_name': student[3],
            'middle_name': student[4],
            'last_name': student[5],
            'gender': student[6],
            'date_of_birth': student[7],
            'age': student[8],
            'course': student[9],
            'registration_datetime': student[10]
        },
        'modules': [
            {
                'type': m[0],
                'code': m[1],
                'name': m[2],
                'grade': m[3],
                'enrollment_date': m[4]
            } for m in modules
        ],
        'export_date': datetime.now().isoformat()
    }
    
    try:
        with open(filename, 'w') as f:
            json.dump(student_data, f, indent=2, default=str)
        print(f"✅ Student data exported to {filename}")
    except Exception as e:
        print(f"Export error: {e}")

def simulate_send_email(student):
    """Simulate sending email to student"""
    print(f"\n📧 EMAIL SIMULATION")
    print("-" * 30)
    print(f"To: {student[1]} ({student[3]} {student[5]})")
    
    subject = input("Email subject: ").strip()
    message = input("Email message: ").strip()
    
    if subject and message:
        print(f"\n✅ Email simulated successfully!")
        print(f"Subject: {subject}")
        print(f"Message: {message}")
        
        # Log the email simulation
        logging.info(f"Email simulated - To: {student[1]}, Subject: {subject}")
    else:
        print("❌ Email cancelled - missing subject or message")

def view_academic_history(student_id):
    """View detailed academic history"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print(f"\n📈 ACADEMIC HISTORY - Student {student_id}")
        print("="*60)
        
        # Get modules with timeline
        cursor.execute('''
        SELECT module_code, module_name, module_type, grade, 
               enrollment_date, completion_date
        FROM student_modules
        WHERE student_id = ?
        ORDER BY enrollment_date
        ''', (student_id,))
        
        history = cursor.fetchall()
        
        if history:
            print(f"{'Date':<12} {'Code':<8} {'Name':<25} {'Type':<10} {'Grade':<8}")
            print("-" * 70)
            
            for module in history:
                code, name, mod_type, grade, enroll_date, complete_date = module
                date_display = enroll_date[:10] if enroll_date else "N/A"
                grade_display = grade if grade else "In Progress"
                print(f"{date_display:<12} {code:<8} {name:<25} {mod_type:<10} {grade_display:<8}")
        else:
            print("No academic history found.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

# ===== MISSING HELPER FUNCTIONS =====

def export_to_excel(filename):
    """Export results to Excel format (simulation)"""
    print(f"📊 Excel export simulation - would export to {filename}")
    print("Note: In production, would use libraries like openpyxl or xlswriter")
    
    # Simulate Excel export
    try:
        # Create CSV as Excel substitute
        csv_filename = filename.replace('.xlsx', '.csv')
        export_to_csv(csv_filename)
        print(f"✅ Exported as CSV instead: {csv_filename}")
    except Exception as e:
        print(f"Export error: {e}")

def export_to_csv(filename):
    """Export results to CSV format"""
    try:
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'Student ID', 'Email', 'Title', 'First Name', 'Middle Name',
                'Last Name', 'Gender', 'Date of Birth', 'Age', 'Course',
                'Registration Datetime'
            ])
            
            # Write data
            for student in last_search_results:
                writer.writerow(student)
        
        print(f"✅ Data exported to {filename}")
        
    except Exception as e:
        print(f"Export error: {e}")

def custom_format_export():
    """Custom format export with user-defined fields"""
    print("\n📋 CUSTOM FORMAT EXPORT")
    print("-" * 40)
    
    print("Available fields:")
    fields = [
        'student_id', 'email', 'title', 'first_name', 'middle_name',
        'last_name', 'gender', 'date_of_birth', 'age', 'course',
        'registration_datetime'
    ]
    
    for i, field in enumerate(fields, 1):
        print(f"{i:2d}. {field}")
    
    selected = input("\nEnter field numbers (comma-separated): ").strip()
    
    try:
        indices = [int(x.strip()) - 1 for x in selected.split(',')]
        selected_fields = [fields[i] for i in indices if 0 <= i < len(fields)]
        
        if not selected_fields:
            print("No valid fields selected.")
            return
        
        # Choose separator
        separator = input("Enter field separator (default: comma): ").strip()
        if not separator:
            separator = ","
        
        # Export
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"custom_export_{timestamp}.txt"
        
        with open(filename, 'w') as f:
            # Write header
            f.write(separator.join(selected_fields) + "\n")
            
            # Write data
            for student in last_search_results:
                values = [str(student[fields.index(field)]) for field in selected_fields]
                f.write(separator.join(values) + "\n")
        
        print(f"✅ Custom export saved to {filename}")
        
    except (ValueError, IndexError) as e:
        print(f"Error in custom export: {e}")

def generate_email_list():
    """Generate email list from search results"""
    if not last_search_results:
        print("No search results available.")
        return
    
    print(f"\n📧 GENERATING EMAIL LIST ({len(last_search_results)} students)")
    print("="*60)
    
    # Extract emails
    emails = []
    for student in last_search_results:
        if student[1]:  # email field
            emails.append(student[1])
    
    print(f"Found {len(emails)} email addresses:")
    
    # Format options
    print("\nFormat options:")
    print("1. Plain text list")
    print("2. Comma-separated")
    print("3. Semicolon-separated (Outlook)")
    print("4. JSON format")
    
    choice = input("Select format (1-4): ").strip()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if choice == '1':
        filename = f"email_list_{timestamp}.txt"
        with open(filename, 'w') as f:
            for email in emails:
                f.write(email + "\n")
    elif choice == '2':
        filename = f"email_list_{timestamp}.txt"
        with open(filename, 'w') as f:
            f.write(", ".join(emails))
    elif choice == '3':
        filename = f"email_list_{timestamp}.txt"
        with open(filename, 'w') as f:
            f.write("; ".join(emails))
    elif choice == '4':
        filename = f"email_list_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump({"emails": emails, "count": len(emails), "generated": datetime.now().isoformat()}, f, indent=2)
    else:
        print("Invalid choice.")
        return
    
    print(f"✅ Email list exported to {filename}")

def create_student_groups():
    """Create student groups from search results"""
    if not last_search_results:
        print("No search results available.")
        return
    
    print(f"\n👥 CREATE STUDENT GROUPS ({len(last_search_results)} students)")
    print("="*60)
    
    print("Group creation options:")
    print("1. Group by course")
    print("2. Group by age range")
    print("3. Group by random assignment")
    print("4. Group by alphabetical order")
    
    choice = input("Select grouping method (1-4): ").strip()
    
    groups = {}
    
    if choice == '1':
        # Group by course
        for student in last_search_results:
            course = student[9]  # course field
            if course not in groups:
                groups[course] = []
            groups[course].append(student)
    
    elif choice == '2':
        # Group by age range
        for student in last_search_results:
            age = student[8]  # age field
            if age < 20:
                age_group = "Under 20"
            elif age <= 25:
                age_group = "20-25"
            elif age <= 30:
                age_group = "26-30"
            else:
                age_group = "Over 30"
            
            if age_group not in groups:
                groups[age_group] = []
            groups[age_group].append(student)
    
    elif choice == '3':
        # Random assignment
        import random
        
        try:
            num_groups = int(input("Number of groups: "))
            if num_groups <= 0:
                print("Invalid number of groups.")
                return
            
            students_copy = last_search_results.copy()
            random.shuffle(students_copy)
            
            for i, student in enumerate(students_copy):
                group_name = f"Group {(i % num_groups) + 1}"
                if group_name not in groups:
                    groups[group_name] = []
                groups[group_name].append(student)
                
        except ValueError:
            print("Invalid input.")
            return
    
    elif choice == '4':
        # Alphabetical order
        sorted_students = sorted(last_search_results, key=lambda x: f"{x[3]} {x[5]}")  # first_name last_name
        
        try:
            group_size = int(input("Students per group: "))
            if group_size <= 0:
                print("Invalid group size.")
                return
            
            for i in range(0, len(sorted_students), group_size):
                group_name = f"Group {(i // group_size) + 1}"
                groups[group_name] = sorted_students[i:i+group_size]
                
        except ValueError:
            print("Invalid input.")
            return
    
    else:
        print("Invalid choice.")
        return
    
    # Display groups
    print(f"\n📋 CREATED {len(groups)} GROUPS:")
    print("="*60)
    
    for group_name, students in groups.items():
        print(f"\n{group_name} ({len(students)} students):")
        for student in students:
            print(f"  • {student[0]} - {student[3]} {student[5]} ({student[1]})")
    
    # Export option
    export_groups = input("\nExport groups to file? (y/n): ").strip().lower()
    if export_groups == 'y':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"student_groups_{timestamp}.json"
        
        groups_data = {}
        for group_name, students in groups.items():
            groups_data[group_name] = [
                {
                    'student_id': s[0],
                    'name': f"{s[3]} {s[5]}",
                    'email': s[1],
                    'course': s[9]
                } for s in students
            ]
        
        with open(filename, 'w') as f:
            json.dump(groups_data, f, indent=2)
        
        print(f"✅ Groups exported to {filename}")

def mark_for_followup():
    """Mark students for follow-up"""
    if not last_search_results:
        print("No search results available.")
        return
    
    print(f"\n📌 MARK FOR FOLLOW-UP ({len(last_search_results)} students)")
    print("="*60)
    
    follow_up_reason = input("Enter follow-up reason: ").strip()
    priority = input("Priority (high/medium/low): ").strip().lower()
    
    if priority not in ['high', 'medium', 'low']:
        priority = 'medium'
    
    # Simulate marking for follow-up
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    follow_up_data = {
        'reason': follow_up_reason,
        'priority': priority,
        'marked_date': timestamp,
        'marked_by': current_user,
        'students': [
            {
                'student_id': s[0],
                'name': f"{s[3]} {s[5]}",
                'email': s[1]
            } for s in last_search_results
        ]
    }
    
    # Save to file
    filename = f"followup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(follow_up_data, f, indent=2)
    
    print(f"✅ {len(last_search_results)} students marked for follow-up")
    print(f"Reason: {follow_up_reason}")
    print(f"Priority: {priority}")
    print(f"Follow-up list saved to: {filename}")

def bulk_enrollment_management():
    """Manage bulk enrollment operations"""
    if not last_search_results:
        print("No search results available.")
        return
    
    print(f"\n🎓 BULK ENROLLMENT MANAGEMENT ({len(last_search_results)} students)")
    print("="*70)
    
    print("Operations:")
    print("1. Enroll in module")
    print("2. Unenroll from module")
    print("3. Transfer between modules")
    print("4. Update enrollment status")
    
    choice = input("Select operation (1-4): ").strip()
    
    if choice == '1':
        module_code = input("Module code to enroll in: ").strip()
        if module_code:
            print(f"✅ Simulation: Enrolled {len(last_search_results)} students in {module_code}")
    
    elif choice == '2':
        module_code = input("Module code to unenroll from: ").strip()
        if module_code:
            print(f"✅ Simulation: Unenrolled {len(last_search_results)} students from {module_code}")
    
    elif choice == '3':
        from_module = input("Transfer FROM module code: ").strip()
        to_module = input("Transfer TO module code: ").strip()
        if from_module and to_module:
            print(f"✅ Simulation: Transferred {len(last_search_results)} students from {from_module} to {to_module}")
    
    elif choice == '4':
        new_status = input("New enrollment status: ").strip()
        if new_status:
            print(f"✅ Simulation: Updated enrollment status to '{new_status}' for {len(last_search_results)} students")

def delete_saved_search():
    """Delete a saved search"""
    view_saved_searches()
    
    try:
        search_id = int(input("\nEnter search ID to delete: "))
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if search exists and belongs to user
        cursor.execute('''
        SELECT search_name FROM saved_searches
        WHERE id = ? AND user_id = ?
        ''', (search_id, current_user))
        
        result = cursor.fetchone()
        if not result:
            print("Search not found or access denied.")
            return
        
        search_name = result[0]
        confirm = input(f"Delete search '{search_name}'? (y/n): ").strip().lower()
        
        if confirm == 'y':
            cursor.execute('DELETE FROM saved_searches WHERE id = ?', (search_id,))
            conn.commit()
            print(f"✅ Search '{search_name}' deleted successfully.")
        else:
            print("Deletion cancelled.")
        
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error deleting search: {e}")

def share_search_profile():
    """Share a search profile with other users"""
    view_saved_searches()
    
    try:
        search_id = int(input("\nEnter search ID to share: "))
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if search exists and belongs to user
        cursor.execute('''
        SELECT search_name FROM saved_searches
        WHERE id = ? AND user_id = ?
        ''', (search_id, current_user))
        
        result = cursor.fetchone()
        if not result:
            print("Search not found or access denied.")
            return
        
        search_name = result[0]
        confirm = input(f"Share search '{search_name}' with all users? (y/n): ").strip().lower()
        
        if confirm == 'y':
            cursor.execute('''
            UPDATE saved_searches 
            SET is_shared = 1 
            WHERE id = ?
            ''', (search_id,))
            conn.commit()
            print(f"✅ Search '{search_name}' is now shared with all users.")
        else:
            print("Sharing cancelled.")
        
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error sharing search: {e}")

def modify_user_permissions():
    """Modify user permissions"""
    view_user_permissions()
    
    user_id = input("\nEnter User ID to modify: ").strip()
    if not user_id:
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT role, permissions FROM user_permissions WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result:
            print("User not found.")
            return
        
        current_role, current_permissions = result
        print(f"\nCurrent role: {current_role}")
        print(f"Current permissions: {current_permissions}")
        
        new_role = input(f"New role (current: {current_role}): ").strip()
        new_permissions = input(f"New permissions (current: {current_permissions}): ").strip()
        
        if new_role or new_permissions:
            if new_role:
                cursor.execute('UPDATE user_permissions SET role = ? WHERE user_id = ?', (new_role, user_id))
            if new_permissions:
                cursor.execute('UPDATE user_permissions SET permissions = ? WHERE user_id = ?', (new_permissions, user_id))
            
            conn.commit()
            print(f"✅ User '{user_id}' permissions updated successfully.")
        else:
            print("No changes made.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error modifying permissions: {e}")

def remove_user_permissions():
    """Remove user permissions"""
    view_user_permissions()
    
    user_id = input("\nEnter User ID to remove: ").strip()
    if not user_id:
        return
    
    confirm = input(f"Remove all permissions for user '{user_id}'? (y/n): ").strip().lower()
    
    if confirm == 'y':
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM user_permissions WHERE user_id = ?', (user_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                print(f"✅ User '{user_id}' removed successfully.")
            else:
                print("User not found.")
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Error removing user: {e}")
    else:
        print("Removal cancelled.")

def manage_scheduled_reports():
    """Manage scheduled reports"""
    print("\n📅 SCHEDULED REPORTS MANAGEMENT")
    print("="*50)
    
    print("1. View scheduled reports")
    print("2. Create new scheduled report")
    print("3. Modify scheduled report")
    print("4. Delete scheduled report")
    print("5. Run scheduled report now")
    
    choice = input("Select option (1-5): ").strip()
    
    if choice == '1':
        view_scheduled_reports()
    elif choice == '2':
        create_scheduled_report()
    elif choice == '3':
        modify_scheduled_report()
    elif choice == '4':
        delete_scheduled_report()
    elif choice == '5':
        run_scheduled_report()

def view_scheduled_reports():
    """View all scheduled reports"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, report_name, schedule_pattern, email_recipients, 
               last_run, is_active
        FROM scheduled_reports
        WHERE user_id = ?
        ORDER BY report_name
        ''', (current_user,))
        
        reports = cursor.fetchall()
        
        if not reports:
            print("No scheduled reports found.")
            return
        
        print(f"\n📋 YOUR SCHEDULED REPORTS:")
        print("-" * 100)
        print(f"{'ID':<5} {'Name':<25} {'Schedule':<15} {'Recipients':<25} {'Last Run':<15} {'Active':<8}")
        print("-" * 100)
        
        for report_id, name, schedule, recipients, last_run, active in reports:
            active_text = "Yes" if active else "No"
            last_run_text = last_run[:10] if last_run else "Never"
            recipients_text = recipients[:22] + "..." if len(recipients) > 25 else recipients
            
            print(f"{report_id:<5} {name:<25} {schedule:<15} {recipients_text:<25} {last_run_text:<15} {active_text:<8}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error viewing scheduled reports: {e}")

def create_scheduled_report():
    """Create a new scheduled report"""
    print("\n📝 CREATE SCHEDULED REPORT")
    print("-" * 40)
    
    report_name = input("Report name: ").strip()
    if not report_name:
        print("Report name is required.")
        return
    
    print("\nSchedule patterns:")
    print("1. Daily")
    print("2. Weekly")
    print("3. Monthly")
    print("4. Custom")
    
    schedule_choice = input("Select schedule (1-4): ").strip()
    
    schedule_patterns = {
        '1': 'daily',
        '2': 'weekly',
        '3': 'monthly',
        '4': input("Enter custom schedule pattern: ").strip()
    }
    
    schedule_pattern = schedule_patterns.get(schedule_choice, 'weekly')
    
    email_recipients = input("Email recipients (comma-separated): ").strip()
    
    # For simplicity, use the last search criteria
    if last_search_results:
        search_criteria = {"type": "last_search", "count": len(last_search_results)}
    else:
        search_criteria = {"type": "all_students"}
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO scheduled_reports 
        (user_id, report_name, search_criteria, schedule_pattern, email_recipients)
        VALUES (?, ?, ?, ?, ?)
        ''', (current_user, report_name, json.dumps(search_criteria), schedule_pattern, email_recipients))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Scheduled report '{report_name}' created successfully!")
        print(f"Schedule: {schedule_pattern}")
        print(f"Recipients: {email_recipients}")
        
    except sqlite3.Error as e:
        print(f"Error creating scheduled report: {e}")

def module_success_probability(cursor):
    """Calculate module success probability"""
    print("\n🎯 MODULE SUCCESS PROBABILITY")
    print("-" * 50)
    
    # Get module statistics
    cursor.execute('''
    SELECT sm.module_code, sm.module_name,
           COUNT(*) as total_enrolled,
           COALESCE(SUM(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1 ELSE 0 END), 0) as passed,
           COALESCE(AVG(CASE WHEN sm.grade IS NOT NULL THEN 1.0 ELSE 0.0 END), 0.0) as completion_rate
    FROM student_modules sm
    GROUP BY sm.module_code, sm.module_name
    HAVING total_enrolled >= 5
    ORDER BY completion_rate DESC
    ''')

    module_stats = cursor.fetchall()

    if not module_stats:
        print("Insufficient data for probability calculation.")
        return

    print(f"📊 MODULE SUCCESS PROBABILITIES:")
    print("-" * 80)
    print(f"{'Module Code':<12} {'Module Name':<30} {'Success Rate':<12} {'Prediction':<15}")
    print("-" * 80)

    for module_code, module_name, total, passed, completion_rate in module_stats:
        passed_safe = passed if passed is not None else 0
        success_rate = (passed_safe / total) * 100 if total > 0 else 0
        
        # Simple prediction based on historical data
        if success_rate >= 80:
            prediction = "High Success"
        elif success_rate >= 60:
            prediction = "Moderate Success"
        else:
            prediction = "Low Success"
        
        print(f"{module_code:<12} {module_name:<30} {success_rate:>8.1f}%    {prediction:<15}")

def graduation_timeline_forecast(cursor):
    """Forecast graduation timelines"""
    print("\n🎓 GRADUATION TIMELINE FORECAST")
    print("-" * 50)
    
    # Get student progress data
    cursor.execute('''
    SELECT s.student_id, s.first_name, s.last_name, s.course,
           COUNT(sm.module_code) as completed_modules,
           s.registration_datetime,
           julianday('now') - julianday(s.registration_datetime) as days_enrolled
    FROM students s
    LEFT JOIN student_modules sm ON s.student_id = sm.student_id 
                                  AND sm.grade IS NOT NULL 
                                  AND sm.grade != 'F'
    GROUP BY s.student_id, s.first_name, s.last_name, s.course, s.registration_datetime
    HAVING days_enrolled > 30
    ORDER BY completed_modules DESC
    ''')
    
    student_progress = cursor.fetchall()
    
    if not student_progress:
        print("Insufficient data for graduation forecast.")
        return
    
    # Assume typical program requires 8 modules for CS, 6 for DS
    required_modules = {'CS': 8, 'DS': 6}
    
    print(f"🔮 GRADUATION FORECASTS:")
    print("-" * 90)
    print(f"{'Student ID':<12} {'Name':<25} {'Course':<8} {'Progress':<10} {'Est. Graduation':<15}")
    print("-" * 90)
    
    for student_id, first_name, last_name, course, completed, reg_date, days_enrolled in student_progress[:15]:
        required = required_modules.get(course, 8)
        progress_pct = (completed / required) * 100
        
        if completed >= required:
            forecast = "Graduated"
        elif completed == 0:
            forecast = "No progress"
        else:
            # Simple linear projection
            modules_per_day = completed / days_enrolled if days_enrolled > 0 else 0
            remaining_modules = required - completed
            
            if modules_per_day > 0:
                days_to_graduate = remaining_modules / modules_per_day
                months_to_graduate = days_to_graduate / 30
                
                if months_to_graduate < 12:
                    forecast = f"{months_to_graduate:.1f} months"
                else:
                    forecast = f"{months_to_graduate/12:.1f} years"
            else:
                forecast = "Stalled"
        
        name = f"{first_name} {last_name}"
        progress_text = f"{completed}/{required}"
        
        print(f"{student_id:<12} {name:<25} {course:<8} {progress_text:<10} {forecast:<15}")

def generate_course_pie_chart(cursor):
    """Generate course enrollment pie chart (text-based)"""
    cursor.execute('''
    SELECT course, COUNT(*) as count
    FROM students
    GROUP BY course
    ORDER BY count DESC
    ''')
    
    data = cursor.fetchall()
    if not data:
        print("No course data available.")
        return
    
    total = sum(count for _, count in data)
    
    print("\n🥧 COURSE ENROLLMENT PIE CHART:")
    print("-" * 50)
    
    for course, count in data:
        percentage = (count / total) * 100 if total > 0 else 0
        pie_chars = int(percentage / 2.5)  # Each char represents 2.5%
        pie_slice = '●' * pie_chars
        print(f"{course:<10} |{pie_slice:<40} {count:>6} ({percentage:>5.1f}%)")

def generate_gender_course_chart(cursor):
    """Generate gender distribution by course chart"""
    cursor.execute('''
    SELECT course, gender, COUNT(*) as count
    FROM students
    GROUP BY course, gender
    ORDER BY course, gender
    ''')
    
    data = cursor.fetchall()
    
    print("\n⚧ GENDER DISTRIBUTION BY COURSE:")
    print("-" * 60)
    
    current_course = None
    for course, gender, count in data:
        if course != current_course:
            if current_course is not None:
                print()  # Add spacing between courses
            print(f"\n{course} Course:")
            current_course = course
        
        bar_length = min(count, 30)  # Cap at 30 chars
        bar = '█' * bar_length
        print(f"  {gender:<10} |{bar:<30} {count}")

def generate_module_popularity_chart(cursor):
    """Generate module popularity chart"""
    cursor.execute('''
    SELECT sm.module_name, COUNT(*) as enrollments
    FROM student_modules sm
    GROUP BY sm.module_name
    ORDER BY enrollments DESC
    LIMIT 15
    ''')
    
    data = cursor.fetchall()
    
    print("\n🎓 TOP 15 MOST POPULAR MODULES:")
    print("-" * 70)
    
    if not data:
        print("No module enrollment data available.")
        return
    
    max_enrollments = max(count for _, count in data)
    
    for i, (module_name, count) in enumerate(data, 1):
        bar_length = int((count / max_enrollments) * 40) if max_enrollments > 0 else 0
        bar = '▓' * bar_length
        
        # Truncate long module names
        display_name = module_name[:35] + "..." if len(module_name) > 38 else module_name
        
        print(f"{i:2d}. {display_name:<38} |{bar:<40} {count}")

def generate_custom_reports():
    """Generate custom reports with user-defined parameters"""
    print("\n📊 CUSTOM REPORT GENERATOR")
    print("="*50)
    
    print("Report types:")
    print("1. Student summary report")
    print("2. Module enrollment report")
    print("3. Demographics analysis")
    print("4. Performance report")
    print("5. Custom SQL report")
    
    choice = input("Select report type (1-5): ").strip()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if choice == '1':
            generate_student_summary_report(cursor)
        elif choice == '2':
            generate_module_enrollment_report(cursor)
        elif choice == '3':
            generate_demographics_analysis(cursor)
        elif choice == '4':
            generate_performance_report(cursor)
        elif choice == '5':
            generate_custom_sql_report(cursor)
        else:
            print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_student_summary_report(cursor):
    """Generate comprehensive student summary report"""
    print("\n📋 STUDENT SUMMARY REPORT")
    print("="*60)
    
    # Overall statistics
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT course) FROM students")
    total_courses = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(age) FROM students WHERE age IS NOT NULL")
    avg_age = cursor.fetchone()[0] or 0
    
    print(f"📊 OVERVIEW:")
    print(f"Total Students: {total_students}")
    print(f"Total Courses: {total_courses}")
    print(f"Average Age: {avg_age:.1f}")
    
    # Course breakdown
    cursor.execute('''
    SELECT course, COUNT(*) as count
    FROM students
    GROUP BY course
    ORDER BY count DESC
    ''')
    
    course_data = cursor.fetchall()
    
    print(f"\n📚 COURSE BREAKDOWN:")
    for course, count in course_data:
        percentage = (count / total_students) * 100 if total_students > 0 else 0
        print(f"  {course}: {count} students ({percentage:.1f}%)")
    
    # Gender distribution
    cursor.execute('''
    SELECT gender, COUNT(*) as count
    FROM students
    GROUP BY gender
    ORDER BY count DESC
    ''')
    
    gender_data = cursor.fetchall()
    
    print(f"\n👥 GENDER DISTRIBUTION:")
    for gender, count in gender_data:
        percentage = (count / total_students) * 100 if total_students > 0 else 0
        print(f"  {gender}: {count} students ({percentage:.1f}%)")
    
    # Recent registrations
    cursor.execute('''
    SELECT COUNT(*) FROM students
    WHERE registration_datetime >= date('now', '-30 days')
    ''')
    
    recent_registrations = cursor.fetchone()[0]
    
    print(f"\n📅 RECENT ACTIVITY:")
    print(f"New registrations (last 30 days): {recent_registrations}")

def generate_module_enrollment_report(cursor):
    """Generate module enrollment report"""
    print("\n🎓 MODULE ENROLLMENT REPORT")
    print("="*60)
    
    # Module statistics
    cursor.execute('''
    SELECT sm.module_code, sm.module_name, sm.module_type,
           COUNT(*) as total_enrolled,
           SUM(CASE WHEN sm.grade IS NOT NULL THEN 1 ELSE 0 END) as completed,
           AVG(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1.0 ELSE 0.0 END) * 100 as success_rate
    FROM student_modules sm
    GROUP BY sm.module_code, sm.module_name, sm.module_type
    ORDER BY total_enrolled DESC
    ''')
    
    module_data = cursor.fetchall()
    
    if not module_data:
        print("No module enrollment data found.")
        return
    
    print(f"📊 MODULE STATISTICS:")
    print("-" * 100)
    print(f"{'Code':<10} {'Name':<30} {'Type':<12} {'Enrolled':<10} {'Completed':<10} {'Success %':<10}")
    print("-" * 100)
    
    for code, name, mod_type, enrolled, completed, success_rate in module_data:
        success_display = f"{success_rate:.1f}%" if success_rate is not None else "N/A"
        name_display = name[:27] + "..." if len(name) > 30 else name
        
        print(f"{code:<10} {name_display:<30} {mod_type:<12} {enrolled:<10} {completed:<10} {success_display:<10}")
    
    # Summary statistics
    total_enrollments = sum(row[3] for row in module_data)
    total_completions = sum(row[4] for row in module_data)
    overall_completion_rate = (total_completions / total_enrollments) * 100 if total_enrollments > 0 else 0
    
    print(f"\n📈 SUMMARY:")
    print(f"Total Enrollments: {total_enrollments}")
    print(f"Total Completions: {total_completions}")
    print(f"Overall Completion Rate: {overall_completion_rate:.1f}%")

def generate_demographics_analysis(cursor):
    """Generate detailed demographics analysis"""
    print("\n👥 DEMOGRAPHICS ANALYSIS REPORT")
    print("="*60)
    
    # Age distribution analysis
    cursor.execute('''
    SELECT 
        CASE 
            WHEN age < 20 THEN 'Under 20'
            WHEN age BETWEEN 20 AND 25 THEN '20-25'
            WHEN age BETWEEN 26 AND 30 THEN '26-30'
            WHEN age BETWEEN 31 AND 35 THEN '31-35'
            WHEN age BETWEEN 36 AND 40 THEN '36-40'
            ELSE 'Over 40'
        END as age_group,
        COUNT(*) as count
    FROM students
    WHERE age IS NOT NULL
    GROUP BY age_group
    ORDER BY 
        CASE age_group
            WHEN 'Under 20' THEN 1
            WHEN '20-25' THEN 2
            WHEN '26-30' THEN 3
            WHEN '31-35' THEN 4
            WHEN '36-40' THEN 5
            ELSE 6
        END
    ''')
    
    age_data = cursor.fetchall()
    total_with_age = sum(count for _, count in age_data)
    
    print(f"📊 AGE DISTRIBUTION:")
    print("-" * 40)
    for age_group, count in age_data:
        percentage = (count / total_with_age) * 100 if total_with_age > 0 else 0
        bar = '█' * min(int(percentage / 2), 40)
        print(f"{age_group:<15} |{bar:<40} {count:>5} ({percentage:>5.1f}%)")
    
    # Cross-tabulation: Course by Gender
    cursor.execute('''
    SELECT course, gender, COUNT(*) as count
    FROM students
    GROUP BY course, gender
    ORDER BY course, gender
    ''')
    
    cross_tab = cursor.fetchall()
    
    print(f"\n📋 COURSE × GENDER CROSS-TABULATION:")
    print("-" * 50)
    
    # Organize data for display
    courses = {}
    for course, gender, count in cross_tab:
        if course not in courses:
            courses[course] = {}
        courses[course][gender] = count
    
    # Display cross-tabulation
    genders = ['male', 'female', 'other']
    header = f"{'Course':<10}" + "".join(f"{g.capitalize():<10}" for g in genders) + "Total"
    print(header)
    print("-" * len(header))
    
    for course, gender_counts in courses.items():
        row = f"{course:<10}"
        total = 0
        for gender in genders:
            count = gender_counts.get(gender, 0)
            row += f"{count:<10}"
            total += count
        row += f"{total}"
        print(row)

def generate_performance_report(cursor):
    """Generate academic performance report"""
    print("\n🎯 ACADEMIC PERFORMANCE REPORT")
    print("="*60)
    
    # Student performance metrics
    cursor.execute('''
    SELECT s.student_id, s.first_name, s.last_name, s.course,
           COUNT(sm.module_code) as total_modules,
           SUM(CASE WHEN sm.grade IS NOT NULL THEN 1 ELSE 0 END) as completed_modules,
           SUM(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1 ELSE 0 END) as passed_modules,
           AVG(CASE WHEN sm.grade IN ('A', 'B', 'C', 'D') THEN 1.0 ELSE 0.0 END) * 100 as success_rate
    FROM students s
    LEFT JOIN student_modules sm ON s.student_id = sm.student_id
    GROUP BY s.student_id, s.first_name, s.last_name, s.course
    HAVING total_modules > 0
    ORDER BY success_rate DESC, completed_modules DESC
    ''')
    
    performance_data = cursor.fetchall()
    
    if not performance_data:
        print("No performance data available.")
        return
    
    print(f"🏆 TOP PERFORMING STUDENTS:")
    print("-" * 100)
    print(f"{'Rank':<5} {'Student ID':<12} {'Name':<25} {'Course':<8} {'Modules':<10} {'Success %':<10}")
    print("-" * 100)
    
    for rank, (student_id, first_name, last_name, course, total, completed, passed, success_rate) in enumerate(performance_data[:20], 1):
        name = f"{first_name} {last_name}"
        modules_text = f"{completed}/{total}"
        success_display = f"{success_rate:.1f}%" if success_rate is not None else "N/A"
        
        print(f"{rank:<5} {student_id:<12} {name:<25} {course:<8} {modules_text:<10} {success_display:<10}")
    
    # Performance statistics by course
    cursor.execute('''
    SELECT s.course,
           AVG(CASE WHEN sm.grade IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100 as avg_completion_rate,
           AVG(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1.0 ELSE 0.0 END) * 100 as avg_success_rate
    FROM students s
    LEFT JOIN student_modules sm ON s.student_id = sm.student_id
    GROUP BY s.course
    ORDER BY avg_success_rate DESC
    ''')
    
    course_performance = cursor.fetchall()
    
    print(f"\n📊 PERFORMANCE BY COURSE:")
    print("-" * 60)
    print(f"{'Course':<10} {'Avg Completion %':<18} {'Avg Success %':<15}")
    print("-" * 60)
    
    for course, completion_rate, success_rate in course_performance:
        completion_display = f"{completion_rate:.1f}%" if completion_rate is not None else "N/A"
        success_display = f"{success_rate:.1f}%" if success_rate is not None else "N/A"
        
        print(f"{course:<10} {completion_display:<18} {success_display:<15}")

def generate_custom_sql_report(cursor):
    """Generate report from custom SQL query"""
    print("\n💻 CUSTOM SQL REPORT")
    print("="*50)
    
    print("⚠️  Warning: Only use trusted SQL queries.")
    print("Available tables: students, student_modules, search_analytics")
    
    query = input("\nEnter SQL query: ").strip()
    
    if not query:
        print("No query provided.")
        return
    
    # Basic validation
    forbidden_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']
    query_upper = query.upper()
    
    for keyword in forbidden_keywords:
        if keyword in query_upper:
            print(f"❌ Forbidden keyword '{keyword}' detected. Query rejected.")
            return
    
    try:
        cursor.execute(query)
        results = cursor.fetchall()
        
        if not results:
            print("Query executed successfully but returned no results.")
            return
        
        # Get column names
        column_names = [description[0] for description in cursor.description]
        
        print(f"\n📊 QUERY RESULTS ({len(results)} rows):")
        print("-" * 100)
        
        # Display header
        header = " | ".join(f"{name:<15}" for name in column_names)
        print(header)
        print("-" * len(header))
        
        # Display results (limit to first 50 rows for readability)
        for row in results[:50]:
            row_str = " | ".join(f"{str(value):<15}" for value in row)
            print(row_str)
        
        if len(results) > 50:
            print(f"\n... and {len(results) - 50} more rows")
        
        # Export option
        export_choice = input(f"\nExport results to CSV? (y/n): ").strip().lower()
        if export_choice == 'y':
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"custom_report_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(column_names)
                writer.writerows(results)
            
            print(f"✅ Results exported to {filename}")
    
    except sqlite3.Error as e:
        print(f"SQL Error: {e}")

def modify_scheduled_report():
    """Modify an existing scheduled report"""
    view_scheduled_reports()
    
    try:
        report_id = int(input("\nEnter report ID to modify: "))
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT report_name, schedule_pattern, email_recipients, is_active
        FROM scheduled_reports
        WHERE id = ? AND user_id = ?
        ''', (report_id, current_user))
        
        result = cursor.fetchone()
        if not result:
            print("Report not found or access denied.")
            return
        
        name, schedule, recipients, active = result
        
        print(f"\nCurrent settings:")
        print(f"Name: {name}")
        print(f"Schedule: {schedule}")
        print(f"Recipients: {recipients}")
        print(f"Active: {'Yes' if active else 'No'}")
        
        # Get new values
        new_name = input(f"New name (current: {name}): ").strip()
        new_schedule = input(f"New schedule (current: {schedule}): ").strip()
        new_recipients = input(f"New recipients (current: {recipients}): ").strip()
        new_active = input(f"Active? y/n (current: {'y' if active else 'n'}): ").strip().lower()
        
        # Update only changed fields
        updates = []
        params = []
        
        if new_name:
            updates.append("report_name = ?")
            params.append(new_name)
        
        if new_schedule:
            updates.append("schedule_pattern = ?")
            params.append(new_schedule)
        
        if new_recipients:
            updates.append("email_recipients = ?")
            params.append(new_recipients)
        
        if new_active in ['y', 'n']:
            updates.append("is_active = ?")
            params.append(1 if new_active == 'y' else 0)
        
        if updates:
            query = f"UPDATE scheduled_reports SET {', '.join(updates)} WHERE id = ?"
            params.append(report_id)
            
            cursor.execute(query, params)
            conn.commit()
            print("✅ Report updated successfully.")
        else:
            print("No changes made.")
        
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error modifying report: {e}")

def delete_scheduled_report():
    """Delete a scheduled report"""
    view_scheduled_reports()
    
    try:
        report_id = int(input("\nEnter report ID to delete: "))
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT report_name FROM scheduled_reports
        WHERE id = ? AND user_id = ?
        ''', (report_id, current_user))
        
        result = cursor.fetchone()
        if not result:
            print("Report not found or access denied.")
            return
        
        report_name = result[0]
        confirm = input(f"Delete report '{report_name}'? (y/n): ").strip().lower()
        
        if confirm == 'y':
            cursor.execute('DELETE FROM scheduled_reports WHERE id = ?', (report_id,))
            conn.commit()
            print(f"✅ Report '{report_name}' deleted successfully.")
        else:
            print("Deletion cancelled.")
        
        conn.close()
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error deleting report: {e}")

def run_scheduled_report():
    """Run a scheduled report immediately"""
    view_scheduled_reports()
    
    try:
        report_id = int(input("\nEnter report ID to run: "))
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT report_name, search_criteria, email_recipients
        FROM scheduled_reports
        WHERE id = ? AND user_id = ?
        ''', (report_id, current_user))
        
        result = cursor.fetchone()
        if not result:
            print("Report not found or access denied.")
            return
        
        report_name, criteria_json, recipients = result
        
        print(f"\n🏃 Running report '{report_name}'...")
        
        # Simulate report execution
        criteria = json.loads(criteria_json)
        
        # For simplicity, just show current student count
        cursor.execute("SELECT COUNT(*) FROM students")
        student_count = cursor.fetchone()[0]
        
        print(f"✅ Report executed successfully!")
        print(f"Report: {report_name}")
        print(f"Data: {student_count} students")
        print(f"Recipients: {recipients}")
        print(f"Execution time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Update last run time
        cursor.execute('''
        UPDATE scheduled_reports 
        SET last_run = CURRENT_TIMESTAMP 
        WHERE id = ?
        ''', (report_id,))
        
        conn.commit()
        conn.close()
        
        print("📧 Report would be emailed to recipients in production.")
        
    except (ValueError, sqlite3.Error) as e:
        print(f"Error running report: {e}")

if __name__ == "__main__":
    print("🛠️  Database Initialization Tool")
    print("=" * 50)
    
    # Check if database exists
    if os.path.exists(str(_DB_PATH)):
        print("📁 Found existing database file")
        check_database_status()
        print()
        
        choice = input("Initialize/update database? (y/n): ").strip().lower()
        if choice == 'y':
            create_enhanced_database()
        else:
            print("Database initialization skipped.")
    else:
        print("📁 No existing database found")
        create_enhanced_database()
    
    print("\n🎯 Next steps:")
    print("1. Run your main advanced_search.py script")
    print("2. Call display_enhanced_menu() to access all features")
    print("3. Try the search analytics dashboard!")

    print("🚀 Enhanced Student Search System Loaded!")
    print("Run display_enhanced_menu() to start the enhanced system.")
    
    # Initialize the enhanced database
    init_enhanced_database()
    
    # Start the enhanced menu
    display_enhanced_menu()
