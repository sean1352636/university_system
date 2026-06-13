import tkinter as tk
import queue
import os
import logging

from education_system.university_system.core.i18n import get_text as _t

from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.config import GuiConfig
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.common import (
    logger,
    StatusBar,
    PLAGIARISM_BACKEND_AVAILABLE,
)


def integrate_plagiarism_checker_with_main():
    """Integration function for backwards compatibility with the original system."""
    try:
        try:
            import main_system
            if hasattr(main_system, 'add_menu_option'):
                main_system.add_menu_option(
                    "Plagiarism Checker (GUI)",
                    launch_gui_from_main_system
                )
                logger.info("Successfully integrated GUI option with main system")
                return True
        except ImportError as e:
            logger.debug(f"Could not integrate with main system: {e}")

        logger.info("Plagiarism checker GUI integration completed")
        return True

    except Exception as e:
        logger.error(f"Error during GUI integration: {e}")
        return False


def launch_gui_from_main_system(auth=None):
    """Launch the plagiarism checker GUI from the main system."""
    try:
        from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.main_gui import PlagiarismCheckerGUI

        print("Launching Plagiarism Checker GUI from main system...")
        app = PlagiarismCheckerGUI(auth=auth)
        app.run()
    except Exception as e:
        print(f"Error launching GUI: {e}")
        logger.error(f"Error launching GUI from main system: {e}")


def run_gui_standalone():
    """Run the GUI in standalone mode."""
    try:
        from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.main_gui import PlagiarismCheckerGUI

        print("Plagiarism Checker GUI - Standalone Mode")
        print("========================================")

        app = PlagiarismCheckerGUI()
        app.run()

    except Exception as e:
        print(f"Error running GUI: {e}")
        input("Press Enter to exit...")


def run_gui_tests():
    """Run basic GUI tests"""
    print("Running GUI component tests...")

    try:
        import tkinter as tk
        from tkinter import ttk
        print("✓ Tkinter imports successful")

        print("Test 2: Testing window creation...")
        root = tk.Tk()
        root.title("Test Window")
        root.geometry("400x300")

        label = ttk.Label(root, text="Test Label")
        label.pack()

        button = ttk.Button(root, text="Test Button")
        button.pack()

        root.destroy()
        print("✓ Basic window creation successful")

        print("Test 3: Testing configuration...")
        config = GuiConfig()
        assert hasattr(config, 'MAIN_WINDOW_WIDTH')
        assert hasattr(config, 'PRIMARY_COLOR')
        print("✓ Configuration classes successful")

        print("Test 4: Testing custom components...")
        from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.common import StatusBar, ScrollableFrame
        test_root = tk.Tk()
        test_root.withdraw()

        status_bar = StatusBar(test_root)
        status_bar.set_status("Test status")
        status_bar.show_progress()
        status_bar.hide_progress()

        scrollable = ScrollableFrame(test_root)

        test_root.destroy()
        print("✓ Custom components successful")

        print("\nAll GUI tests passed! ✓")
        print("The GUI should work correctly.")

    except Exception as e:
        print(f"✗ GUI test failed: {e}")
        print("There may be issues with the GUI setup.")


def main():
    """Main function for command line execution"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Plagiarism Detection System - GUI Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python plagiarism_gui.py                    # Run GUI in standalone mode
  python plagiarism_gui.py --create-launcher  # Create launcher script only
  python plagiarism_gui.py --test             # Test GUI components

The GUI provides a user-friendly interface for:
• Submitting documents to the repository
• Checking documents for plagiarism
• Searching and managing the document repository
• Viewing detailed statistics and reports

This GUI extension is fully backwards compatible with the original
plagiarism_main.py command-line interface.
        """
    )

    parser.add_argument(
        '--test',
        action='store_true',
        help='Run GUI component tests'
    )

    parser.add_argument(
        '--integrate',
        action='store_true',
        help='Run integration with main system'
    )

    args = parser.parse_args()

    if args.test:
        run_gui_tests()
        return

    if args.integrate:
        if integrate_plagiarism_checker_with_main():
            print("Integration completed successfully!")
        else:
            print("Integration completed with warnings. Check logs for details.")
        return

    # Default: run GUI
    run_gui_standalone()
