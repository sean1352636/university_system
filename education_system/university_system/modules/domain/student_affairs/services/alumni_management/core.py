from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
import time
import threading
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

DB_PATH = str(paths.DEFAULT_DB_PATH)

# Use this function for all DB operations safely
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

# Retry wrapper for locked DB
def safe_execute(cursor, query, params=(), retries=3, delay=1.0):
    for attempt in range(retries):
        try:
            cursor.execute(query, params)
            return
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e).lower():
                print(f"[Retry] DB locked, retrying ({attempt+1}/{retries})...")
                time.sleep(delay)
            else:
                raise
    raise sqlite3.OperationalError("DB is locked after multiple retries.")

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# Thread-safe auth instance management
_auth = None
_auth_lock = threading.Lock()


def get_auth():
    """Get the auth instance in a thread-safe manner."""
    with _auth_lock:
        return _auth


def set_auth(auth_instance):
    """Set the auth instance in a thread-safe manner."""
    global _auth
    with _auth_lock:
        _auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)


# Backward compatibility: 'auth' property for legacy code
# NOTE: Direct access to 'auth' is deprecated; use get_auth() instead
class _AuthProxy:
    """Proxy class for backward-compatible 'auth' global access."""
    def __getattr__(self, name):
        instance = get_auth()
        if instance is None:
            return None
        return getattr(instance, name)

    def __bool__(self):
        return get_auth() is not None


auth = _AuthProxy()

# Enhanced permissions setup for all new features
def setup_alumni_permissions():
    permissions = [
        # Original permissions
        ('manage_alumni', 'Manage alumni records and profiles'),
        ('view_alumni', 'View all alumni records'),
        ('view_own_alumni_profile', 'View own alumni profile'),
        ('make_donation', 'Make donations to the institution'),
        ('view_own_donations', 'View own donation history'),
        ('manage_mentorships', 'Manage alumni-student mentorship programs'),

        # New feature permissions
        ('access_alumni_directory', 'Access public alumni directory'),
        ('manage_alumni_directory', 'Manage alumni directory settings'),
        ('send_newsletters', 'Send newsletters and bulk communications'),
        ('manage_communication', 'Manage communication system'),
        ('post_jobs', 'Post job opportunities'),
        ('view_job_board', 'View job board'),
        ('manage_job_board', 'Manage job board system'),
        ('schedule_career_counseling', 'Schedule career counseling sessions'),
        ('provide_career_counseling', 'Provide career counseling services'),
        ('manage_events_advanced', 'Advanced event management features'),
        ('process_payments', 'Process event and donation payments'),
        ('manage_campaigns', 'Manage fundraising campaigns'),
        ('view_analytics', 'View analytics and reports'),
        ('manage_social_features', 'Manage social features and engagement'),
        ('moderate_forum', 'Moderate alumni forum discussions'),
        ('manage_integrations', 'Manage system integrations'),
        ('admin_security', 'Administer security settings'),
        ('view_audit_logs', 'View system audit logs'),
        ('manage_ai_features', 'Manage AI-powered features'),
        ('manage_gamification', 'Manage gamification features'),
        ('manage_content', 'Manage content and publications'),
        ('ambassador_program', 'Participate in ambassador program'),
        ('manage_ambassadors', 'Manage ambassador program')
    ]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for perm, desc in permissions:
            safe_execute(cursor, '''
                INSERT OR IGNORE INTO permissions (permission_name, description, created_at)
                VALUES (?, ?, ?)''', (perm, desc, timestamp))

        # Enhanced role mappings
        role_mappings = {
            'admin': [p[0] for p in permissions],  # Admin gets all permissions
            'staff': [
                'manage_alumni', 'view_alumni', 'manage_alumni_directory',
                'send_newsletters', 'manage_communication', 'manage_job_board',
                'provide_career_counseling', 'manage_events_advanced',
                'process_payments', 'manage_campaigns', 'view_analytics',
                'manage_social_features', 'moderate_forum', 'manage_ambassadors'
            ],
            'student': [
                'view_own_alumni_profile', 'make_donation', 'view_own_donations',
                'access_alumni_directory', 'view_job_board', 'schedule_career_counseling'
            ],
            'alumni': [
                'view_own_alumni_profile', 'make_donation', 'view_own_donations',
                'access_alumni_directory', 'post_jobs', 'view_job_board',
                'schedule_career_counseling', 'ambassador_program'
            ],
            'parent': ['access_alumni_directory', 'view_job_board'],
            'instructor': [
                'view_alumni', 'access_alumni_directory', 'manage_job_board',
                'provide_career_counseling', 'view_analytics'
            ]
        }

        for role, perms in role_mappings.items():
            safe_execute(cursor, 'SELECT id FROM roles WHERE role_name = ?', (role,))
            role_result = cursor.fetchone()
            if not role_result:
                continue
            role_id = role_result[0]

            for perm in perms:
                safe_execute(cursor, 'SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                perm_result = cursor.fetchone()
                if perm_result:
                    perm_id = perm_result[0]
                    safe_execute(cursor, '''
                        INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                        VALUES (?, ?)''', (role_id, perm_id))

        conn.commit()
        print("Enhanced alumni permissions and role mappings set up successfully.")
