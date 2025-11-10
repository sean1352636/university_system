#!/usr/bin/env python3
"""
Test script for chart generation functionality
Verifies that charts can be generated from database data
"""

import sys
import os

# Add project root to path
sys.path.insert(0, '/home/seancatchpole989')

from university_system.modules.shared.utils.chart_generator import (
    DatabaseChartGenerator, CHARTS_AVAILABLE
)

def test_chart_availability():
    """Test if chart generation libraries are available"""
    print("=" * 60)
    print("CHART GENERATION AVAILABILITY TEST")
    print("=" * 60)

    if CHARTS_AVAILABLE:
        print("✓ Chart generation is AVAILABLE")
        print("  - matplotlib: INSTALLED")
        print("  - seaborn: INSTALLED")
        print("  - numpy: INSTALLED")
    else:
        print("✗ Chart generation is NOT available")
        print("  Install with: pip install matplotlib seaborn")
        return False

    print()
    return True


def test_database_charts():
    """Test generating charts from database"""
    if not CHARTS_AVAILABLE:
        print("Skipping database chart tests (libraries not available)")
        return

    print("=" * 60)
    print("DATABASE CHART GENERATION TESTS")
    print("=" * 60)
    print()

    gen = DatabaseChartGenerator()

    tests = [
        ("Age Distribution", gen.generate_age_distribution),
        ("Course Distribution", gen.generate_course_distribution),
        ("Registration Timeline", gen.generate_registration_timeline),
        ("Gender-Course Distribution", gen.generate_gender_course_distribution),
        ("Module Popularity", gen.generate_module_popularity),
        ("Grade Distribution", gen.generate_grade_distribution),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"Testing: {test_name}...", end=" ")
        try:
            fig = test_func()
            if fig:
                print("✓ SUCCESS (chart generated)")
                results.append((test_name, "SUCCESS", "Chart generated"))

                # Save to temp file for verification
                import tempfile
                fd, temp_path = tempfile.mkstemp(suffix='.png', prefix=f'test_chart_{test_name.replace(" ", "_")}_')
                os.close(fd)
                fig.savefig(temp_path, dpi=100, bbox_inches='tight')
                print(f"  Saved to: {temp_path}")
                results.append((test_name, "SAVED", temp_path))
            else:
                print("⚠ WARNING (no data in database)")
                results.append((test_name, "NO_DATA", "Database has no data for this chart"))
        except Exception as e:
            print(f"✗ FAILED: {str(e)}")
            results.append((test_name, "FAILED", str(e)))

        print()

    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    success_count = sum(1 for _, status, _ in results if status in ["SUCCESS", "SAVED"])
    total_tests = len(tests)

    print(f"\nTotal Tests: {total_tests}")
    print(f"Successful: {success_count // 2}")  # Divide by 2 because each chart has 2 results
    print(f"Warnings: {sum(1 for _, status, _ in results if status == 'NO_DATA')}")
    print(f"Failed: {sum(1 for _, status, _ in results if status == 'FAILED')}")

    print("\nDetailed Results:")
    for test_name, status, message in results:
        if status == "SAVED":
            continue  # Skip saved file paths in summary
        icon = "✓" if status == "SUCCESS" else "⚠" if status == "NO_DATA" else "✗"
        print(f"  {icon} {test_name}: {status}")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("CHART GENERATION TEST SUITE")
    print("=" * 60)
    print()

    # Test 1: Check availability
    if not test_chart_availability():
        print("\n✗ Chart generation not available. Exiting.")
        return 1

    print()

    # Test 2: Test database charts
    test_database_charts()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
