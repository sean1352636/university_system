"""Export and utility mixin for ParkingManagementGUI."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from education_system.post_18.university_system.modules.domain.campus.mobility.gui.parking_management import _t, DEFAULT_DB_PATH

# These service functions are only available when PARKING_MANAGEMENT_AVAILABLE is True
try:
    from education_system.post_18.university_system.modules.domain.campus.mobility.gui.parking_management import (
        export_permits, export_vehicles, export_violations, export_parking_lots, export_users,
    )
except ImportError:
    export_permits = export_vehicles = export_violations = export_parking_lots = export_users = None


class ExportsMixin:
    """Mixin providing export and database utility functionality."""

    def show_export_dialog(self):
        """Show export dialog with multiple options"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Export Data")
        dialog.geometry("350x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Export Options", font=("Arial", 12, "bold")).pack(pady=(0, 20))

        # Quick export buttons
        ttk.Label(main_frame, text="Quick Export:").pack(anchor="w", pady=(0, 5))

        quick_frame = ttk.Frame(main_frame)
        quick_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Button(quick_frame, text="Export Permits (CSV)",
                  command=lambda: export_permits('csv')).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Export Vehicles (CSV)",
                  command=lambda: export_vehicles('csv')).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Export Violations (CSV)",
                  command=lambda: export_violations('csv')).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Export Parking Lots (CSV)",
                  command=lambda: export_parking_lots('csv')).pack(fill=tk.X, pady=2)

        # Advanced options
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        ttk.Button(main_frame, text="Advanced Export Options",
                  command=self.show_advanced_export_dialog).pack(fill=tk.X, pady=5)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def show_advanced_export_dialog(self):
        """Show advanced export options dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Export Options")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Advanced Export Options", font=("Arial", 12, "bold")).pack(pady=(0, 20))

        # Export type
        ttk.Label(main_frame, text="Export Type:").pack(anchor="w")
        export_type_var = tk.StringVar()
        export_types = [
            ("All Data (Complete Export)", "all"),
            ("Permits Only", "permits"),
            ("Vehicles Only", "vehicles"),
            ("Violations Only", "violations"),
            ("Parking Lots Only", "lots"),
            ("Users Only", "users")
        ]

        for text, value in export_types:
            ttk.Radiobutton(main_frame, text=text, variable=export_type_var, value=value).pack(anchor="w")

        export_type_var.set("all")

        ttk.Label(main_frame, text="").pack()  # Spacer

        # Format type
        ttk.Label(main_frame, text="Format:").pack(anchor="w")
        format_var = tk.StringVar()
        formats = [("CSV", "csv"), ("Excel", "excel"), ("PDF", "pdf"), ("Text", "txt")]

        for text, value in formats:
            ttk.Radiobutton(main_frame, text=text, variable=format_var, value=value).pack(anchor="w")

        format_var.set("csv")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)

        def export_data():
            export_type = export_type_var.get()
            format_type = format_var.get()

            try:
                if export_type == "all":
                    export_permits(format_type)
                    export_vehicles(format_type)
                    export_violations(format_type)
                    export_parking_lots(format_type)
                    messagebox.showinfo("Success", "All data exported successfully!")
                elif export_type == "permits":
                    export_permits(format_type)
                elif export_type == "vehicles":
                    export_vehicles(format_type)
                elif export_type == "violations":
                    export_violations(format_type)
                elif export_type == "lots":
                    export_parking_lots(format_type)
                elif export_type == "users":
                    export_users(format_type)

                dialog.destroy()
                self.update_status(f"{export_type.title()} exported successfully")

            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}")

        ttk.Button(button_frame, text="Export", command=export_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def backup_database(self):
        """Backup the database"""
        try:
            import shutil

            # Get backup location
            backup_path = filedialog.asksaveasfilename(
                title="Save Database Backup",
                defaultextension=".db",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )

            if backup_path:
                # Copy current database
                current_db = str(DEFAULT_DB_PATH)
                shutil.copy2(current_db, backup_path)

                self.update_status("Database backed up successfully")
                messagebox.showinfo("Success", f"Database backed up to {backup_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to backup database: {e}")
