#!/usr/bin/env python3
"""
Parking Management System Launcher

This script provides a unified entry point for both GUI and console interfaces
while maintaining backward compatibility with the existing system.

Usage:
    python parking_launcher.py           # Launch GUI interface
    python parking_launcher.py --gui     # Launch GUI interface
    python parking_launcher.py --console # Launch console interface
    python parking_launcher.py --help    # Show help
"""

import sys
import os
import argparse
import tkinter as tk
from tkinter import messagebox

from university_system.modules.shared.utils.i18n import get_text

def check_dependencies():
    """Check if all required dependencies are available"""
    missing_deps = []
    
    # Check for GUI dependencies
    try:
        import tkinter
        import tkinter.ttk
    except ImportError:
        missing_deps.append("tkinter (required for GUI)")
    
    # Check for core dependencies
    try:
        from university_system.infrastructure.database.db import sqlite3
    except ImportError:
        missing_deps.append("sqlite3")
    
    try:
        from datetime import datetime, timedelta
    except ImportError:
        missing_deps.append("datetime")
    
    # Check for optional dependencies
    optional_missing = []
    
    try:
        import pandas
    except ImportError:
        optional_missing.append("pandas (for Excel export)")
    
    try:
        from reportlab.lib.pagesizes import letter
    except ImportError:
        optional_missing.append("reportlab (for PDF export)")
    
    if missing_deps:
        print(get_text("mobility.parking.error_missing_required_deps"))
        for dep in missing_deps:
            print(get_text("mobility.parking.dep_item", dep=dep))
        print(get_text("mobility.parking.install_missing_deps"))
        return False

    if optional_missing:
        print(get_text("mobility.parking.warning_missing_optional_deps"))
        for dep in optional_missing:
            print(get_text("mobility.parking.dep_item", dep=dep))
        print(get_text("mobility.parking.some_features_unavailable"))
    
    return True

def launch_gui():
    """Launch the GUI interface"""
    try:
        # Import the GUI module.  In the refactored package the services live
        # under ``refactored.services`` rather than ``utils.services``.  If a
        # GUI implementation exists it should be placed alongside
        # ``parking_management.py`` as ``parking_management_gui.py``.
        from university_system.modules.domain.mobility.services.parking_management_gui import ParkingManagementGUI
        
        print(get_text("mobility.parking.starting_gui"))
        
        # Create and run the GUI
        root = tk.Tk()
        app = ParkingManagementGUI(root)
        
        # Handle window closing
        def on_closing():
            if messagebox.askokcancel("Quit", "Do you want to quit?"):
                root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
        
    except ImportError as e:
        print(get_text("mobility.parking.error_import_gui", error=str(e)))
        print(get_text("mobility.parking.ensure_gui_in_directory"))
        return False
    except Exception as e:
        print(get_text("mobility.parking.error_launching_gui", error=str(e)))
        return False
    
    return True

def launch_console():
    """Launch the console interface"""
    try:
        # Import the original parking management module.  ``parking_management``
        # lives inside ``refactored.services``, not ``utils.services``.
        from university_system.modules.domain.mobility.services.parking_management import display_parking_menu, set_auth
        from university_system.infrastructure.auth import UserAuth
        from university_system.infrastructure.shared_context import get_auth

        print(get_text("mobility.parking.starting_console"))
        print("=" * 60)

        # Initialize authentication
        auth = get_auth()
        if auth is None:
            auth = UserAuth()
        set_auth(auth)
        
        # Run the original console interface
        display_parking_menu()
        
    except ImportError as e:
        print(f"Error: Could not import console module: {e}")
        print("Please ensure parking_management.py and required modules are available.")
        return False
    except Exception as e:
        print(f"Error launching console interface: {e}")
        return False
    
    return True

def show_interface_selection():
    """Show interface selection dialog"""
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        choice = messagebox.askyesnocancel(
            "Interface Selection",
            "Choose your preferred interface:\n\n"
            "Yes - GUI Interface (Graphical)\n"
            "No - Console Interface (Text-based)\n"
            "Cancel - Exit"
        )
        
        root.destroy()
        
        if choice is True:
            return "gui"
        elif choice is False:
            return "console"
        else:
            return "exit"
    except Exception:
        # Fallback to console if GUI selection fails
        print("GUI not available for interface selection.")
        print("Defaulting to console interface...")
        return "console"

def main():
    """Main launcher function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Parking Management System Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python parking_launcher.py              # Show interface selection dialog
  python parking_launcher.py --gui        # Launch GUI interface directly
  python parking_launcher.py --console    # Launch console interface directly
        """
    )
    
    parser.add_argument(
        '--gui', 
        action='store_true',
        help='Launch GUI interface'
    )
    
    parser.add_argument(
        '--console', 
        action='store_true',
        help='Launch console interface'
    )
    
    parser.add_argument(
        '--no-deps-check',
        action='store_true',
        help='Skip dependency check'
    )
    
    args = parser.parse_args()
    
    # Check dependencies (unless skipped)
    if not args.no_deps_check:
        print("Checking dependencies...")
        if not check_dependencies():
            sys.exit(1)
        print("Dependencies check passed.\n")
    
    # Determine which interface to launch
    interface = None
    
    if args.gui and args.console:
        print("Error: Cannot specify both --gui and --console")
        sys.exit(1)
    elif args.gui:
        interface = "gui"
    elif args.console:
        interface = "console"
    else:
        # No specific interface requested, show selection
        interface = show_interface_selection()
    
    # Launch the selected interface
    if interface == "gui":
        print("Launching GUI interface...")
        success = launch_gui()
    elif interface == "console":
        print("Launching console interface...")
        success = launch_console()
    elif interface == "exit":
        print("Exiting...")
        sys.exit(0)
    else:
        print("Error: Invalid interface selection")
        sys.exit(1)
    
    if not success:
        print("\nFailed to launch the selected interface.")
        
        # Offer fallback
        if interface == "gui":
            print("Would you like to try the console interface instead? (y/n): ", end="")
            try:
                choice = input().lower().strip()
                if choice in ['y', 'yes']:
                    print("\nFalling back to console interface...")
                    success = launch_console()
            except KeyboardInterrupt:
                print("\nExiting...")
                sys.exit(1)
        
        if not success:
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)