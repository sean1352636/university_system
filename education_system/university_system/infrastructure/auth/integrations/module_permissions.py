"""
Module Permissions Setup

This module contains all the permission setup functions for various system modules.
Each function sets up the necessary permissions in the database for specific features.

Functions:
    - initialize_complete_system(): Initialize complete system with all integrations
    - init_trip_db(): Initialize trip management database
    - setup_trip_permissions(): Setup trip management permissions
    - integrate_trip_management_with_main(): Integrate trip management
    - add_finance_permissions(): Add finance permissions
    - fix_alumni_permissions(): Fix alumni permissions for existing database
    - get_health_role_permissions(): Get health-related role permissions
    - add_calendar_permissions(): Add calendar permissions
    - setup_ai_detector_permissions(): Setup AI detector permissions
    - verify_ai_detector_setup(): Verify AI detector setup
    - add_ai_detector_permissions_to_database(): Add AI detector permissions to DB
    - add_plagiarism_permissions(): Add plagiarism permissions
    - fix_library_permissions(): Fix library permissions
"""

import logging
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
)

logger = logging.getLogger(__name__)

# Import optional chatbot availability check
try:
    from education_system.university_system.infrastructure.auth.optional_dependencies import is_chatbot_available
    CHATBOT_AVAILABLE = is_chatbot_available()
except ImportError:
    CHATBOT_AVAILABLE = False

# Import PERMISSIONS constant - will be populated by core module
PERMISSIONS = {}

def initialize_complete_system():
    """Initialize the complete system with chatbot integration
    
    Returns:
        UserAuth instance if successful, None otherwise
    """
    print("=== INITIALIZING COMPLETE UNIVERSITY SYSTEM ===")
    
    try:
        # Import here to avoid circular imports
        from education_system.university_system.infrastructure.auth.core import UserAuth
        
        # Initialize authentication
        print("1. Initializing authentication system...")
        auth = UserAuth()
        
        # Setup chatbot permissions
        print("2. Setting up chatbot permissions...")
        from education_system.university_system.infrastructure.auth.chatbot_integration import setup_chatbot_permissions
        setup_chatbot_permissions(auth)
        
        # Initialize chatbot integration
        print("3. Initializing chatbot integration...")
        from education_system.university_system.infrastructure.auth.chatbot_integration import initialize_chatbot_integration
        initialize_chatbot_integration(auth)
        
        # Test the integration
        print("4. Testing integration...")
        if CHATBOT_AVAILABLE:
            print("✓ Chatbot integration available")
        else:
            logger.warning("Chatbot integration not available")
        
        print("5. System initialization completed!")
        print("\nAvailable features:")
        print("- User authentication and authorization")
        print("- Role-based access control")
        print("- University chatbot with voice support")
        print("- Integrated conversation logging")
        print("- Analytics and reporting")
        
        return auth

    except sqlite3.Error as e:
        print(f"❌ System initialization failed (database error): {e}")
        return None
    except (AuthenticationError, PermissionDeniedError) as e:
        print(f"❌ System initialization failed (auth error): {e}")
        return None
    except (ImportError, AttributeError) as e:
        print(f"❌ System initialization failed (module error): {e}")
        return None

def init_trip_db():
    """Initialize trip management database tables
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create trips table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            destination TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            max_participants INTEGER,
            cost REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_by INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')
        
        # Create trip registrations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trip_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            registration_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(trip_id, user_id)
        )
        ''')
        
        # Create trip expenses table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trip_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            expense_date TEXT NOT NULL,
            category TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')
        
        conn.commit()
        conn.close()
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Error initializing trip database: {e}")
        return False

def setup_trip_permissions(auth=None):
    """Setup trip management permissions
    
    Args:
        auth: Optional UserAuth instance (unused, kept for compatibility)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Trip permissions
        trip_permissions = [
            ('manage_trips', 'Manage Trip Records'),
            ('create_trips', 'Create New Trips'),
            ('view_trips', 'View Trip Information'),
            ('register_for_trips', 'Register for Trips'),
            ('view_own_trip_registrations', 'View Own Trip Registrations'),
            ('cancel_trip_registration', 'Cancel Trip Registration'),
            ('manage_trip_participants', 'Manage Trip Participants'),
            ('view_trip_reports', 'View Trip Reports'),
            ('manage_trip_expenses', 'Manage Trip Expenses'),
            ('approve_trip_registrations', 'Approve Trip Registrations')
        ]
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for perm_name, perm_desc in trip_permissions:
            cursor.execute(
                'INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                (perm_name, perm_desc, timestamp)
            )
        
        # Assign permissions to roles
        role_permissions = {
            'admin': [
                'manage_trips', 'create_trips', 'view_trips', 'register_for_trips',
                'view_own_trip_registrations', 'cancel_trip_registration',
                'manage_trip_participants', 'view_trip_reports', 'manage_trip_expenses',
                'approve_trip_registrations'
            ],
            'staff': [
                'create_trips', 'view_trips', 'manage_trip_participants',
                'view_trip_reports', 'manage_trip_expenses', 'approve_trip_registrations'
            ],
            'instructor': [
                'view_trips', 'register_for_trips', 'view_own_trip_registrations',
                'cancel_trip_registration'
            ],
            'student': [
                'view_trips', 'register_for_trips', 'view_own_trip_registrations',
                'cancel_trip_registration'
            ]
        }
        
        for role_name, permissions in role_permissions.items():
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if role_result:
                role_id = role_result[0]
                
                for perm_name in permissions:
                    cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                    perm_result = cursor.fetchone()
                    if perm_result:
                        perm_id = perm_result[0]
                        cursor.execute(
                            'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                            (role_id, perm_id)
                        )
        
        conn.commit()
        conn.close()
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Error setting up trip permissions: {e}")
        return False

def set_trip_auth(auth_instance):
    """Set the authentication instance for trip management
    
    Args:
        auth_instance: UserAuth instance
    """
    global _trip_auth_instance
    _trip_auth_instance = auth_instance
    logging.info("Trip management authentication configured")

def integrate_trip_management_with_main():
    """Integrate trip management with the main system
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize trip database
        if not init_trip_db():
            logging.error("Failed to initialize trip database")
            return False
        
        # Setup permissions
        if not setup_trip_permissions():
            logging.error("Failed to setup trip permissions")
            return False
        
        logging.info("Trip management integration completed successfully")
        return True

    except sqlite3.Error as e:
        logging.error(f"Database error integrating trip management: {e}")
        return False
    except (PermissionDeniedError, AuthenticationError) as e:
        logging.error(f"Auth error integrating trip management: {e}")
        return False

# Global variable for trip auth instance
_trip_auth_instance = None

def add_finance_permissions(auth=None):
    """Add finance-related permissions to the database
    
    Args:
        auth: Optional UserAuth instance (unused, kept for compatibility)
        
    Returns:
        List[str]: List of created permission names
    """
    finance_permissions = [
        ('view_financial_reports', 'View Financial Reports'),
        ('manage_finances', 'Manage Financial Records'),
        ('export_financial_data', 'Export Financial Data'),
        ('record_payments', 'Record Payment Transactions')
    ]

    created_permissions = []
    conn = get_connection()
    cursor = conn.cursor()

    for perm_name, perm_desc in finance_permissions:
        try:
            # Check if permission already exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            if not cursor.fetchone():
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                conn.commit()
                created_permissions.append(perm_name)
        except sqlite3.Error as e:
            logger.error(f"Error creating permission {perm_name}: {e}")

    conn.close()
    return created_permissions

def fix_alumni_permissions():
    """Fix alumni permissions for existing database"""
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # All alumni-related permissions that should exist
    all_alumni_permissions = [
        ('manage_alumni', 'Manage Alumni'),
        ('view_alumni', 'View Alumni'),
        ('view_own_alumni_profile', 'View Own Alumni Profile'),
        ('update_own_alumni_profile', 'Update Own Alumni Profile'),
        ('manage_events', 'Manage Events'),
        ('view_events', 'View Events'),
        ('make_donation', 'Make Donation'),
        ('view_own_donations', 'View Own Donations'),
        ('manage_donations', 'Manage Donations'),
        ('manage_mentorships', 'Manage Mentorships'),
        ('view_own_mentorships', 'View Own Mentorships')
    ]
    
    # Create any missing permissions
    for perm_name, perm_desc in all_alumni_permissions:
        cursor.execute(
            'INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
            (perm_name, perm_desc, timestamp)
        )
    
    conn.commit()
    print("Created missing alumni permissions")
    
    # Now assign them to the admin role
    cursor.execute('SELECT id FROM roles WHERE role_name = ?', ('admin',))
    admin_role = cursor.fetchone()
    
    if admin_role:
        admin_role_id = admin_role[0]
        
        for perm_name, _ in all_alumni_permissions:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            perm = cursor.fetchone()
            
            if perm:
                perm_id = perm[0]
                cursor.execute(
                    'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                    (admin_role_id, perm_id)
                )
        
        conn.commit()
        print("Assigned alumni permissions to admin role")
    
    # Also assign appropriate permissions to other roles
    role_permissions = {
        'staff': ['view_alumni', 'manage_events', 'view_events'],
        'alumni': ['view_own_alumni_profile', 'update_own_alumni_profile', 'view_events', 
                  'view_own_donations', 'make_donation'],
        'student': ['view_events']
    }
    
    for role_name, permissions in role_permissions.items():
        cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
        role = cursor.fetchone()
        
        if role:
            role_id = role[0]
            
            for perm_name in permissions:
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                perm = cursor.fetchone()
                
                if perm:
                    perm_id = perm[0]
                    cursor.execute(
                        'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                        (role_id, perm_id)
                    )
            
            print(f"Assigned alumni permissions to {role_name} role")
    
    conn.commit()
    conn.close()
    print("\nAlumni permissions have been fixed!")
    print("Please restart your application and try logging in as admin again.")

def get_health_role_permissions() -> Dict[str, List[str]]:
    """Return a dictionary of health-related permissions for different roles.
    This can be used when creating new roles in the system.
    
    Returns:
        Dict[str, List[str]]: Dictionary mapping role names to their health permissions
    """
    return {
        'admin': [
            'manage_health_records',
            'view_any_health_record',
            'manage_health_appointments',
            'verify_vaccinations',
            'issue_health_advisories',
            'view_health_advisories',
            'view_health_resources'
        ],
        'health_provider': [
            'manage_health_records',
            'view_any_health_record',
            'manage_health_appointments',
            'manage_vaccinations',
            'verify_vaccinations',
            'issue_health_advisories',
            'view_health_advisories',
            'view_health_resources'
        ],
        'staff': [
            'view_health_advisories',
            'view_vaccination_requirements',
            'view_health_resources'
        ],
        'student': [
            'view_own_health_record',
            'schedule_health_appointment',
            'view_own_appointments',
            'cancel_own_appointment',
            'view_own_vaccinations',
            'update_insurance_info',
            'view_health_advisories',
            'view_health_resources'
        ]
    }

def add_calendar_permissions():
    """Add calendar-related permissions to the database"""
    from education_system.university_system.infrastructure.auth.core import UserAuth
    
    auth = UserAuth()
    calendar_permissions = [
        ('manage_academic_calendar', 'Manage Academic Calendar'),
        ('view_academic_calendar', 'View Academic Calendar'),
        ('create_academic_events', 'Create Academic Events'),
        ('update_academic_events', 'Update Academic Events'),
        ('delete_academic_events', 'Delete Academic Events'),
        ('export_calendar_data', 'Export Calendar Data'),
        ('view_school_calendar', 'View School Calendar')
    ]
    
    try:
        conn = auth._create_configured_connection()
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for perm_name, perm_desc in calendar_permissions:
            # Check if permission already exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            if not cursor.fetchone():
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                print(f"Added permission: {perm_name}")
        
        conn.commit()
        conn.close()
        
        # Now associate these permissions with roles
        auth._init_db()  # This will update role-permission associations
        
        print("Calendar permissions added successfully!")
        
    except sqlite3.Error as e:
        logger.error(f"Error adding calendar permissions: {e}")

def setup_ai_detector_permissions():
    """Setup AI detector permissions in the database
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from education_system.university_system.infrastructure.auth.core import UserAuth
        
        auth = UserAuth()
        
        # AI detector permissions with descriptions
        ai_permissions = [
            ('access_ai_detector', 'Access AI detector functionality'),
            ('analyze_submissions', 'Analyze submissions for AI-generated content'),
            ('view_own_ai_results', 'View AI detection results for own submissions'),
            ('view_any_ai_results', 'View AI detection results for any submission'),
            ('manage_ai_whitelist', 'Manage AI detector whitelist patterns'),
            ('configure_ai_detector', 'Configure AI detector settings'),
            ('view_ai_statistics', 'View AI detection statistics and reports')
        ]
        
        conn = auth._create_configured_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        created_permissions = []
        for perm_name, perm_desc in ai_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                created_permissions.append(perm_name)
        
        # Update role-permission associations for AI permissions
        for role_name, permissions in PERMISSIONS.items():
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if role_result:
                role_id = role_result[0]
                
                for perm_name in permissions:
                    if perm_name in [p[0] for p in ai_permissions]:
                        cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                        perm_result = cursor.fetchone()
                        if perm_result:
                            perm_id = perm_result[0]
                            cursor.execute(
                                'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                                (role_id, perm_id)
                            )
                            if cursor.fetchone()[0] == 0:
                                cursor.execute(
                                    'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                    (role_id, perm_id)
                                )
        
        conn.commit()
        conn.close()
        
        if created_permissions:
            print(f"✅ Created AI permissions: {', '.join(created_permissions)}")
        else:
            logger.info("AI permissions already exist")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Error setting up AI permissions: {e}")
        return False

def verify_ai_detector_setup():
    """Verify that the AI detector is properly set up
    
    Returns:
        bool: True if setup is valid, False otherwise
    """
    try:
        # Check database tables exist
        conn = get_connection()
        cursor = conn.cursor()
        
        required_tables = [
            'ai_detector_submissions',
            'ai_detector_results', 
            'ai_detector_settings',
            'ai_detector_indicators',
            'ai_detector_whitelist'
        ]
        
        missing_tables = []
        for table in required_tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cursor.fetchone():
                missing_tables.append(table)
        
        # Check permissions exist
        ai_permissions = [
            'access_ai_detector', 'analyze_submissions', 'view_own_ai_results',
            'view_any_ai_results', 'manage_ai_whitelist', 'configure_ai_detector',
            'view_ai_statistics'
        ]
        
        missing_permissions = []
        for perm in ai_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm,))
            if cursor.fetchone()[0] == 0:
                missing_permissions.append(perm)
        
        conn.close()
        
        if missing_tables or missing_permissions:
            print(f"❌ AI Detector setup incomplete:")
            if missing_tables:
                print(f"   Missing tables: {', '.join(missing_tables)}")
            if missing_permissions:
                print(f"   Missing permissions: {', '.join(missing_permissions)}")
            return False
        else:
            logger.info("AI Detector setup verified")
            return True

    except sqlite3.Error as e:
        print(f"❌ Database error verifying AI detector setup: {e}")
        return False
    except (KeyError, TypeError) as e:
        print(f"❌ Data error verifying AI detector setup: {e}")
        return False

def add_ai_detector_permissions_to_database(auth_instance):
    """Add AI detector permissions to the database during initialization
    
    Args:
        auth_instance: UserAuth instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(auth_instance.db_path)
        cursor = conn.cursor()
        
        # Define AI detector permissions
        ai_permissions = [
            ('access_ai_detector', 'Access AI detector functionality'),
            ('analyze_submissions', 'Analyze submissions for AI-generated content'),
            ('view_own_ai_results', 'View AI detection results for own submissions'),
            ('view_any_ai_results', 'View AI detection results for any submission'),
            ('manage_ai_whitelist', 'Manage AI detector whitelist patterns'),
            ('configure_ai_detector', 'Configure AI detector settings'),
            ('view_ai_statistics', 'View AI detection statistics')
        ]
        
        # Add each permission if it doesn't exist
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for perm_name, perm_desc in ai_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                logging.info(f"Added permission: {perm_name}")
        
        # Associate permissions with roles
        
        # First, get the permission IDs
        perm_ids = {}
        for perm_name, _ in ai_permissions:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            result = cursor.fetchone()
            if result:
                perm_ids[perm_name] = result[0]
        
        # Define role-permission associations
        role_permissions = {
            'admin': [
                'access_ai_detector', 'analyze_submissions', 'view_own_ai_results', 
                'view_any_ai_results', 'manage_ai_whitelist', 'configure_ai_detector', 
                'view_ai_statistics'
            ],
            'staff': [
                'access_ai_detector', 'analyze_submissions', 
                'view_any_ai_results', 'view_ai_statistics'
            ],
            'instructor': [
                'access_ai_detector', 'analyze_submissions', 
                'view_any_ai_results', 'view_ai_statistics'
            ],
            'student': [
                'access_ai_detector', 'analyze_submissions', 'view_own_ai_results'
            ]
        }
        
        # Add role-permission associations
        for role_name, permissions in role_permissions.items():
            # Get role ID
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if not role_result:
                continue
                
            role_id = role_result[0]
            
            # Add permissions to role
            for perm_name in permissions:
                if perm_name in perm_ids:
                    perm_id = perm_ids[perm_name]
                    
                    # Check if association already exists
                    cursor.execute(
                        'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                        (role_id, perm_id)
                    )
                    
                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                            (role_id, perm_id)
                        )
                        logging.info(f"Added permission {perm_name} to role {role_name}")
        
        conn.commit()
        conn.close()
        
        logging.info("AI detector permissions configured successfully")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Database error adding AI permissions: {e}")
        return False
    except (AttributeError, KeyError) as e:
        logging.error(f"Configuration error adding AI permissions: {e}")
        import traceback
        logging.debug(traceback.format_exc())
        return False

def add_plagiarism_permissions(auth_instance=None):
    """Add plagiarism-related permissions to the database
    
    Args:
        auth_instance: Optional UserAuth instance (unused, kept for compatibility)
        
    Returns:
        List[str]: List of created permission names
    """
    plagiarism_permissions = [
        ('check_plagiarism', 'Check documents for plagiarism'),
        ('manage_plagiarism_system', 'Manage plagiarism checking system settings'),
        ('submit_document', 'Submit documents to the plagiarism repository'),
        ('check_plagiarism_any_course', 'Check plagiarism across all courses'),
        ('access_plagiarism_menu', 'Access the plagiarism checker menu')
    ]
    
    created_permissions = []
    
    try:
        # Use direct database connection to avoid recursion
        conn = get_connection()
        cursor = conn.cursor()
        
        # Add each permission
        for perm_name, perm_desc in plagiarism_permissions:
            try:
                # Check if permission already exists
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                if not cursor.fetchone():
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(
                        'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                        (perm_name, perm_desc, timestamp)
                    )
                    created_permissions.append(perm_name)
                    logging.info(f"Created permission: {perm_name}")
            except sqlite3.Error as e:
                logging.error(f"Error creating permission {perm_name}: {e}")
        
        # Get permission IDs for role assignments
        permission_ids = {}
        for perm_name in [p[0] for p in plagiarism_permissions]:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            result = cursor.fetchone()
            if result:
                permission_ids[perm_name] = result[0]
        
        # Grant permissions to roles
        role_permissions = {
            'admin': ['check_plagiarism', 'manage_plagiarism_system', 'submit_document', 
                     'check_plagiarism_any_course', 'access_plagiarism_menu'],
            'staff': ['check_plagiarism', 'submit_document', 'access_plagiarism_menu'],
            'instructor': ['check_plagiarism', 'submit_document', 'access_plagiarism_menu'],
            'student': ['submit_document', 'access_plagiarism_menu']
        }
        
        for role, perms in role_permissions.items():
            # Get role ID
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
            role_result = cursor.fetchone()
            if not role_result:
                logging.warning(f"Role '{role}' not found, skipping permission assignment")
                continue
                
            role_id = role_result[0]
            
            # Grant permissions
            for perm in perms:
                if perm in permission_ids:
                    perm_id = permission_ids[perm]
                    
                    # Check if permission is already granted
                    cursor.execute(
                        'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                        (role_id, perm_id)
                    )
                    
                    if cursor.fetchone()[0] == 0:
                        try:
                            cursor.execute(
                                'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                (role_id, perm_id)
                            )
                            logging.info(f"Granted permission '{perm}' to role '{role}'")
                        except sqlite3.Error as e:
                            logging.error(f"Error granting {perm} to role {role}: {e}")
        
        conn.commit()
        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error adding plagiarism permissions: {e}")
        return []
    except (KeyError, TypeError) as e:
        logging.error(f"Configuration error adding plagiarism permissions: {e}")
        return []

    return created_permissions

def fix_library_permissions():
    """Fix library permissions for existing database"""
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # All library-related permissions that should exist
    all_library_permissions = [
        ('view_books', 'View Books'),
        ('manage_books', 'Manage Books'),
        ('manage_loans', 'Manage Loans'),
        ('checkout_books', 'Checkout Books'),
        ('view_loans', 'View Loans'),
        ('view_reports', 'View Reports'),
        ('generate_reports', 'Generate Reports'),
        ('system_config', 'System Config'),
        ('manage_reservations', 'Manage Book Reservations'),
        ('manage_reading_lists', 'Manage Reading Lists'),
        ('manage_reviews', 'Manage Book Reviews')
    ]
    
    # Create any missing permissions
    for perm_name, perm_desc in all_library_permissions:
        cursor.execute(
            'INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
            (perm_name, perm_desc, timestamp)
        )
    
    conn.commit()
    print("Created missing library permissions")
    
    # Now assign them to the admin role
    cursor.execute('SELECT id FROM roles WHERE role_name = ?', ('admin',))
    admin_role = cursor.fetchone()
    
    if admin_role:
        admin_role_id = admin_role[0]
        
        for perm_name, _ in all_library_permissions:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            perm = cursor.fetchone()
            
            if perm:
                perm_id = perm[0]
                cursor.execute(
                    'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                    (admin_role_id, perm_id)
                )
        
        conn.commit()
        print("Assigned library permissions to admin role")
    
    # Also assign appropriate permissions to staff
    role_permissions = {
        'staff': ['view_books', 'manage_books', 'manage_loans', 'checkout_books', 
                 'view_loans', 'view_reports', 'manage_reservations', 'manage_reading_lists'],
        'student': ['view_books', 'checkout_books', 'view_loans', 'manage_reading_lists', 'manage_reviews'],
        'instructor': ['view_books', 'checkout_books', 'view_loans', 'manage_reading_lists', 'manage_reviews']
    }
    
    for role_name, permissions in role_permissions.items():
        cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
        role = cursor.fetchone()
        
        if role:
            role_id = role[0]
            
            for perm_name in permissions:
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                perm = cursor.fetchone()
                
                if perm:
                    perm_id = perm[0]
                    cursor.execute(
                        'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                        (role_id, perm_id)
                    )
            
            print(f"Assigned library permissions to {role_name} role")
    
    conn.commit()
    conn.close()
    print("\nLibrary permissions have been fixed!")

# Export public functions
__all__ = [
    'initialize_complete_system',
    'init_trip_db',
    'setup_trip_permissions',
    'set_trip_auth',
    'integrate_trip_management_with_main',
    'add_finance_permissions',
    'fix_alumni_permissions',
    'get_health_role_permissions',
    'add_calendar_permissions',
    'setup_ai_detector_permissions',
    'verify_ai_detector_setup',
    'add_ai_detector_permissions_to_database',
    'add_plagiarism_permissions',
    'fix_library_permissions',
]
