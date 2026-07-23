#!/usr/bin/env python3
"""
Test MFA Unique Contacts Enforcement
Verifies that email addresses and phone numbers can only be linked to one user account.
"""

import sys
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime

from education_system.post_18.university_system.infrastructure.auth.mfa_service import MFAService

def test_unique_email_enforcement():
    """Test that email addresses must be unique across users"""
    print("\n" + "="*80)
    print("TEST 1: Email Uniqueness Enforcement")
    print("="*80)

    service = MFAService()

    # Simulate User 1 registering email for MFA
    print("\n1. User 1 (ID: 100) registers email: admin@university.edu")
    result1 = service.generate_email_otp(100, "admin@university.edu")

    if result1['success']:
        print("   ✓ User 1 successfully registered email for MFA")
    else:
        print(f"   ✗ Failed: {result1.get('error')}")
        return False

    # Simulate User 2 trying to register the SAME email
    print("\n2. User 2 (ID: 200) attempts to register SAME email: admin@university.edu")
    result2 = service.generate_email_otp(200, "admin@university.edu")

    if not result2['success'] and 'already registered' in result2.get('error', '').lower():
        print("   ✓ CORRECTLY REJECTED - Email already in use")
        print(f"   ✓ Error message: {result2['error']}")
    else:
        print(f"   ✗ FAILED - Should have rejected duplicate email")
        print(f"   ✗ Result: {result2}")
        return False

    # User 1 can update their own email
    print("\n3. User 1 (ID: 100) updates to different email: admin2@university.edu")
    result3 = service.generate_email_otp(100, "admin2@university.edu")

    if result3['success']:
        print("   ✓ User 1 successfully updated their email")
    else:
        print(f"   ✗ Failed: {result3.get('error')}")
        return False

    # Now User 2 can register the previously used email (since User 1 no longer uses it)
    print("\n4. User 2 (ID: 200) can now register the freed email: admin@university.edu")
    result4 = service.generate_email_otp(200, "admin@university.edu")

    if result4['success']:
        print("   ✓ User 2 successfully registered freed email")
    else:
        print(f"   ✗ Failed: {result4.get('error')}")
        return False

    print("\n✅ Email uniqueness test PASSED")
    return True

def test_unique_phone_enforcement():
    """Test that phone numbers must be unique across users"""
    print("\n" + "="*80)
    print("TEST 2: Phone Number Uniqueness Enforcement")
    print("="*80)

    service = MFAService()

    # Simulate User 3 registering phone for MFA
    print("\n1. User 3 (ID: 300) registers phone: +447700900123")
    result1 = service.generate_sms_otp(300, "+447700900123")

    if result1['success']:
        print("   ✓ User 3 successfully registered phone for MFA")
    else:
        print(f"   ✗ Failed: {result1.get('error')}")
        return False

    # Simulate User 4 trying to register the SAME phone
    print("\n2. User 4 (ID: 400) attempts to register SAME phone: +447700900123")
    result2 = service.generate_sms_otp(400, "+447700900123")

    if not result2['success'] and 'already registered' in result2.get('error', '').lower():
        print("   ✓ CORRECTLY REJECTED - Phone already in use")
        print(f"   ✓ Error message: {result2['error']}")
    else:
        print(f"   ✗ FAILED - Should have rejected duplicate phone")
        print(f"   ✗ Result: {result2}")
        return False

    # User 3 can update their own phone
    print("\n3. User 3 (ID: 300) updates to different phone: +447700900456")
    result3 = service.generate_sms_otp(300, "+447700900456")

    if result3['success']:
        print("   ✓ User 3 successfully updated their phone")
    else:
        print(f"   ✗ Failed: {result3.get('error')}")
        return False

    print("\n✅ Phone uniqueness test PASSED")
    return True

def test_update_mfa_method_uniqueness():
    """Test that update_mfa_method also enforces uniqueness"""
    print("\n" + "="*80)
    print("TEST 3: Update MFA Method Uniqueness")
    print("="*80)

    service = MFAService()

    # Setup: User 5 has email
    print("\n1. User 5 (ID: 500) registers email: staff@university.edu")
    result1 = service.update_mfa_method(500, 'email', "staff@university.edu")

    if result1['success']:
        print("   ✓ User 5 registered email via update_mfa_method")
    else:
        print(f"   ✗ Failed: {result1.get('error')}")
        return False

    # User 6 tries to use same email via update_mfa_method
    print("\n2. User 6 (ID: 600) attempts to use SAME email via update: staff@university.edu")
    result2 = service.update_mfa_method(600, 'email', "staff@university.edu")

    if not result2['success'] and 'already registered' in result2.get('error', '').lower():
        print("   ✓ CORRECTLY REJECTED via update_mfa_method")
        print(f"   ✓ Error message: {result2['error']}")
    else:
        print(f"   ✗ FAILED - Should have rejected duplicate email")
        print(f"   ✗ Result: {result2}")
        return False

    print("\n✅ Update method uniqueness test PASSED")
    return True

def test_cross_user_scenario():
    """Test realistic cross-user scenario"""
    print("\n" + "="*80)
    print("TEST 4: Realistic Cross-User Scenario")
    print("="*80)

    service = MFAService()

    print("\nScenario: Admin and Staff trying to use same contact info")
    print("-" * 80)

    # Admin user sets up MFA
    print("\n1. Admin (ID: 1) sets up MFA with email: security@university.edu")
    result1 = service.generate_email_otp(1, "security@university.edu")

    if result1['success']:
        print("   ✓ Admin successfully set up email MFA")
    else:
        print(f"   ✗ Failed: {result1.get('error')}")
        return False

    print("\n2. Admin (ID: 1) also sets up SMS MFA: +447700900999")
    result2 = service.generate_sms_otp(1, "+447700900999")

    if result2['success']:
        print("   ✓ Admin successfully set up SMS MFA")
    else:
        print(f"   ✗ Failed: {result2.get('error')}")
        return False

    # Staff user tries to use admin's email
    print("\n3. Staff (ID: 2) attempts to use Admin's email: security@university.edu")
    result3 = service.generate_email_otp(2, "security@university.edu")

    if not result3['success']:
        print("   ✓ BLOCKED - Cannot use Admin's email")
    else:
        print("   ✗ FAILED - Should have blocked")
        return False

    # Staff user tries to use admin's phone
    print("\n4. Staff (ID: 2) attempts to use Admin's phone: +447700900999")
    result4 = service.generate_sms_otp(2, "+447700900999")

    if not result4['success']:
        print("   ✓ BLOCKED - Cannot use Admin's phone")
    else:
        print("   ✗ FAILED - Should have blocked")
        return False

    # Staff sets up their own unique contacts
    print("\n5. Staff (ID: 2) sets up their own email: staff2@university.edu")
    result5 = service.generate_email_otp(2, "staff2@university.edu")

    if result5['success']:
        print("   ✓ Staff successfully set up unique email")
    else:
        print(f"   ✗ Failed: {result5.get('error')}")
        return False

    print("\n✅ Cross-user scenario test PASSED")
    return True

def cleanup_test_data():
    """Clean up test MFA records"""
    print("\n" + "="*80)
    print("Cleaning up test data...")
    print("="*80)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Remove test user MFA records
        test_user_ids = [100, 200, 300, 400, 500, 600, 1, 2]

        for user_id in test_user_ids:
            cursor.execute("DELETE FROM mfa_methods WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM mfa_otp_codes WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM mfa_user_settings WHERE user_id = ?", (user_id,))

        conn.commit()
        print("✓ Test data cleaned up successfully")
        return True

    except Exception as e:
        conn.rollback()
        print(f"✗ Cleanup failed: {e}")
        return False
    finally:
        conn.close()

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("MFA UNIQUE CONTACTS ENFORCEMENT TEST SUITE")
    print("="*80)
    print("Database: (isolated test DB)")
    print(f"Time: {datetime.now().isoformat()}")

    # Clean up any existing test data
    cleanup_test_data()

    # Run tests
    tests = [
        ("Email Uniqueness", test_unique_email_enforcement),
        ("Phone Uniqueness", test_unique_phone_enforcement),
        ("Update Method Uniqueness", test_update_mfa_method_uniqueness),
        ("Cross-User Scenario", test_cross_user_scenario),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Clean up test data
    cleanup_test_data()

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print("\n" + "="*80)
    print(f"Results: {passed}/{total} tests passed")
    print("="*80)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! MFA uniqueness enforcement is working correctly.")
        return True
    else:
        print("\n⚠️  SOME TESTS FAILED! Please review the output above.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
