"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def run_library_system_with_gui_option():
    """Run library system with option to choose CLI or GUI"""

    if len(sys.argv) > 1 and sys.argv[1] in ['--gui', '-g']:
        # GUI mode
        print("Starting Library Management System - GUI Mode")
        start_gui_library_system()
    elif len(sys.argv) > 1 and sys.argv[1] in ['--cli', '-c']:
        # CLI mode
        print("Starting Library Management System - CLI Mode")
        if ORIGINAL_LIBRARY_AVAILABLE:
            display_library_menu()
        else:
            print("CLI mode requires original library module")
    else:
        # Ask user preference
        print("Enhanced Library Management System")
        print("=================================")
        print("1. GUI Mode (Recommended)")
        print("2. CLI Mode (Traditional)")
        print("3. Exit")

        choice = input("Choose interface (1-3): ").strip()

        if choice == '1':
            start_gui_library_system()
        elif choice == '2':
            if ORIGINAL_LIBRARY_AVAILABLE:
                display_library_menu()
            else:
                print("CLI mode requires original library module")
                start_gui_library_system()
        else:
            print("Goodbye!")
