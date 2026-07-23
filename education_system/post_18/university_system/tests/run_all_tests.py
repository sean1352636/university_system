#!/usr/bin/env python3
"""
Comprehensive Test Runner - Master test runner for University System

The university test suite uses a **feature-first** layout that mirrors the
source ``modules/`` tree: one folder per feature, holding CLI *and* GUI tests
together. Interface type is expressed with a pytest **marker**, not a
directory:

  - GUI tests carry ``pytestmark = pytest.mark.gui``  -> select with ``-m gui``
  - everything else is "CLI/backend"                  -> select with ``-m "not gui"``

Top-level layers (mirror of ``modules/``):
  - core/           cross-cutting utilities (config, i18n, paths, exceptions)
  - domain/         one folder per feature (academics, finance, health, ...)
  - infrastructure/ auth, database, email, security, validation, ai
  - services/       cross-cutting services
  - shared/         university-shared (analytics, gui widgets, utils)
  - integration/    cross-feature journeys, e2e, performance
  - sal/            the SAL subsystem
  - scripts/        tests for one-off maintenance scripts
  - smoke/          broad smoke tests

Uses pytest for automatic test discovery, fixtures, and comprehensive reporting.
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Tests directory (this file lives at the tests/ root).
TESTS_DIR = Path(__file__).parent

# Top-level layers, in display order.
LAYERS = [
    "core",
    "domain",
    "infrastructure",
    "services",
    "shared",
    "integration",
    "sal",
    "scripts",
    "smoke",
]

RUNNER_PYTEST_DEFAULTS = [
    "-o",
    "addopts=",
    "--import-mode=importlib",
    "--ignore=education_system/post_18/university_system/tests/domain/commerce/restaurant",
    "--ignore=education_system/post_18/university_system/tests/domain/health",
    "--ignore=education_system/post_18/university_system/tests/domain/academics/assessment",
    "--ignore=education_system/post_18/university_system/tests/domain/academics/assignments",
]


def _with_serial_pytest(args):
    """Disable xdist for this interactive runner unless the user asked for it."""
    has_xdist_option = any(
        arg == "-n"
        or arg.startswith("-n")
        or arg == "--numprocesses"
        or arg.startswith("--numprocesses=")
        for arg in args
    )
    if has_xdist_option:
        return list(args)
    return list(args) + ["-n0"]


def _with_runner_pytest_defaults(args):
    """Use runner defaults instead of pyproject's quiet/parallel addopts."""
    return RUNNER_PYTEST_DEFAULTS + list(args)


def _gui_test_files():
    """GUI test files = those declaring the gui marker (location-independent)."""
    return [
        p
        for p in TESTS_DIR.rglob("test_*.py")
        if "pytest.mark.gui" in p.read_text(errors="ignore")
    ]


def _all_test_files():
    return list(TESTS_DIR.rglob("test_*.py"))


class CollectionProgressPlugin:
    """Print a concise collection summary for the interactive test runner."""

    def pytest_collection_modifyitems(self, session, config, items):
        print(f"\nCollected {len(items)} tests. Starting execution...\n", flush=True)


def run_pytest(args, description=None):
    """Run pytest with given arguments."""
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

    pytest_args = _with_serial_pytest(_with_runner_pytest_defaults(args))
    logger.info(f"Running pytest with args: {' '.join(pytest_args)}")
    print("\nCollecting tests...", flush=True)
    exit_code = pytest.main(pytest_args, plugins=[CollectionProgressPlugin()])
    return exit_code == 0


def run_all_tests():
    """Run all tests with verbose output."""
    pytest_args = [str(TESTS_DIR), "-vv", "--tb=short", "-ra", "--strict-markers", "--color=yes"]
    return run_pytest(pytest_args, "Running ALL tests")


def run_sample_tests():
    """Run quick sample tests for validation."""
    sample_tests = [
        "infrastructure/database/test_database.py",
        "infrastructure/auth/test_user_authentication.py",
        "shared/utils/test_config.py",
    ]
    print("\nRunning sample tests for quick validation...")
    all_passed = True
    for test in sample_tests:
        test_path = TESTS_DIR / test
        if test_path.exists():
            all_passed &= run_pytest([str(test_path), "-vv", "--tb=short"], f"Running {test}")
        else:
            print(f"Warning: Test file not found: {test}")
    return all_passed


def run_critical_tests():
    """Run critical tests (auth, database, security)."""
    critical_tests = [
        "infrastructure/auth/test_user_authentication.py",
        "infrastructure/database/test_database.py",
        "infrastructure/database/test_db_connection_pooling.py",
        "infrastructure/security/test_comprehensive_security.py",
    ]
    print("\nRunning critical tests...")
    all_passed = True
    for test in critical_tests:
        test_path = TESTS_DIR / test
        if test_path.exists():
            all_passed &= run_pytest([str(test_path), "-vv", "--tb=short"], f"Running {test}")
        else:
            print(f"Warning: Test file not found: {test}")
    return all_passed


def generate_coverage_report():
    """Generate comprehensive coverage report."""
    print("\nGenerating coverage report...")
    pytest_args = [
        str(TESTS_DIR),
        "--cov=university_system",
        "--cov-report=html",
        "--cov-report=term",
        "-vv",
        "--tb=short",
    ]
    success = run_pytest(pytest_args, "Generating Coverage Report")
    if success:
        print("\nCoverage report generated!")
        print("HTML report: htmlcov/index.html")
    return success


def run_tests_by_layer():
    """Run tests for a single architectural layer."""
    print("\nSelect layer:")
    available = [layer for layer in LAYERS if (TESTS_DIR / layer).exists()]
    for idx, layer in enumerate(available, 1):
        print(f"  {idx}. {layer}")

    choice = input(f"\nEnter choice (1-{len(available)}): ").strip()
    try:
        layer_name = available[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid choice")
        return False

    pytest_args = [str(TESTS_DIR / layer_name), "-vv", "--tb=short", "-ra"]
    return run_pytest(pytest_args, f"Running {layer_name} layer tests")


def run_by_marker():
    """Run tests filtered by pytest markers."""
    print("\nAvailable markers:")
    markers = {
        "1": "unit",
        "2": "integration",
        "3": "slow",
        "4": "security",
        "5": "gui",
    }
    for key, name in markers.items():
        print(f"  {key}. {name}")

    marker = markers.get(input("\nEnter choice (1-5): ").strip())
    if marker is None:
        print("Invalid choice")
        return False

    pytest_args = [str(TESTS_DIR), "-m", marker, "-vv", "--tb=short"]
    return run_pytest(pytest_args, f"Running tests with marker: {marker}")


def run_tests_by_domain():
    """Run tests for a specific domain area."""
    domain_root = TESTS_DIR / "domain"
    if not domain_root.exists():
        print("Warning: no domain/ directory found")
        return False

    print("\nSelect domain area:")
    domains = sorted(
        (d for d in domain_root.iterdir() if d.is_dir() and d.name != "__pycache__"),
        key=lambda d: d.name,
    )
    domains = [d for d in domains if list(d.rglob("test_*.py"))]
    for idx, d in enumerate(domains, 1):
        count = len(list(d.rglob("test_*.py")))
        print(f"  {idx}. {d.name:20s} ({count:3d} test files)")

    try:
        selected = domains[int(input(f"\nEnter choice (1-{len(domains)}): ").strip()) - 1]
    except (ValueError, IndexError):
        print("Invalid choice")
        return False

    pytest_args = [str(selected), "-vv", "--tb=short", "-ra"]
    return run_pytest(pytest_args, f"Running {selected.name} domain tests")


def run_gui_tests():
    """Run all GUI-marked tests (-m gui)."""
    gui_count = len(_gui_test_files())
    print(f"\nFound {gui_count} GUI test files (pytest.mark.gui)")
    if input(f"Run all {gui_count} GUI test files? (y/n): ").strip().lower() != "y":
        print("Cancelled")
        return False
    return run_pytest([str(TESTS_DIR), "-m", "gui", "-vv", "--tb=short", "-ra"], "Running all GUI tests")


def run_cli_tests():
    """Run all non-GUI (backend) tests (-m 'not gui')."""
    total = len(_all_test_files())
    gui = len(_gui_test_files())
    print(f"\nRunning ~{total - gui} CLI/backend test files (-m 'not gui')")
    if input("Proceed? (y/n): ").strip().lower() != "y":
        print("Cancelled")
        return False
    return run_pytest(
        [str(TESTS_DIR), "-m", "not gui", "-vv", "--tb=short", "-ra"], "Running all CLI/backend tests"
    )


def show_detailed_structure():
    """Show detailed test file structure."""
    print("\n" + "=" * 80)
    print("DETAILED TEST STRUCTURE")
    print("=" * 80)

    all_files = _all_test_files()
    gui_files = set(_gui_test_files())
    print(f"\nTotal test files: {len(all_files)}")
    print(f"   - GUI (pytest.mark.gui) : {len(gui_files)}")
    print(f"   - CLI/backend           : {len(all_files) - len(gui_files)}")

    print("\nFiles by layer:")
    for layer in LAYERS:
        layer_path = TESTS_DIR / layer
        if layer_path.exists():
            files = list(layer_path.rglob("test_*.py"))
            if files:
                gui_n = sum(1 for f in files if f in gui_files)
                print(f"   - {layer:15s} : {len(files):3d} files ({gui_n} gui)")

    domain_root = TESTS_DIR / "domain"
    if domain_root.exists():
        print("\nDomain tests by area:")
        for d in sorted(domain_root.iterdir(), key=lambda d: d.name):
            if d.is_dir() and d.name != "__pycache__":
                count = len(list(d.rglob("test_*.py")))
                if count:
                    print(f"   - {d.name:20s} : {count:3d} files")

    print("\n" + "=" * 80)
    input("\nPress Enter to continue...")


def interactive_menu():
    """Display interactive menu and handle user choice."""
    print("=" * 80)
    print("COMPREHENSIVE TEST SUITE RUNNER")
    print("=" * 80)

    all_files = _all_test_files()
    gui_files = _gui_test_files()
    print(f"\nTotal: {len(all_files)} test files")
    print(f"   - GUI tests: {len(gui_files)} files (pytest.mark.gui)")
    print(f"   - CLI tests: {len(all_files) - len(gui_files)} files (backend services)")

    print("\nTest distribution by layer:")
    for layer in LAYERS:
        layer_path = TESTS_DIR / layer
        if layer_path.exists():
            count = len(list(layer_path.rglob("test_*.py")))
            if count:
                print(f"   - {layer:15s} : {count:3d} files")

    print("\nChoose test execution mode:")
    print("  1. Run ALL tests (comprehensive, may take time)")
    print("  2. Run SAMPLE tests (quick validation)")
    print("  3. Run CRITICAL tests only (auth, db, security)")
    print("  4. Generate COVERAGE report")
    print("  5. Run tests by LAYER")
    print("  6. Run tests by MARKER (unit, integration, slow, security, gui)")
    print("  7. Show DETAILED test structure")
    print("  8. List all available tests")
    print("  9. Run tests by DOMAIN area (academics, finance, health, ...)")
    print(" 10. Run all GUI tests (-m gui)")
    print(" 11. Run all CLI tests (-m 'not gui')")
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
        success = run_pytest([str(TESTS_DIR), "--collect-only"], "Listing all available tests")
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

    print("\n" + "=" * 80)
    print("Test execution completed successfully!" if success else "Warning: Some tests failed")
    print("=" * 80)
    return success


def main():
    """Main execution."""
    if len(sys.argv) > 1:
        print("=" * 80)
        print("UNIVERSITY SYSTEM - COMPREHENSIVE TEST SUITE (PYTEST)")
        print("=" * 80)
        try:
            import pytest
        except ImportError:
            print("Error: pytest is not installed. Install it with: pip install pytest")
            return False
        pytest_args = _with_serial_pytest(_with_runner_pytest_defaults([str(TESTS_DIR)] + sys.argv[1:]))
        print("\nCollecting tests...", flush=True)
        exit_code = pytest.main(pytest_args, plugins=[CollectionProgressPlugin()])
        print("\n" + "=" * 80)
        print("All tests passed!" if exit_code == 0 else f"Some tests failed (exit code: {exit_code})")
        print("=" * 80)
        return exit_code == 0
    return interactive_menu()


if __name__ == "__main__":
    try:
        sys.exit(0 if main() else 1)
    except KeyboardInterrupt:
        print("\n\nWarning: Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\nError: Unexpected error: {e}")
        sys.exit(1)
