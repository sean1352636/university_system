"""Entry points and backward compatibility for the backup GUI system."""
import os
import sys
import tkinter as tk
from tkinter import messagebox

from education_system.post_18.university_system.modules.shared.gui.database.shared_imports import logger
from education_system.post_18.university_system.modules.shared.gui.database.config import config, save_config
from education_system.post_18.university_system.modules.shared.gui.database.scheduling.scheduler import stop_scheduler
from education_system.post_18.university_system.modules.shared.gui.database.operations.backup_ops import (
    create_enhanced_backup, validate_backup, list_available_backups,
)
from education_system.post_18.university_system.modules.shared.gui.database.operations.restore_ops import restore_from_backup


def start_backup_gui():
    """Start the GUI backup application"""
    # Lazy import to avoid circular imports
    from education_system.post_18.university_system.modules.shared.gui.database.backup_gui import BackupGUI

    root = tk.Tk()
    app = BackupGUI(root)

    # Handle window closing
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit the backup system?"):
            stop_scheduler()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")

    root.mainloop()

# Backward compatibility functions - these maintain the original CLI interface

def display_enhanced_backup_menu_gui():
    """GUI version of the enhanced backup menu with CLI fallback"""
    try:
        # Try to start GUI
        start_backup_gui()
    except Exception as e:
        print(f"Failed to start GUI: {e}")
        print("Falling back to CLI interface...")
        # Import and use original CLI function
    try:
        from education_system.post_18.university_system.infrastructure.database.data_backup import display_enhanced_backup_menu
    except ImportError:
        from education_system.post_18.university_system.infrastructure.database.data_backup import display_enhanced_backup_menu

def display_backup_menu_gui():
    """GUI version of backup menu with CLI fallback"""
    display_enhanced_backup_menu_gui()

def open_data_backup_gui():
    """GUI version of data backup with CLI fallback"""
    display_enhanced_backup_menu_gui()

# Entry point functions - these maintain full backward compatibility

def main():
    """Main entry point - detects if GUI is available"""
    import sys

    # Check for GUI flag
    if len(sys.argv) > 1 and sys.argv[1] in ['--gui', '-g']:
        start_backup_gui()
    elif len(sys.argv) > 1 and sys.argv[1] in ['--cli', '-c']:
        # Force CLI mode
        try:
            from education_system.post_18.university_system.infrastructure.database.data_backup import display_enhanced_backup_menu
        except ImportError:
            from education_system.post_18.university_system.infrastructure.database.data_backup import display_enhanced_backup_menu

    else:
        # Try GUI first, fall back to CLI
        try:
            start_backup_gui()
        except Exception as e:
            print(f"GUI not available ({e}), using CLI interface...")
        try:
            from education_system.post_18.university_system.infrastructure.database.data_backup import display_enhanced_backup_menu
        except ImportError:
            from education_system.post_18.university_system.infrastructure.database.data_backup import display_enhanced_backup_menu


# Legacy function names for backward compatibility
display_enhanced_backup_menu = display_enhanced_backup_menu_gui
display_backup_menu = display_backup_menu_gui
open_data_backup = open_data_backup_gui

# CLI integration functions

def create_backup_gui(*args, **kwargs):
    """GUI wrapper for create_backup function"""
    # For programmatic use, still use the original function
    return create_enhanced_backup(*args, **kwargs)

def backup_before_operation_gui(operation_name):
    """GUI wrapper for backup_before_operation"""
    return create_enhanced_backup(manual=False, operation_name=operation_name)

# System tray integration (optional)
try:
    import pystray
    from PIL import Image

    class SystemTrayApp:
        """System tray application for backup system"""

        def __init__(self):
            self.icon = None
            self.gui_app = None

        def create_image(self):
            """Create tray icon image"""
            # Create a simple icon (in real implementation, use proper icon file)
            return Image.new('RGB', (64, 64), color='blue')

        def show_gui(self, icon, item):
            """Show GUI from system tray"""
            if self.gui_app is None:
                # Lazy import to avoid circular imports
                from education_system.post_18.university_system.modules.shared.gui.database.backup_gui import BackupGUI

                root = tk.Tk()
                self.gui_app = BackupGUI(root)
                root.mainloop()

        def quit_app(self, icon, item):
            """Quit application"""
            stop_scheduler()
            icon.stop()

        def start(self):
            """Start system tray application"""
            menu = pystray.Menu(
                pystray.MenuItem("Open Backup System", self.show_gui),
                pystray.MenuItem("Quit", self.quit_app)
            )

            self.icon = pystray.Icon("BackupSystem", self.create_image(), "Backup System", menu)
            self.icon.run()

    def start_system_tray():
        """Start system tray version"""
        app = SystemTrayApp()
        app.start()

except ImportError:
    def start_system_tray():
        """Fallback when pystray not available"""
        print("System tray not available, starting regular GUI...")
        start_backup_gui()

# Command line interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Data Backup System")
    parser.add_argument('--gui', '-g', action='store_true', help='Start GUI interface')
    parser.add_argument('--cli', '-c', action='store_true', help='Start CLI interface')
    parser.add_argument('--tray', '-t', action='store_true', help='Start system tray version')
    parser.add_argument('--backup', '-b', action='store_true', help='Create quick backup and exit')
    parser.add_argument('--restore', '-r', metavar='BACKUP_FILE', help='Restore from specific backup file')
    parser.add_argument('--validate', '-v', metavar='BACKUP_FILE', help='Validate specific backup file')
    parser.add_argument('--list', '-l', action='store_true', help='List available backups')

    args = parser.parse_args()

    if args.backup:
        # Quick backup
        print("Creating backup...")
        result = create_enhanced_backup(manual=True)
        if result:
            print(f"Backup created: {result}")
        else:
            print("Backup failed!")
            sys.exit(1)

    elif args.restore:
        # Restore from backup
        print(f"Restoring from {args.restore}...")
        success = restore_from_backup(args.restore)
        if success:
            print("Restore completed successfully!")
        else:
            print("Restore failed!")
            sys.exit(1)

    elif args.validate:
        # Validate backup
        print(f"Validating {args.validate}...")
        results = validate_backup(args.validate)

        print("Validation Results:")
        print(f"File exists: {'✓' if results['file_exists'] else '✗'}")
        print(f"File readable: {'✓' if results['file_readable'] else '✗'}")
        print(f"Database valid: {'✓' if results['database_valid'] else '✗'}")
        print(f"Tables accessible: {'✓' if results['tables_accessible'] else '✗'}")
        print(f"Hash verified: {'✓' if results['hash_verified'] else '✗'}")

        if results['errors']:
            print("Errors:")
            for error in results['errors']:
                print(f"  \u2022 {error}")

    elif args.list:
        # List backups
        backups = list_available_backups()
        if backups:
            print(f"{'ID':<4} {'Type':<12} {'Date':<20} {'Size':<12} {'File'}")
            print("-" * 80)
            for backup in backups:
                print(f"{backup['id']:<4} {backup.get('backup_type', 'full'):<12} "
                      f"{backup['date_formatted']:<20} {backup['size_formatted']:<12} "
                      f"{backup['filename']}")
        else:
            print("No backups found")

    elif args.tray:
        # System tray
        start_system_tray()

    elif args.cli:
        # CLI interface
        try:
            from education_system.post_18.university_system.infrastructure.database.data_backup import display_enhanced_backup_menu
        except ImportError:
            from education_system.post_18.university_system.infrastructure.database.data_backup import display_enhanced_backup_menu


    elif args.gui:
        # GUI interface
        start_backup_gui()

    else:
        # Default behavior - try GUI, fall back to CLI
        main()

# Module-level imports for backward compatibility
if __name__ != "__main__":
    # When imported as module, expose all original functions
    # This ensures 100% backward compatibility
    try:
        from education_system.post_18.university_system.infrastructure.database.data_backup import (
            calculate_file_hash, cleanup_old_backups, compare_backups,
            compare_table_data, compress_file, create_enhanced_backup,
            create_incremental_backup, create_schema_only_backup,
            create_selective_backup, decompress_file, decrypt_file,
            delete_backup, display_backup_menu, display_enhanced_backup_menu,
            download_from_aws_s3, encrypt_file, ensure_backup_directory,
            export_to_csv, export_to_json, export_to_xml,
            generate_backup_statistics, generate_encryption_key,
            get_database_tables, get_database_tables_from_connection,
            has_database_changed, list_available_backups, load_backup_template,
            load_config, notify_backup_result, open_data_backup,
            parse_cron_schedule, restore_from_backup, restore_partial_tables,
            save_backup_template, save_config, scheduled_backup_job,
            secure_delete_file, send_discord_notification, send_email_notification,
            send_slack_notification, start_scheduler, stop_scheduler,
            upload_to_aws_s3, upload_to_ftp, upload_to_sftp, validate_backup,
            verify_backup_integrity
        )

        # Override the display functions to use GUI versions
        original_display_enhanced_backup_menu = display_enhanced_backup_menu
        original_display_backup_menu = display_backup_menu
        original_open_data_backup = open_data_backup

        def display_enhanced_backup_menu(*args, **kwargs):
            """Enhanced backup menu with GUI support"""
            try:
                return display_enhanced_backup_menu_gui(*args, **kwargs)
            except Exception:
                return original_display_enhanced_backup_menu(*args, **kwargs)

        def display_backup_menu(*args, **kwargs):
            """Backup menu with GUI support"""
            try:
                return display_backup_menu_gui(*args, **kwargs)
            except Exception:
                return original_display_backup_menu(*args, **kwargs)

        def open_data_backup(*args, **kwargs):
            """Data backup with GUI support"""
            try:
                return open_data_backup_gui(*args, **kwargs)
            except Exception:
                return original_open_data_backup(*args, **kwargs)

    except ImportError as e:
        print(f"Warning: Could not import original backup functions: {e}")
        print("GUI-only mode active.")
