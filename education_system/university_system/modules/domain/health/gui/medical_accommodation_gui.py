# accommodation_gui.py
# Backward-compatible wrapper — all code has been refactored into the
# medical_accommodation package.  This file re-exports the public API so
# that existing ``from … import medical_accommodation_gui`` statements
# continue to work unchanged.

from education_system.university_system.modules.domain.health.gui.medical_accommodation import (  # noqa: F401
    AccommodationGUI,
    main,
    integrate_with_original_cli,
    export_gui_data_to_cli_format,
    resolve_user_identifier,
    check_conflict,
    validate_gui_input,
    create_tooltip,
    format_date_display,
    get_status_color,
    gui_error_handler,
    GUI_CONFIG,
    GUI_VERSION,
)

# Re-export dialog classes for any code that imported them directly
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs import (  # noqa: F401
    AccommodationDialog,
    DetailsDialog,
    DocumentUploadDialog,
    ExportFilterDialog,
    ImportResultDialog,
    DatabaseInfoDialog,
    SettingsDialog,
    HelpDialog,
)
from education_system.university_system.modules.domain.health.gui.medical_accommodation.approval import ApprovalDialog  # noqa: F401
from education_system.university_system.modules.domain.health.gui.medical_accommodation.templates import (  # noqa: F401
    TemplateDialog,
    ApplyTemplateDialog,
    TemplateManagerDialog,
)
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dashboard import (  # noqa: F401
    StatisticsDialog,
    ExpiryResultDialog,
)
from education_system.university_system.modules.domain.health.gui.medical_accommodation.bulk_operations import BulkOperationsDialog  # noqa: F401

# Keep CLI_AVAILABLE accessible for anything that checked it
from education_system.university_system.modules.domain.health.gui.medical_accommodation._common import CLI_AVAILABLE  # noqa: F401

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == '--gui':
            main()
        elif sys.argv[1] == '--cli':
            if CLI_AVAILABLE:
                from education_system.university_system.modules.domain.health.gui.medical_accommodation._common import display_accommodation_menu
                display_accommodation_menu()
            else:
                print("CLI mode not available - original accommodation module not found")
        elif sys.argv[1] == '--help':
            print("Student Accommodation Management System")
            print("Usage:")
            print("  python accommodation_gui.py           # Auto-detect mode")
            print("  python accommodation_gui.py --gui     # Force GUI mode")
            print("  python accommodation_gui.py --cli     # Force CLI mode")
            print("  python accommodation_gui.py --help    # Show this help")
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information")
    else:
        try:
            import tkinter  # noqa: F401
            main()
        except ImportError:
            print("GUI not available (tkinter not installed). Using CLI mode...")
            if CLI_AVAILABLE:
                from education_system.university_system.modules.domain.health.gui.medical_accommodation._common import display_accommodation_menu
                display_accommodation_menu()
            else:
                print("Neither GUI nor CLI mode available.")
        except Exception as e:
            print(f"GUI failed to start: {e}")
            print("Falling back to CLI mode...")
            if CLI_AVAILABLE:
                from education_system.university_system.modules.domain.health.gui.medical_accommodation._common import display_accommodation_menu
                display_accommodation_menu()
            else:
                print("CLI mode also not available.")
