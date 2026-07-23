from education_system.post_18.university_system.modules.domain.campus.mobility.services.trip_management import _common
from education_system.post_18.university_system.modules.domain.campus.mobility.services.trip_management._common import get_text, logging, datetime
from education_system.post_18.university_system.modules.domain.campus.mobility.services.trip_management.database import get_db_connection


def setup_trip_permissions(auth=None):
    """Setup trip management permissions"""
    try:
        # Import auth functions from the refactored authentication module
        from education_system.post_18.university_system.infrastructure.auth import UserAuth
        if auth is None:
            auth = UserAuth()

        trip_permissions = [
            ('manage_trips', 'Manage all trip operations'),
            ('create_trips', 'Create new trips'),
            ('view_trips', 'View trip information'),
            ('register_for_trips', 'Register for trips'),
            ('view_own_trip_registrations', 'View own trip registrations'),
            ('cancel_trip_registration', 'Cancel trip registration'),
            ('manage_trip_participants', 'Manage trip participants'),
            ('view_trip_reports', 'View trip reports'),
            ('manage_trip_expenses', 'Manage trip expenses'),
            ('approve_trip_registrations', 'Approve trip registrations')
        ]

        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        created_permissions = []
        for perm_name, perm_desc in trip_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                created_permissions.append(perm_name)

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

        if created_permissions:
            print(get_text("mobility.trip_management.permissions.created", "Created trip permissions: {permissions}").format(permissions=', '.join(created_permissions)))

        return True

    except Exception as e:
        logging.error(get_text("mobility.trip_management.permissions.setup_error", "Error setting up trip permissions: {error}").format(error=e))
        return False


def setup_report_permissions():
    """Setup additional permissions for report generation"""
    try:
        from education_system.post_18.university_system.infrastructure.auth import UserAuth

        report_permissions = [
            ('generate_trip_reports', 'Generate trip reports'),
            ('view_financial_reports', 'View financial trip reports'),
            ('export_participant_data', 'Export participant data'),
            ('generate_comprehensive_reports', 'Generate comprehensive trip reports')
        ]

        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        created_permissions = []
        for perm_name, perm_desc in report_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
                created_permissions.append(perm_name)

        # Assign permissions to roles
        role_permissions = {
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

        if created_permissions:
            print(get_text("mobility.trip_management.permissions.report_created", "Created report permissions: {permissions}").format(permissions=', '.join(created_permissions)))

        return True

    except Exception as e:
        logging.error(get_text("mobility.trip_management.permissions.report_setup_error", "Error setting up report permissions: {error}").format(error=e))
        return False
