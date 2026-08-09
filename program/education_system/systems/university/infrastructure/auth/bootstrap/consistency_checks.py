"""Legacy authentication integration and consistency checks."""
import traceback

from ..facade import UserAuth

def test_authentication_fix():
    """Run diagnostics against authentication data without seeding demo users."""
    print("=== AUTHENTICATION DATA CHECK ===")

    auth = UserAuth()

    # Summarise role coverage
    auth.verify_default_accounts()
    auth.ensure_staff_account_exists()

    # Inspect for orphaned records and locked accounts
    with auth.db_manager.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            '''
            SELECT COUNT(*)
            FROM users u
            LEFT JOIN user_accounts ua ON u.id = ua.user_id
            WHERE ua.user_id IS NULL
            '''
        )
        orphan_count = cursor.fetchone()[0]
        if orphan_count:
            print(f"⚠️  {orphan_count} user record(s) do not have login accounts. Call fix_missing_accounts() if appropriate.")
        else:
            print("✓ All user records have corresponding login accounts.")

        cursor.execute("SELECT COUNT(*) FROM user_accounts WHERE is_active = 0")
        locked_accounts = cursor.fetchone()[0]
        if locked_accounts:
            print(f"⚠️  {locked_accounts} account(s) are marked inactive.")
        else:
            print("✓ No inactive accounts detected.")

def test_authentication_with_ai_detector():
    """Summarise AI detector permissions without relying on seeded accounts."""
    print("=== TESTING AI DETECTOR PERMISSIONS ===")

    try:
        auth = UserAuth()

        ai_permissions = [
            'access_ai_detector',
            'analyze_submissions',
            'view_own_ai_results',
            'view_any_ai_results',
            'manage_ai_whitelist',
            'configure_ai_detector',
            'view_ai_statistics',
        ]

        with auth.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT permission_name
                FROM permissions
                WHERE permission_name IN ({})
                '''.format(','.join('?' for _ in ai_permissions)),
                ai_permissions,
            )
            present_perms = {row[0] for row in cursor.fetchall()}
            missing_perms = sorted(set(ai_permissions) - present_perms)

            if missing_perms:
                print(f"❌ Missing AI detector permissions: {', '.join(missing_perms)}")
            else:
                print("✓ All AI detector permissions are registered.")

            cursor.execute(
                '''
                SELECT DISTINCT u.username, u.role
                FROM user_accounts ua
                JOIN users u ON ua.user_id = u.id
                JOIN roles r ON r.role_name = u.role
                JOIN role_permissions rp ON rp.role_id = r.id
                JOIN permissions p ON p.id = rp.permission_id
                WHERE p.permission_name IN ({})
                ORDER BY u.role, u.username
                '''.format(','.join('?' for _ in ai_permissions)),
                ai_permissions,
            )
            rows = cursor.fetchall()

            if rows:
                print("\nUsers currently mapped to AI detector permissions:")
                for username, role in rows:
                    print(f"• {username} ({role})")
            else:
                print("\n⚠️  No user accounts are currently mapped to AI detector permissions.")

    except Exception as e:
        print(f"❌ Error testing AI detector permissions: {e}")
        traceback.print_exc()

def test_plagiarism_authentication():
    """Test plagiarism system authentication"""
    print("=== TESTING PLAGIARISM AUTHENTICATION ===")

    try:
        auth = UserAuth()

        plagiarism_permissions = [
            'check_plagiarism',
            'manage_plagiarism_system',
            'submit_document',
            'check_plagiarism_any_course',
            'access_plagiarism_menu',
        ]

        with auth.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT permission_name
                FROM permissions
                WHERE permission_name IN ({})
                '''.format(','.join('?' for _ in plagiarism_permissions)),
                plagiarism_permissions,
            )
            present_perms = {row[0] for row in cursor.fetchall()}
            missing_perms = sorted(set(plagiarism_permissions) - present_perms)

            if missing_perms:
                print(f"❌ Missing plagiarism permissions: {', '.join(missing_perms)}")
            else:
                print("✓ All plagiarism permissions are registered.")

    except Exception as e:
        print(f"❌ Error testing plagiarism permissions: {e}")
        traceback.print_exc()

def simple_login_test(username=None, password=None):
    """Simple login test function"""
    auth = UserAuth()

    if username is None:
        username = input("Username: ")
    if password is None:
        import getpass
        password = getpass.getpass("Password: ")

    result = auth.login(username, password)

    if result.get('success'):
        print(f"✓ Login successful! Welcome, {result['user']['first_name']}!")
        print(f"Role: {result['user']['role']}")
        print(f"Permissions: {len(result['user'].get('permissions', []))} permission(s)")
    else:
        print(f"✗ Login failed: {result.get('error')}")

    return auth

def test_trip_integration():
    """Test trip management integration"""
    print("=== TESTING TRIP INTEGRATION ===")

    try:
        auth = UserAuth()

        trip_permissions = [
            'manage_trips',
            'create_trips',
            'view_trips',
            'register_for_trips',
            'view_own_trip_registrations',
            'cancel_trip_registration',
        ]

        with auth.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                '''
                SELECT permission_name
                FROM permissions
                WHERE permission_name IN ({})
                '''.format(','.join('?' for _ in trip_permissions)),
                trip_permissions,
            )
            present_perms = {row[0] for row in cursor.fetchall()}
            missing_perms = sorted(set(trip_permissions) - present_perms)

            if missing_perms:
                print(f"❌ Missing trip permissions: {', '.join(missing_perms)}")
            else:
                print("✓ All trip permissions are registered.")

    except Exception as e:
        print(f"❌ Error testing trip permissions: {e}")
        traceback.print_exc()

def quick_test_integration():
    """Quick integration test"""
    print("=== QUICK INTEGRATION TEST ===")

    try:
        auth = UserAuth()
        print("✓ UserAuth initialized successfully")

        # Test login with default admin
        from education_system.systems.university.infrastructure.defaults import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
        result = auth.login(DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD)
        if result.get('success'):
            print("✓ Admin login successful")
            auth.logout()
            print("✓ Logout successful")
        else:
            print(f"✗ Admin login failed: {result.get('error')}")

        print("\n✅ Quick integration test completed!")

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        traceback.print_exc()
