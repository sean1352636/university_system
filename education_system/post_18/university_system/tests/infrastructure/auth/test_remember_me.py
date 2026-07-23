#!/usr/bin/env python3
"""
Test script for Remember Me functionality

This script tests the remember me feature in both GUI and CLI contexts.
"""

import sys


def test_remember_me_token_operations():
    """Test token save/load/clear operations"""
    print("\n" + "="*60)
    print("Testing Remember Me Token Operations")
    print("="*60)

    try:
        from education_system.post_18.university_system.infrastructure.auth.managers.session_manager import (
            save_cli_remember_token,
            load_cli_remember_token,
            clear_cli_remember_token
        )

        # Test save
        print("\n1. Testing token save...")
        save_cli_remember_token("test_user", "test_token_123", "device_abc")
        print("   ✅ Token saved successfully")

        # Test load
        print("\n2. Testing token load...")
        data = load_cli_remember_token()
        if data and data['username'] == 'test_user':
            print(f"   ✅ Token loaded: username={data['username']}")
        else:
            print("   ❌ Token load failed")
            return False

        # Test clear
        print("\n3. Testing token clear...")
        clear_cli_remember_token()
        data = load_cli_remember_token()
        if data is None:
            print("   ✅ Token cleared successfully")
        else:
            print("   ❌ Token clear failed")
            return False

        return True

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_enhanced_auth_availability():
    """Test if EnhancedAuth is available"""
    print("\n" + "="*60)
    print("Testing EnhancedAuth Availability")
    print("="*60)

    try:
        from education_system.post_18.university_system.infrastructure.auth.enhanced_auth import (
            EnhancedAuth,
            create_enhanced_auth
        )
        print("   ✅ EnhancedAuth module available")

        # Try to create instance
        auth = create_enhanced_auth()
        print(f"   ✅ EnhancedAuth instance created: {type(auth).__name__}")

        return True

    except ImportError as e:
        print(f"   ❌ EnhancedAuth not available: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error creating EnhancedAuth: {e}")
        return False


def test_remember_me_manager():
    """Test RememberMeManager functionality"""
    print("\n" + "="*60)
    print("Testing RememberMeManager")
    print("="*60)

    try:
        from education_system.post_18.university_system.infrastructure.security.remember_me import (
            remember_me_manager
        )

        print("   ✅ RememberMeManager available")

        # Test database initialization
        remember_me_manager.initialize_database()
        print("   ✅ Database initialized")

        # Test token creation
        token = remember_me_manager.create_token(
            user_id=1,
            device_fingerprint="test_device",
            ip_address="127.0.0.1"
        )

        if token:
            print(f"   ✅ Token created: {token[:16]}...")

            # Test token verification
            user_id = remember_me_manager.verify_and_rotate_token(
                token=token,
                device_fingerprint="test_device",
                ip_address="127.0.0.1"
            )

            if user_id:
                print(f"   ✅ Token verified for user_id: {user_id}")

                # Test token revocation
                count = remember_me_manager.revoke_all_user_tokens(user_id)
                print(f"   ✅ Revoked {count} token(s)")
            else:
                print("   ❌ Token verification failed")
                return False
        else:
            print("   ❌ Token creation failed")
            return False

        return True

    except ImportError as e:
        print(f"   ❌ RememberMeManager not available: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_security_integration():
    """Test SecurityManager integration"""
    print("\n" + "="*60)
    print("Testing Security Integration")
    print("="*60)

    try:
        from education_system.post_18.university_system.infrastructure.security import (
            get_security_manager,
            REMEMBER_ME_AVAILABLE,
            SECURITY_INTEGRATION_AVAILABLE
        )

        print(f"   Remember Me Available: {REMEMBER_ME_AVAILABLE}")
        print(f"   Security Integration Available: {SECURITY_INTEGRATION_AVAILABLE}")

        if SECURITY_INTEGRATION_AVAILABLE:
            security = get_security_manager()
            status = security.get_security_status()

            print("\n   Security Component Status:")
            for component, available in status.items():
                icon = "✅" if available else "❌"
                print(f"      {icon} {component}: {available}")

            return True
        else:
            print("   ❌ Security integration not available")
            return False

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("REMEMBER ME FUNCTIONALITY TEST SUITE")
    print("="*60)

    results = {
        "Token Operations": test_remember_me_token_operations(),
        "EnhancedAuth Availability": test_enhanced_auth_availability(),
        "RememberMeManager": test_remember_me_manager(),
        "Security Integration": test_security_integration(),
    }

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = 0
    failed = 0

    for test_name, result in results.items():
        icon = "✅ PASS" if result else "❌ FAIL"
        print(f"{icon} - {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n🎉 All tests passed! Remember me functionality is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
