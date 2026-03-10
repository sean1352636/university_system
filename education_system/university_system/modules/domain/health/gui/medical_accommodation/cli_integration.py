# cli_integration.py
# CLI integration mixin, standalone functions, and main entry point.

from ._common import (
    tk, ttk, messagebox, ScrolledText,
    os, sys, threading, datetime, json, logging,
    Path, sqlite3,
    CLI_AVAILABLE, get_connection, logger,
)

if CLI_AVAILABLE:
    from ._common import (
        display_accommodation_menu, verify_database_schema,
        migrate_audit_log_schema, fix_accommodation_db_schema,
        log_action,
    )


class CliIntegrationMixin:
    """CLI integration and database admin methods for AccommodationGUI."""

    def launch_cli(self):
        """Launch CLI mode"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        if messagebox.askyesno("Launch CLI",
            "This will open the command-line interface in a new window. Continue?"):

            try:
                thread = threading.Thread(target=self.run_cli_mode)
                thread.daemon = True
                thread.start()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to launch CLI: {str(e)}")

    def run_cli_mode(self):
        """Run CLI mode in background"""
        try:
            display_accommodation_menu()
        except Exception as e:
            print(f"CLI error: {e}")

    def migrate_database_schema(self):
        """Run database schema migration"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        try:
            result = messagebox.askyesno("Database Migration",
                "This will update the database schema. Continue?")
            if not result:
                return

            self.status_var.set("Running database migration...")
            self.root.update()

            success1 = migrate_audit_log_schema()
            success2 = fix_accommodation_db_schema()

            if success1 and success2:
                messagebox.showinfo("Success", "Database migration completed successfully")
            else:
                messagebox.showwarning("Warning", "Migration completed with some issues. Check logs.")

            self.status_var.set("Migration completed")

        except Exception as e:
            messagebox.showerror("Error", f"Migration failed: {str(e)}")
            self.status_var.set("Migration failed")

    def verify_db_schema(self):
        """Verify database schema and display results"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        try:
            import io
            import contextlib

            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                verify_database_schema()

            result = output.getvalue()

            result_window = tk.Toplevel(self.root)
            result_window.title("Database Schema Verification")
            result_window.geometry("700x600")

            main_frame = ttk.Frame(result_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text="Database Schema Information",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 10))

            text_frame = ttk.Frame(main_frame)
            text_frame.pack(fill=tk.BOTH, expand=True)

            text_widget = ScrolledText(text_frame, wrap=tk.WORD, width=80, height=30)
            text_widget.pack(fill=tk.BOTH, expand=True)
            text_widget.insert('1.0', result)
            text_widget.config(state='disabled')

            ttk.Button(main_frame, text="Close",
                      command=result_window.destroy).pack(pady=10)

            if CLI_AVAILABLE:
                log_action('verify_schema', None, 'Verified database schema')

        except Exception as e:
            messagebox.showerror("Error", f"Schema verification failed: {str(e)}")


# --- Standalone Functions ---

def integrate_with_original_cli():
    """Integrate GUI option into the original CLI accommodation menu.

    Returns:
        bool: True if the integration succeeded, False otherwise.
    """
    if not CLI_AVAILABLE:
        logging.info("Accommodation CLI not available; skipping GUI integration.")
        return False

    try:
        cli_module = sys.modules.get(
            "university_system.modules.domain.housing.services.accommodation"
        )
        if cli_module is None:
            import importlib
            cli_module = importlib.import_module(
                "university_system.modules.domain.housing.services.accommodation"
            )
    except Exception as err:
        logging.error("Failed to import accommodation CLI module: %s", err)
        return False

    if getattr(cli_module, "_gui_menu_patched", False):
        return True

    def launch_gui_from_cli():
        """Helper that launches the GUI, used by injected CLI menu option."""
        print("\nLaunching Accommodation GUI...\n")
        try:
            main()
        except Exception as exc:
            logging.exception("Accommodation GUI failed to start from CLI: %s", exc)
            print(f"Unable to start the GUI: {exc}")
            input("Press Enter to return to the CLI menu...")

    def gui_enabled_menu():
        """CLI menu function with an additional option for launching the GUI."""
        cli_module.init_accommodation_db()

        options = {
            '0': ('Launch GUI Interface', launch_gui_from_cli, []),
            '1': ('Register Student Accommodation', cli_module.add_accommodation, ['manage_accommodations']),
            '2': ('Bulk Import from CSV', cli_module.bulk_import_from_csv, ['manage_accommodations', 'batch_operations']),
            '3': ('Import from JSON', cli_module.import_from_json, ['manage_accommodations', 'batch_operations']),
            '4': ('Save Template', cli_module.save_template, ['manage_accommodations']),
            '5': ('Apply Template', cli_module.apply_template, ['manage_accommodations']),
            '6': ('Search/Filter Accommodations', cli_module.view_accommodations, ['view_accommodations']),
            '7': ('Update Accommodation', cli_module.update_accommodation, ['manage_accommodations']),
            '8': ('Remove Accommodation', cli_module.remove_accommodation, ['manage_accommodations']),
            '9': ('View by Accommodation Type', cli_module.view_students_by_accommodation, ['view_accommodations']),
            '10': ('Approve/Reject Accommodations', cli_module.approve_accommodation, ['approve_accommodations']),
            '11': ('Export Data', cli_module.export_accommodations, ['export_data']),
            '12': ('Check Expiry Notifications', cli_module.check_expiry_notifications, ['manage_accommodations']),
            '13': ('Dashboard Metrics', cli_module.show_dashboard_metrics, ['view_accommodations']),
            '14': ('Generate Statistics Report', cli_module.generate_statistics_report, ['view_accommodations']),
            '15': ('Return to Main Menu', None, [])
        }

        while True:
            print("\nAccommodation Management:")
            print("=" * 40)

            available_options = []
            current_auth = getattr(cli_module, "auth", None)
            for key, (desc, _, required_perms) in options.items():
                if not current_auth or not required_perms or not getattr(current_auth, "current_user", None):
                    print(f"{key}. {desc}")
                    available_options.append(key)
                elif all(current_auth.check_permission(perm) for perm in required_perms):
                    print(f"{key}. {desc}")
                    available_options.append(key)

            choice = input("\nEnter your choice: ").strip()

            if choice not in options:
                print("Invalid choice. Please try again.")
                continue

            if choice not in available_options:
                print("You don't have permission to access that option.")
                continue

            desc, handler, _ = options[choice]
            if handler is None:
                break

            try:
                if handler is cli_module.bulk_import_from_csv:
                    filepath = input("CSV file path: ").strip()
                    handler(filepath)
                else:
                    handler()
            except Exception as exc:
                logging.exception("Menu action '%s' failed: %s", desc, exc)
                print(f"An error occurred during {desc}: {exc}")
                print("Please try again or contact technical support.")

    cli_module.display_accommodation_menu = gui_enabled_menu
    cli_module._gui_menu_patched = True
    logging.info("Accommodation CLI menu patched to include GUI launch option.")
    return True


def export_gui_data_to_cli_format(output_path=None):
    """Export GUI-managed accommodation data in a format compatible with CLI imports.

    Args:
        output_path: Optional path for the JSON file.

    Returns:
        tuple[list[dict], str]: The exported records and the file path written to disk.
    """
    if not CLI_AVAILABLE:
        logging.info("Accommodation CLI not available; GUI export skipped.")
        return [], ""

    export_records = []
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT id, student_id, accommodation_type, description,
                       start_date, end_date, status, notes,
                       created_at, updated_at
                FROM accommodations
                ORDER BY created_at ASC
                '''
            )
            export_records = [dict(row) for row in cursor.fetchall()]
    except Exception as err:
        logging.error("Failed to gather accommodation data for CLI export: %s", err)
        raise

    if output_path is None:
        try:
            from education_system.university_system.modules.shared.constants import paths
            export_dir = Path(paths.DATA_DIR) / "exports"
        except Exception:
            export_dir = Path.cwd() / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = export_dir / f"accommodations_gui_export_{timestamp}.json"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open('w', encoding='utf-8') as handle:
        json.dump(export_records, handle, indent=2, default=str)

    logging.info("Accommodation GUI data exported for CLI import: %s", output_path)
    return export_records, os.fspath(output_path)


def main():
    """Main function to run the GUI application"""
    # Import here to avoid circular imports
    from .main_gui import AccommodationGUI

    root = tk.Tk()

    # Set up global auth if available
    if CLI_AVAILABLE:
        try:
            from ._common import auth
        except (ImportError, AttributeError):
            pass

    app = AccommodationGUI(root)

    # Set up keyboard shortcuts
    app.setup_keyboard_shortcuts()

    # Set window icon (if icon file exists)
    try:
        if os.path.exists('icon.ico'):
            root.iconbitmap('icon.ico')
    except Exception as e:
        logger.debug(f"Failed to set window icon: {e}")

    # Start the application
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplication closed by user")
    except Exception as e:
        print(f"Application error: {e}")
        if CLI_AVAILABLE:
            print("Falling back to CLI mode...")
            display_accommodation_menu()
