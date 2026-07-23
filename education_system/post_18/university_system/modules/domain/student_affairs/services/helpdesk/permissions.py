from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime


def setup_enhanced_helpdesk_permissions():
    """Setup enhanced helpdesk permissions"""
    conn = get_connection()
    cursor = conn.cursor()

    # Check if the permissions table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='permissions'")
    if not cursor.fetchone():
        print("Permissions table not found. Please initialize the user authentication system first.")
        conn.close()
        return

    # Add enhanced helpdesk permissions
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        permissions = [
            ('create_ticket', 'Can create support tickets'),
            ('view_own_tickets', 'Can view own support tickets'),
            ('reply_to_own_ticket', 'Can reply to own support tickets'),
            ('view_all_tickets', 'Can view all support tickets'),
            ('reply_to_any_ticket', 'Can reply to any support tickets'),
            ('manage_tickets', 'Can manage ticket status and priority'),
            ('manage_sla', 'Can manage SLA policies'),
            ('manage_workflows', 'Can manage automated workflows'),
            ('manage_kb', 'Can manage knowledge base articles'),
            ('view_analytics', 'Can view analytics and reports'),
            ('manage_departments', 'Can manage departments'),
            ('manage_organizations', 'Can manage organizations'),
            ('bulk_operations', 'Can perform bulk ticket operations'),
            ('system_admin', 'Full system administration access')
        ]

        # Add permissions if they don't already exist
        for perm_name, perm_desc in permissions:
            cursor.execute(
                "SELECT COUNT(*) FROM permissions WHERE permission_name = ?",
                (perm_name,)
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)",
                    (perm_name, perm_desc, timestamp)
                )

        # Associate permissions with roles
        # Student role permissions
        cursor.execute("SELECT id FROM roles WHERE role_name = 'student'")
        student_role_id = cursor.fetchone()

        if student_role_id:
            student_perms = ['create_ticket', 'view_own_tickets', 'reply_to_own_ticket']
            for perm in student_perms:
                cursor.execute("SELECT id FROM permissions WHERE permission_name = ?", (perm,))
                perm_id = cursor.fetchone()
                if perm_id:
                    cursor.execute(
                        "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                        (student_role_id[0], perm_id[0])
                    )

        # Staff role permissions
        cursor.execute("SELECT id FROM roles WHERE role_name = 'staff'")
        staff_role_id = cursor.fetchone()

        if staff_role_id:
            staff_perms = ['create_ticket', 'view_own_tickets', 'reply_to_own_ticket',
                          'view_all_tickets', 'reply_to_any_ticket', 'manage_tickets']
            for perm in staff_perms:
                cursor.execute("SELECT id FROM permissions WHERE permission_name = ?", (perm,))
                perm_id = cursor.fetchone()
                if perm_id:
                    cursor.execute(
                        "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                        (staff_role_id[0], perm_id[0])
                    )

        # Admin role permissions (all permissions)
        cursor.execute("SELECT id FROM roles WHERE role_name = 'admin'")
        admin_role_id = cursor.fetchone()

        if admin_role_id:
            cursor.execute("SELECT id FROM permissions")
            all_permissions = cursor.fetchall()

            for perm_id in all_permissions:
                cursor.execute(
                    "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                    (admin_role_id[0], perm_id[0])
                )

        conn.commit()
        print("Enhanced helpdesk permissions setup successfully!")

    except sqlite3.Error as e:
        print(f"Error setting up enhanced helpdesk permissions: {e}")
    finally:
        conn.close()
