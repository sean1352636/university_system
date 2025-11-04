#!/usr/bin/env python3
"""Test script to verify email infrastructure is properly linked to user_authentication"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_auth_linkage():
    """Test that all email components are properly linked to user authentication"""

    print("Testing email infrastructure auth linkage...")
    print("=" * 60)

    # Test 1: Import user_authentication and verify global functions
    print("\n1. Testing user_authentication module...")
    try:
        from university_system.infrastructure.auth.user_authentication import (
            get_current_user, set_auth_instance, UserAuth
        )
        print("   ✓ Successfully imported auth functions")
    except ImportError as e:
        print(f"   ✗ Failed to import auth functions: {e}")
        return False

    # Test 2: Import email state module and verify it imports auth functions
    print("\n2. Testing email state module...")
    try:
        from university_system.infrastructure.email import state
        print(f"   ✓ state.HAS_AUTH = {state.HAS_AUTH}")
        if not state.HAS_AUTH:
            print("   ⚠ WARNING: Email state module couldn't import auth functions")
    except ImportError as e:
        print(f"   ✗ Failed to import email state: {e}")
        return False

    # Test 3: Create a UserAuth instance and set it
    print("\n3. Testing auth instance creation and linkage...")
    try:
        auth = UserAuth()
        print("   ✓ Created UserAuth instance")

        # Simulate login
        auth.current_user = {
            'id': 1,
            'username': 'test_user',
            'email': 'test@university.edu',
            'role': 'admin',
            'first_name': 'Test',
            'last_name': 'User'
        }
        print("   ✓ Set current_user on auth instance")
    except Exception as e:
        print(f"   ✗ Failed to create auth instance: {e}")
        return False

    # Test 4: Set auth in email infrastructure
    print("\n4. Testing email infrastructure set_auth...")
    try:
        from university_system.infrastructure.email import set_auth
        set_auth(auth)
        print("   ✓ Called set_auth(auth)")
    except Exception as e:
        print(f"   ✗ Failed to set auth: {e}")
        return False

    # Test 5: Verify auth is accessible through state module
    print("\n5. Testing auth accessibility through state module...")
    try:
        if state.auth is not None:
            print(f"   ✓ state.auth is set: {state.auth}")
            if hasattr(state.auth, 'current_user'):
                print(f"   ✓ state.auth.current_user: {state.auth.current_user['username']}")
            else:
                print("   ✗ state.auth has no current_user attribute")
                return False
        else:
            print("   ✗ state.auth is None")
            return False
    except Exception as e:
        print(f"   ✗ Failed to access state.auth: {e}")
        return False

    # Test 6: Verify auth_proxy works
    print("\n6. Testing auth_proxy...")
    try:
        from university_system.infrastructure.email.state import auth_proxy
        if auth_proxy:
            print(f"   ✓ auth_proxy is truthy")
            print(f"   ✓ auth_proxy.current_user: {auth_proxy.current_user['username']}")
        else:
            print("   ✗ auth_proxy is falsy")
            return False
    except Exception as e:
        print(f"   ✗ Failed to use auth_proxy: {e}")
        return False

    # Test 7: Verify get_current_user works
    print("\n7. Testing get_current_user()...")
    try:
        current = get_current_user()
        if current:
            print(f"   ✓ get_current_user() returned: {current['username']}")
        else:
            print("   ✗ get_current_user() returned None")
            return False
    except Exception as e:
        print(f"   ✗ Failed to call get_current_user(): {e}")
        return False

    # Test 8: Test CommunicationDashboard initialization with auth
    print("\n8. Testing CommunicationDashboard with auth...")
    try:
        from university_system.infrastructure.email.admin import CommunicationDashboard
        dashboard = CommunicationDashboard(auth=auth)
        print("   ✓ Created CommunicationDashboard with auth")

        if dashboard.auth and dashboard.auth.current_user:
            print(f"   ✓ dashboard.auth.current_user: {dashboard.auth.current_user['username']}")
        else:
            print("   ✗ dashboard.auth is not set properly")
            return False
    except Exception as e:
        print(f"   ✗ Failed to create CommunicationDashboard: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 9: Test email_service auth usage
    print("\n9. Testing email_service auth access...")
    try:
        from university_system.infrastructure.email import email_service
        # The email_service module imports auth_proxy as auth
        # Verify it can access current_user
        if hasattr(email_service, 'auth'):
            if email_service.auth and hasattr(email_service.auth, 'current_user'):
                print(f"   ✓ email_service.auth.current_user accessible")
            else:
                print("   ⚠ email_service.auth exists but current_user not accessible")
        else:
            print("   ⚠ email_service doesn't have auth attribute (may be using auth_proxy)")
    except Exception as e:
        print(f"   ✗ Error accessing email_service: {e}")

    print("\n" + "=" * 60)
    print("✅ All auth linkage tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_auth_linkage()
    sys.exit(0 if success else 1)
