from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import _common
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import get_text, logging, datetime
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management.database import get_db_connection


TRIP_PERMISSIONS = [
    ('manage_trips', 'Manage all trip operations'),
    ('create_trips', 'Create new trips'),
    ('view_trips', 'View trip information'),
    ('register_for_trips', 'Register for trips'),
    ('view_own_trip_registrations', 'View own trip registrations'),
    ('cancel_trip_registration', 'Cancel trip registration'),
    ('manage_trip_participants', 'Manage trip participants'),
    ('view_trip_reports', 'View trip reports'),
    ('manage_trip_expenses', 'Manage trip expenses'),
    ('approve_trip_registrations', 'Approve trip registrations'),
] + [
    # One per approval stage (approvals.STAGE_PERMISSIONS).
    ('approve_trips_department', 'Decide the Department stage of trip approval'),
    ('approve_trips_hs', 'Decide the Health & Safety stage of trip approval, sign off trip risk '
                         'assessments and review trip incidents'),
    ('approve_trips_finance', 'Decide the Finance stage of trip approval'),
    ('approve_trips_international', 'Decide the International stage of trip approval'),
]

TRIP_ROLE_PERMISSIONS = {
    'admin': [
        'manage_trips', 'create_trips', 'view_trips', 'register_for_trips',
        'view_own_trip_registrations', 'cancel_trip_registration',
        'manage_trip_participants', 'view_trip_reports', 'manage_trip_expenses',
        'approve_trip_registrations', 'approve_trips_department', 'approve_trips_hs',
        'approve_trips_finance', 'approve_trips_international'
    ],
    # Staff decide the Department and Finance stages; nobody may decide a
    # trip they created or lead (approvals.decide).
    'staff': [
        'create_trips', 'view_trips', 'manage_trip_participants',
        'view_trip_reports', 'manage_trip_expenses', 'approve_trip_registrations',
        'approve_trips_department', 'approve_trips_finance'
    ],
    # Health & Safety: the H&S coordinators safety_bus notifies.
    'health_admin': [
        'view_trips', 'approve_trips_hs'
    ],
    # Instructors lead trips (Assign Staff offers them; the GUI's is_staff
    # includes them), so they may propose one. manage_trip_expenses /
    # participants stay with staff: a creator or leader manages their own
    # trip through trips.can_manage_trip.
    'instructor': [
        'create_trips', 'view_trips', 'register_for_trips',
        'view_own_trip_registrations', 'cancel_trip_registration'
    ],
    'student': [
        'view_trips', 'register_for_trips', 'view_own_trip_registrations',
        'cancel_trip_registration'
    ]
}

REPORT_PERMISSIONS = [
    ('generate_trip_reports', 'Generate trip reports'),
    ('view_financial_reports', 'View financial trip reports'),
    ('export_participant_data', 'Export participant data'),
    ('generate_comprehensive_reports', 'Generate comprehensive trip reports')
]

REPORT_ROLE_PERMISSIONS = {
    'admin': [
        'generate_trip_reports', 'view_financial_reports',
        'export_participant_data', 'generate_comprehensive_reports'
    ],
    'staff': [
        'generate_trip_reports', 'view_financial_reports',
        'export_participant_data'
    ],
    'instructor': [
        'generate_trip_reports'
    ]
}


def _seed(permissions, role_permissions):
    """Insert missing permissions and role grants in one transaction.

    Returns the names of permissions created, or ``None`` when the database
    could not be opened. The connection is always closed and a failure rolls
    back.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        created_permissions = []
        for perm_name, perm_desc in permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                created_permissions.append(perm_name)

        for role_name, perms in role_permissions.items():
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if not role_result:
                continue
            role_id = role_result[0]
            for perm_name in perms:
                cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                perm_result = cursor.fetchone()
                if perm_result:
                    cursor.execute(
                        'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                        (role_id, perm_result[0])
                    )

        conn.commit()
        return created_permissions
    except Exception:
        try:
            conn.rollback()
        except Exception:
            logging.debug("Rollback failed", exc_info=True)
        raise
    finally:
        conn.close()


def setup_trip_permissions(auth=None):
    """Setup trip management permissions"""
    try:
        created_permissions = _seed(TRIP_PERMISSIONS, TRIP_ROLE_PERMISSIONS)
        if created_permissions is None:
            return False
        if created_permissions:
            print(get_text("mobility.trip_management.permissions.created", "Created trip permissions: {permissions}").format(permissions=', '.join(created_permissions)))
        return True

    except Exception as e:
        logging.error(get_text("mobility.trip_management.permissions.setup_error", "Error setting up trip permissions: {error}").format(error=e))
        return False


def setup_report_permissions():
    """Setup additional permissions for report generation"""
    try:
        created_permissions = _seed(REPORT_PERMISSIONS, REPORT_ROLE_PERMISSIONS)
        if created_permissions is None:
            return False
        if created_permissions:
            print(get_text("mobility.trip_management.permissions.report_created", "Created report permissions: {permissions}").format(permissions=', '.join(created_permissions)))
        return True

    except Exception as e:
        logging.error(get_text("mobility.trip_management.permissions.report_setup_error", "Error setting up report permissions: {error}").format(error=e))
        return False
