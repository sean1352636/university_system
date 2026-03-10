#!/usr/bin/env python3
"""
Comprehensive Test Runner - Master test runner for University System

This script provides multiple test execution modes for all 308 test files:
- Run all tests (7,178+ individual tests)
- Run sample/critical tests
- Generate coverage reports
- Run tests by layer (infrastructure, domain, shared, integration, modules, misc)
- Run tests by domain area (academics, finance, health, housing, student affairs, commerce)
- Run tests by marker (unit, integration, slow, security)
- Run all GUI tests (85 test files with Tkinter imports)
- Run all CLI tests (223 test files for backend services)
- Show detailed test structure with all files organized by category

Test files are organized into two main categories:
  - gui/            85 files (tests that use Tkinter GUI components)
  - cli/           223 files (tests for backend services, database, auth, etc.)

Within each category, tests are organized by layer:
  - domain/        (academics, finance, health, housing, student_affairs, commerce, mobility)
  - infrastructure/ (auth, database, email, security, ai)
  - shared/        (utils, gui, analytics)
  - integration/   (workflows, marketplace)
  - modules/       (services)
  - misc/          (miscellaneous tests)

Uses pytest for automatic test discovery, fixtures, and comprehensive reporting.
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
GUI_DIR = TESTS_DIR / "gui"
CLI_DIR = TESTS_DIR / "cli"


def run_pytest(args, description=None):
    """Run pytest with given arguments"""
    if description:
        print(f"\n{'='*80}")
        print(f"Running: {description}")
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
        "cli/infrastructure/database/test_database.py",
        "cli/infrastructure/auth/test_user_authentication.py",
        "cli/shared/utils/test_config.py"
    ]

    print("\nRunning sample tests for quick validation...")
    all_passed = True

    for test in sample_tests:
        test_path = TESTS_DIR / test
        if test_path.exists():
            pytest_args = [str(test_path), "-v", "--tb=short"]
            passed = run_pytest(pytest_args, f"Running {test}")
            all_passed = all_passed and passed
        else:
            print(f"Warning: Test file not found: {test}")

    return all_passed


def run_critical_tests():
    """Run critical tests (auth, database, integration)"""
    critical_tests = [
        "cli/infrastructure/auth/test_user_authentication.py",
        "cli/infrastructure/database/test_database.py",
        "cli/infrastructure/database/test_db_connection_pooling.py",
        "cli/infrastructure/security/test_comprehensive_security.py",
    ]

    print("\nRunning critical tests...")
    all_passed = True

    for test in critical_tests:
        test_path = TESTS_DIR / test
        if test_path.exists():
            pytest_args = [str(test_path), "-v", "--tb=short"]
            passed = run_pytest(pytest_args, f"Running {test}")
            all_passed = all_passed and passed
        else:
            print(f"Warning: Test file not found: {test}")

    return all_passed


def generate_coverage_report():
    """Generate comprehensive coverage report"""
    print("\nGenerating coverage report...")

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
        print("\nCoverage report generated!")
        print("HTML report: htmlcov/index.html")
        print("\nView in browser:")
        print("  firefox htmlcov/index.html")

    return success


def run_tests_by_layer():
    """Run tests organized by architectural layer"""
    print("\nSelect layer:")
    print("  1. Infrastructure (auth, database, email, security, AI)")
    print("  2. Domain (academics, finance, health, housing, student affairs, commerce)")
    print("  3. Shared (utils, gui, analytics)")
    print("  4. Integration (workflows, marketplace)")
    print("  5. Modules (services)")
    print("  6. Misc (miscellaneous tests)")

    layer_choice = input("\nEnter choice (1-6): ").strip()

    layer_names = {
        "1": "infrastructure",
        "2": "domain",
        "3": "shared",
        "4": "integration",
        "5": "modules",
        "6": "misc"
    }

    if layer_choice not in layer_names:
        print("Invalid choice")
        return False

    layer_name = layer_names[layer_choice]

    # Collect test paths from both cli and gui directories
    test_paths = []
    for base_dir in [CLI_DIR, GUI_DIR]:
        layer_path = base_dir / layer_name
        if layer_path.exists():
            test_paths.append(str(layer_path))

    if not test_paths:
        print(f"Warning: No test directories found for layer: {layer_name}")
        return False

    pytest_args = test_paths + ["-v", "--tb=short", "-ra"]

    return run_pytest(pytest_args, f"Running {layer_name} layer tests")


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
        print("Invalid choice")
        return False

    marker = markers[marker_choice]

    pytest_args = [
        str(TESTS_DIR),
        "-m", marker,
        "-v",
        "--tb=short"
    ]

    return run_pytest(pytest_args, f"Running tests with marker: {marker}")


def run_tests_by_domain():
    """Run tests for specific domain area"""
    print("\nSelect domain area:")

    # Collect available domains from both cli and gui
    domains = {}
    for base_dir in [CLI_DIR, GUI_DIR]:
        domain_path = base_dir / "domain"
        if domain_path.exists():
            for subdomain in domain_path.iterdir():
                if subdomain.is_dir() and subdomain.name != "__pycache__":
                    test_count = len(list(subdomain.rglob("test_*.py")))
                    if subdomain.name not in domains:
                        domains[subdomain.name] = {"paths": [], "count": 0}
                    domains[subdomain.name]["paths"].append(subdomain)
                    domains[subdomain.name]["count"] += test_count

    # Convert to list for indexing
    domain_list = [(name, data) for name, data in sorted(domains.items()) if data["count"] > 0]

    # Display domain options
    for idx, (name, data) in enumerate(domain_list, 1):
        print(f"  {idx}. {name:20s} ({data['count']:3d} test files)")

    # Collect academics subcategories
    academics_subs = {}
    for base_dir in [CLI_DIR, GUI_DIR]:
        academics_path = base_dir / "domain" / "academics"
        if academics_path.exists():
            for sub_category in academics_path.iterdir():
                if sub_category.is_dir() and sub_category.name != "__pycache__":
                    sub_count = len(list(sub_category.glob("test_*.py")))
                    if sub_category.name not in academics_subs:
                        academics_subs[sub_category.name] = {"paths": [], "count": 0}
                    academics_subs[sub_category.name]["paths"].append(sub_category)
                    academics_subs[sub_category.name]["count"] += sub_count

    academics_list = [(name, data) for name, data in sorted(academics_subs.items()) if data["count"] > 0]

    if academics_list:
        print("\n  Academics Subcategories:")
        for idx, (name, data) in enumerate(academics_list, len(domain_list) + 1):
            print(f"  {idx}. academics/{name:15s} ({data['count']:3d} test files)")

    total_options = len(domain_list) + len(academics_list)
    choice = input(f"\nEnter choice (1-{total_options}): ").strip()

    try:
        choice_idx = int(choice)
        if 1 <= choice_idx <= len(domain_list):
            selected_name, selected_data = domain_list[choice_idx - 1]
            selected_paths = selected_data["paths"]
        elif len(domain_list) < choice_idx <= total_options:
            selected_name, selected_data = academics_list[choice_idx - len(domain_list) - 1]
            selected_name = f"academics/{selected_name}"
            selected_paths = selected_data["paths"]
        else:
            print("Invalid choice")
            return False
    except (ValueError, IndexError):
        print("Invalid choice")
        return False

    pytest_args = [str(p) for p in selected_paths] + ["-v", "--tb=short", "-ra"]

    return run_pytest(pytest_args, f"Running {selected_name} domain tests")


def run_gui_tests():
    """Run all GUI-related tests"""
    print("\nSearching for GUI test files...")

    gui_test_files = list(GUI_DIR.rglob("test_*.py"))

    if not gui_test_files:
        print("Warning: No GUI test files found")
        return False

    print(f"Found {len(gui_test_files)} GUI test files")
    print("\nTest distribution by layer:")

    # Show distribution by layer
    layers = {}
    for test_file in gui_test_files:
        rel_path = test_file.relative_to(GUI_DIR)
        layer = rel_path.parts[0] if len(rel_path.parts) > 1 else "root"
        layers[layer] = layers.get(layer, 0) + 1

    for layer, count in sorted(layers.items()):
        print(f"   - {layer}: {count} files")

    print()
    confirm = input(f"Run all {len(gui_test_files)} GUI test files? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled")
        return False

    pytest_args = [str(GUI_DIR), "-v", "--tb=short", "-ra"]

    return run_pytest(pytest_args, "Running all GUI tests")


def run_cli_tests():
    """Run all CLI-related tests (non-GUI backend tests)"""
    print("\nSearching for CLI test files...")

    cli_test_files = list(CLI_DIR.rglob("test_*.py"))

    if not cli_test_files:
        print("Warning: No CLI test files found")
        return False

    print(f"Found {len(cli_test_files)} CLI test files")
    print("\nTest distribution by layer:")

    # Show distribution by layer
    layers = {}
    for test_file in cli_test_files:
        rel_path = test_file.relative_to(CLI_DIR)
        layer = rel_path.parts[0] if len(rel_path.parts) > 1 else "root"
        layers[layer] = layers.get(layer, 0) + 1

    for layer, count in sorted(layers.items()):
        print(f"   - {layer}: {count} files")

    print()
    confirm = input(f"Run all {len(cli_test_files)} CLI test files? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled")
        return False

    pytest_args = [str(CLI_DIR), "-v", "--tb=short", "-ra"]

    return run_pytest(pytest_args, "Running all CLI tests")


def show_detailed_structure():
    """Show detailed test file structure"""
    print("\n" + "="*80)
    print("DETAILED TEST STRUCTURE")
    print("="*80)
    print()

    # Show GUI tests structure
    print("GUI TESTS (tests with Tkinter imports):")
    gui_count = len(list(GUI_DIR.rglob("test_*.py")))
    print(f"   Total: {gui_count} files")

    for layer in ["domain", "infrastructure", "shared", "integration", "modules", "misc"]:
        layer_path = GUI_DIR / layer
        if layer_path.exists():
            layer_tests = list(layer_path.rglob("test_*.py"))
            if layer_tests:
                print(f"   - {layer:20s} : {len(layer_tests):3d} files")
    print()

    # Show CLI tests structure
    print("CLI TESTS (backend services, database, auth, etc.):")
    cli_count = len(list(CLI_DIR.rglob("test_*.py")))
    print(f"   Total: {cli_count} files")

    for layer in ["domain", "infrastructure", "shared", "integration", "modules", "misc"]:
        layer_path = CLI_DIR / layer
        if layer_path.exists():
            layer_tests = list(layer_path.rglob("test_*.py"))
            if layer_tests:
                print(f"   - {layer:20s} : {len(layer_tests):3d} files")
    print()

    # Show domain breakdown
    print("DOMAIN TESTS BY AREA (combined GUI + CLI):")
    domains = {}
    for base_dir in [CLI_DIR, GUI_DIR]:
        domain_path = base_dir / "domain"
        if domain_path.exists():
            for subdomain in domain_path.iterdir():
                if subdomain.is_dir() and subdomain.name != "__pycache__":
                    count = len(list(subdomain.rglob("test_*.py")))
                    domains[subdomain.name] = domains.get(subdomain.name, 0) + count

    for name, count in sorted(domains.items()):
        print(f"   - {name:20s} : {count:3d} files")

    print("\n" + "="*80)
    input("\nPress Enter to continue...")


def interactive_menu():
    """Display interactive menu and handle user choice"""
    print("="*80)
    print("COMPREHENSIVE TEST SUITE RUNNER")
    print("="*80)
    print()

    # Count test files recursively
    gui_tests = list(GUI_DIR.rglob("test_*.py"))
    cli_tests = list(CLI_DIR.rglob("test_*.py"))
    total_tests = len(gui_tests) + len(cli_tests)

    print(f"Total: {total_tests} test files")
    print(f"   - GUI tests: {len(gui_tests)} files (Tkinter-based)")
    print(f"   - CLI tests: {len(cli_tests)} files (backend services)")
    print()

    # Show structure overview
    print("Test Distribution by Layer (combined):")
    for layer in ["domain", "infrastructure", "shared", "integration", "modules", "misc"]:
        layer_count = 0
        for base_dir in [CLI_DIR, GUI_DIR]:
            layer_path = base_dir / layer
            if layer_path.exists():
                layer_count += len(list(layer_path.rglob("test_*.py")))
        if layer_count > 0:
            print(f"   - {layer:15s} : {layer_count:3d} files")
    print()

    print("Choose test execution mode:")
    print("  1. Run ALL tests (comprehensive, may take time)")
    print("  2. Run SAMPLE tests (quick validation)")
    print("  3. Run CRITICAL tests only (auth, db, security)")
    print("  4. Generate COVERAGE report")
    print("  5. Run tests by LAYER (infrastructure, domain, shared, etc.)")
    print("  6. Run tests by MARKER (unit, integration, slow, security)")
    print("  7. Show DETAILED test structure (all files organized)")
    print("  8. List all available tests")
    print("  9. Run tests by DOMAIN area (academics, finance, health, etc.)")
    print(" 10. Run all GUI tests")
    print(" 11. Run all CLI tests")
    print("  0. Exit")

    choice = input("\nEnter choice (0-11): ").strip()

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
        show_detailed_structure()
        return True
    elif choice == "8":
        # List all tests
        pytest_args = [str(TESTS_DIR), "--collect-only"]
        success = run_pytest(pytest_args, "Listing all available tests")
    elif choice == "9":
        success = run_tests_by_domain()
    elif choice == "10":
        success = run_gui_tests()
    elif choice == "11":
        success = run_cli_tests()
    elif choice == "0":
        print("Exiting...")
        return True
    else:
        print("Invalid choice")
        return False

    print("\n" + "="*80)
    if success:
        print("Test execution completed successfully!")
    else:
        print("Warning: Some tests failed or encountered errors")
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
            print("All tests passed!")
        else:
            logger.warning(f"Some tests failed (exit code: {exit_code})")
            print(f"Some tests failed (exit code: {exit_code})")
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
        print("\n\nWarning: Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\nError: Unexpected error: {e}")
        sys.exit(1)
