#!/usr/bin/env python3
"""
Comprehensive Test Runner - Master test runner for University System

This script provides multiple test execution modes:
- Run all tests
- Run sample/critical tests
- Generate coverage reports
- Run tests by layer (infrastructure, domain, shared, web)

Uses pytest for better fixtures, test isolation, and reporting.
"""

import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get tests directory
TESTS_DIR = Path(__file__).parent


def run_pytest(args, description=None):
    """Run pytest with given arguments"""
    if description:
        print(f"\n{'='*80}")
        print(f"🚀 {description}")
        print(f"{'='*80}")

    try:
        import pytest
    except ImportError:
        logger.error("pytest is not installed. Please install it with: pip install pytest")
        print("Error: pytest is not installed.")
        print("Install it with: pip install pytest")
        return False

    logger.info(f"Running pytest with args: {' '.join(args)}")
    exit_code = pytest.main(args)

    return exit_code == 0


def run_all_tests():
    """Run all tests with verbose output"""
    pytest_args = [
        str(TESTS_DIR),
        "-v",
        "--tb=short",
        "-ra",
        "--strict-markers",
        "--color=yes",
    ]
    return run_pytest(pytest_args, "Running ALL tests")


def run_sample_tests():
    """Run quick sample tests for validation"""
    sample_tests = [
        "test_utils.py",
        "test_database.py",
        "test_integration_workflows.py"
    ]

    print("\n📊 Running sample tests for quick validation...")
    all_passed = True

    for test in sample_tests:
        test_path = TESTS_DIR / test
        if test_path.exists():
            pytest_args = [str(test_path), "-v", "--tb=short"]
            passed = run_pytest(pytest_args, f"Running {test}")
            all_passed = all_passed and passed
        else:
            print(f"⚠️  Test file not found: {test}")

    return all_passed


def run_critical_tests():
    """Run critical tests (auth, database, integration)"""
    critical_tests = [
        "test_user_authentication.py",
        "test_database.py",
        "test_integration_workflows.py",
        "test_db.py",
        "test_authentication.py"
    ]

    print("\n🔒 Running critical tests...")
    all_passed = True

    for test in critical_tests:
        test_path = TESTS_DIR / test
        if test_path.exists():
            pytest_args = [str(test_path), "-v", "--tb=short"]
            passed = run_pytest(pytest_args, f"Running {test}")
            all_passed = all_passed and passed

    return all_passed


def generate_coverage_report():
    """Generate comprehensive coverage report"""
    print("\n📊 Generating coverage report...")

    pytest_args = [
        str(TESTS_DIR),
        "--cov=university_system",
        "--cov-report=html",
        "--cov-report=term",
        "-v",
        "--tb=short"
    ]

    success = run_pytest(pytest_args, "Generating Coverage Report")

    if success:
        print("\n✅ Coverage report generated!")
        print("📁 HTML report: htmlcov/index.html")
        print("\nView in browser:")
        print("  firefox htmlcov/index.html")

    return success


def run_tests_by_layer():
    """Run tests organized by architectural layer"""
    print("\nSelect layer:")
    print("  1. Infrastructure (auth, database, email, security)")
    print("  2. Domain (academics, finance, student, health, housing)")
    print("  3. Shared (utils, gui, analytics)")
    print("  4. Web (web services, APIs)")

    layer_choice = input("\nEnter choice (1-4): ").strip()

    layer_patterns = {
        "1": ["*auth*", "*database*", "*db*", "*email*", "*security*"],
        "2": ["*academic*", "*finance*", "*student*", "*health*", "*housing*"],
        "3": ["*utils*", "*gui*", "*analytics*", "*reporting*"],
        "4": ["*web*", "*api*", "*rest*"]
    }

    if layer_choice not in layer_patterns:
        print("❌ Invalid choice")
        return False

    patterns = layer_patterns[layer_choice]
    all_passed = True

    print(f"\n🔍 Finding tests matching patterns: {', '.join(patterns)}")

    for pattern in patterns:
        matching_tests = list(TESTS_DIR.glob(f"test_{pattern}.py"))

        for test in matching_tests[:5]:  # Limit to 5 per pattern
            pytest_args = [str(test), "-v", "--tb=short"]
            passed = run_pytest(pytest_args, f"Running {test.name}")
            all_passed = all_passed and passed

    return all_passed


def run_by_marker():
    """Run tests filtered by pytest markers"""
    print("\nAvailable markers:")
    print("  1. unit - Unit tests only")
    print("  2. integration - Integration tests only")
    print("  3. slow - Slow tests")
    print("  4. security - Security tests")

    marker_choice = input("\nEnter choice (1-4): ").strip()

    markers = {
        "1": "unit",
        "2": "integration",
        "3": "slow",
        "4": "security"
    }

    if marker_choice not in markers:
        print("❌ Invalid choice")
        return False

    marker = markers[marker_choice]

    pytest_args = [
        str(TESTS_DIR),
        "-m", marker,
        "-v",
        "--tb=short"
    ]

    return run_pytest(pytest_args, f"Running tests with marker: {marker}")


def interactive_menu():
    """Display interactive menu and handle user choice"""
    print("="*80)
    print("🧪 COMPREHENSIVE TEST SUITE RUNNER")
    print("="*80)
    print()

    # Count test files
    test_files = list(TESTS_DIR.glob("test_*.py"))
    print(f"📊 Found {len(test_files)} test files")
    print()

    print("Choose test execution mode:")
    print("  1. Run ALL tests (comprehensive, may take time)")
    print("  2. Run SAMPLE tests (quick validation)")
    print("  3. Run CRITICAL tests only (auth, db, integration)")
    print("  4. Generate COVERAGE report")
    print("  5. Run tests by LAYER (infrastructure, domain, shared, web)")
    print("  6. Run tests by MARKER (unit, integration, slow, security)")
    print("  7. List all available tests")
    print("  8. Exit")

    choice = input("\nEnter choice (1-8): ").strip()

    if choice == "1":
        success = run_all_tests()
    elif choice == "2":
        success = run_sample_tests()
    elif choice == "3":
        success = run_critical_tests()
    elif choice == "4":
        success = generate_coverage_report()
    elif choice == "5":
        success = run_tests_by_layer()
    elif choice == "6":
        success = run_by_marker()
    elif choice == "7":
        # List all tests
        pytest_args = [str(TESTS_DIR), "--collect-only"]
        success = run_pytest(pytest_args, "Listing all available tests")
    elif choice == "8":
        print("Exiting...")
        return True
    else:
        print("❌ Invalid choice")
        return False

    print("\n" + "="*80)
    if success:
        print("✅ Test execution completed successfully!")
    else:
        print("⚠️  Some tests failed or encountered errors")
    print("="*80)

    return success


def main():
    """Main execution"""

    # Check if arguments were provided
    if len(sys.argv) > 1:
        # Direct pytest mode with arguments
        logger.info("Running pytest with provided arguments")
        print("="*80)
        print("UNIVERSITY SYSTEM - COMPREHENSIVE TEST SUITE (PYTEST)")
        print("="*80)
        print()

        pytest_args = [str(TESTS_DIR)] + sys.argv[1:]

        try:
            import pytest
        except ImportError:
            logger.error("pytest is not installed. Please install it with: pip install pytest")
            print("Error: pytest is not installed.")
            print("Install it with: pip install pytest")
            return False

        exit_code = pytest.main(pytest_args)

        print()
        print("="*80)
        if exit_code == 0:
            logger.info("All tests passed!")
            print("✓ All tests passed!")
        else:
            logger.warning(f"Some tests failed (exit code: {exit_code})")
            print(f"✗ Some tests failed (exit code: {exit_code})")
        print("="*80)

        return exit_code == 0
    else:
        # Interactive mode
        return interactive_menu()


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
