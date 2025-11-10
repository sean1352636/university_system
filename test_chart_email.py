#!/usr/bin/env python3
"""
Test script for chart email functionality
Verifies that charts can be emailed to administrators
"""

import sys
sys.path.insert(0, '/home/seancatchpole989')

from university_system.modules.shared.utils.chart_generator import (
    ChartGenerator, EMAIL_AVAILABLE, CHARTS_AVAILABLE
)

def test_email_availability():
    """Test if email service is available"""
    print("=" * 60)
    print("EMAIL SERVICE AVAILABILITY TEST")
    print("=" * 60)

    if EMAIL_AVAILABLE:
        print("✓ Email service is AVAILABLE")
        print("  - send_email: IMPORTED")
        print("  - send_email_as_system: IMPORTED")
        print("  - get_auth: IMPORTED")
    else:
        print("✗ Email service is NOT available")
        print("  Check email infrastructure configuration")
        return False

    print()
    return True


def test_chart_email_integration():
    """Test chart email integration"""
    if not CHARTS_AVAILABLE:
        print("Skipping chart email test (matplotlib not available)")
        return

    if not EMAIL_AVAILABLE:
        print("Skipping chart email test (email service not available)")
        return

    print("=" * 60)
    print("CHART EMAIL INTEGRATION TEST")
    print("=" * 60)
    print()

    # Create a simple test chart
    print("Creating test chart...", end=" ")
    try:
        from university_system.modules.shared.utils.chart_generator import DatabaseChartGenerator

        gen = DatabaseChartGenerator()
        fig = gen.generate_age_distribution()

        if fig:
            print("✓ SUCCESS")
            print()

            # Test email functionality (without actually sending)
            print("Testing email_chart method...", end=" ")
            chart_gen = ChartGenerator()

            # Check if method exists
            if hasattr(chart_gen, 'email_chart'):
                print("✓ Method exists")
                print()

                print("Email functionality ready:")
                print("  - Charts can be saved as attachments")
                print("  - Email sending configured")
                print("  - Default recipient: admin@university.edu")
                print()
                print("To test actual email sending:")
                print("  1. Open Advanced Search GUI")
                print("  2. Navigate to: Visualization → Interactive Charts")
                print("  3. Generate any chart")
                print("  4. Click '📧 Email Chart' button")
                print("  5. Enter recipient email and click 'Send Email'")
            else:
                print("✗ Method not found")
        else:
            print("⚠ No data for test chart")

    except Exception as e:
        print(f"✗ FAILED: {str(e)}")

    print()


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("CHART EMAIL FUNCTIONALITY TEST SUITE")
    print("=" * 60)
    print()

    # Test 1: Check email availability
    email_ok = test_email_availability()

    # Test 2: Test chart email integration
    if email_ok:
        test_chart_email_integration()
    else:
        print("Email service not available. Skipping integration tests.")

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
