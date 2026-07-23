import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector
from education_system.post_18.university_system.modules.domain.student_affairs.gui.student_union_gui.equipment.equipment_browse import (
    BrowseAvailableEquipmentDialog, SearchEquipmentDialog
)
from education_system.post_18.university_system.modules.domain.student_affairs.gui.student_union_gui.equipment.equipment_checkout import (
    CheckOutEquipmentDialog, ReturnEquipmentDialog, ViewMyEquipmentCheckoutsDialog
)

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
    from education_system.post_18.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class ManageEquipmentSystemDialog:
    """Main hub for equipment management system"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Equipment Management System")
        self.dialog.geometry("950x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🎬 Equipment Management",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # System overview
        overview_frame = ttk.LabelFrame(main_frame, text="System Overview")
        overview_frame.pack(fill='x', pady=(0, 15))

        overview_grid = ttk.Frame(overview_frame)
        overview_grid.pack(fill='x', padx=15, pady=10)

        ttk.Label(overview_grid, text="Total Equipment:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="156 items").grid(row=0, column=1, sticky='w', padx=10)

        ttk.Label(overview_grid, text="Available Now:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="98 items (63%)", foreground='green').grid(row=1, column=1, sticky='w', padx=10)

        ttk.Label(overview_grid, text="Checked Out:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="45 items (29%)").grid(row=2, column=1, sticky='w', padx=10)

        ttk.Label(overview_grid, text="Under Maintenance:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="13 items (8%)", foreground='orange').grid(row=3, column=1, sticky='w', padx=10)

        # Action cards
        cards_frame = ttk.Frame(main_frame)
        cards_frame.pack(fill='both', expand=True, pady=(0, 15))

        # Row 1
        row1 = ttk.Frame(cards_frame)
        row1.pack(fill='x', pady=(0, 10))

        self.create_action_card(row1, "📋 Browse Equipment", "View all available equipment", self.browse_equipment).pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_action_card(row1, "🔍 Search Equipment", "Find specific items", self.search_equipment).pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_action_card(row1, "✅ Check Out", "Borrow equipment", self.checkout_equipment).pack(side='left', fill='both', expand=True)

        # Row 2
        row2 = ttk.Frame(cards_frame)
        row2.pack(fill='x', pady=(0, 10))

        self.create_action_card(row2, "↩️ Return Equipment", "Return borrowed items", self.return_equipment).pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_action_card(row2, "📚 My Checkouts", "View your borrowed items", self.my_checkouts).pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_action_card(row2, "🔧 Maintenance", "Track repairs & maintenance", self.maintenance_tracking).pack(side='left', fill='both', expand=True)

        # Admin section (if admin)
        if True:  # Check admin status
            admin_frame = ttk.LabelFrame(main_frame, text="Admin Functions")
            admin_frame.pack(fill='x', pady=(0, 15))

            admin_buttons = ttk.Frame(admin_frame)
            admin_buttons.pack(padx=15, pady=10)

            ttk.Button(admin_buttons, text="➕ Add New Equipment", command=self.add_equipment, width=20).pack(side='left', padx=(0, 10))
            ttk.Button(admin_buttons, text="📊 Generate Reports", command=self.generate_reports, width=20).pack(side='left', padx=(0, 10))
            ttk.Button(admin_buttons, text="⚙️ Update Status", command=self.update_status, width=20).pack(side='left')

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def create_action_card(self, parent, title, description, command):
        card = ttk.Frame(parent, relief='raised', borderwidth=1)

        ttk.Label(card, text=title, font=('Arial', 11, 'bold')).pack(pady=(10, 5), padx=10)
        ttk.Label(card, text=description, font=('Arial', 9), wraplength=150).pack(pady=(0, 10), padx=10)
        ttk.Button(card, text="Open", command=command).pack(pady=(0, 10))

        return card

    def browse_equipment(self):
        from tkinter import messagebox
        dialog = BrowseAvailableEquipmentDialog(self.dialog, self.auth)

    def search_equipment(self):
        dialog = SearchEquipmentDialog(self.dialog, self.auth)

    def checkout_equipment(self):
        dialog = CheckOutEquipmentDialog(self.dialog, self.auth)

    def return_equipment(self):
        dialog = ReturnEquipmentDialog(self.dialog, self.auth)

    def my_checkouts(self):
        dialog = ViewMyEquipmentCheckoutsDialog(self.dialog, self.auth)

    def maintenance_tracking(self):
        dialog = EquipmentMaintenanceTrackingDialog(self.dialog, self.auth)

    def add_equipment(self):
        dialog = AddNewEquipmentDialog(self.dialog, self.auth)

    def generate_reports(self):
        dialog = GenerateEquipmentReportsDialog(self.dialog, self.auth)

    def update_status(self):
        dialog = UpdateEquipmentStatusDialog(self.dialog, self.auth)



class AddNewEquipmentDialog:
    """Dialog for adding new equipment (admin)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Equipment")
        self.dialog.geometry("700x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.field_widgets = {}
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Add New Equipment",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Scrollable form
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Form fields - key maps to DB column or internal name
        form_frame = ttk.Frame(scrollable_frame)
        form_frame.pack(fill='both', expand=True, padx=15, pady=10)

        fields = [
            ("equipment_name", "Equipment Name:*", "Entry"),
            ("category", "Category:*", "Combo", ('Audio Equipment', 'Video Equipment', 'Lighting', 'Computers', 'Sports Equipment', 'Event Supplies', 'Other')),
            ("description", "Description:", "Text"),
            ("serial_number", "Serial Number:", "Entry"),
            ("purchase_date", "Purchase Date (YYYY-MM-DD):", "Entry"),
            ("condition_status", "Condition:", "Combo", ('good', 'fair', 'poor')),
            ("location", "Location:", "Entry"),
            ("replacement_cost", "Replacement Cost:", "Entry"),
        ]

        for i, field_info in enumerate(fields):
            key = field_info[0]
            label = field_info[1]
            field_type = field_info[2]

            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky='nw', pady=5)

            if field_type == "Entry":
                widget = ttk.Entry(form_frame, width=45)
                widget.grid(row=i, column=1, sticky='ew', padx=10, pady=5)
                self.field_widgets[key] = widget
            elif field_type == "Combo":
                widget = ttk.Combobox(form_frame, width=43, state='readonly')
                widget['values'] = field_info[3]
                widget.current(0)
                widget.grid(row=i, column=1, sticky='ew', padx=10, pady=5)
                self.field_widgets[key] = widget
            elif field_type == "Text":
                widget = scrolledtext.ScrolledText(form_frame, height=3, width=45)
                widget.grid(row=i, column=1, sticky='ew', padx=10, pady=5)
                self.field_widgets[key] = widget

        form_frame.columnconfigure(1, weight=1)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Add Equipment", command=self.add_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='right')

    def _get_field_value(self, key):
        """Get the value from a form field widget."""
        widget = self.field_widgets.get(key)
        if widget is None:
            return ""
        if isinstance(widget, scrolledtext.ScrolledText):
            return widget.get("1.0", tk.END).strip()
        return widget.get().strip()

    def add_equipment(self):
        name = self._get_field_value("equipment_name")
        category = self._get_field_value("category")

        if not name:
            messagebox.showwarning("Validation Error", "Equipment Name is required.", parent=self.dialog)
            return
        if not category:
            messagebox.showwarning("Validation Error", "Category is required.", parent=self.dialog)
            return

        description = self._get_field_value("description")
        serial_number = self._get_field_value("serial_number")
        purchase_date = self._get_field_value("purchase_date")
        condition_status = self._get_field_value("condition_status") or "good"
        location = self._get_field_value("location")
        replacement_cost_str = self._get_field_value("replacement_cost")

        # Validate purchase date if provided
        if purchase_date:
            try:
                datetime.strptime(purchase_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showwarning("Validation Error",
                                       "Purchase Date must be in YYYY-MM-DD format.",
                                       parent=self.dialog)
                return

        # Validate replacement cost if provided
        replacement_cost = None
        if replacement_cost_str:
            try:
                replacement_cost = float(replacement_cost_str.replace(",", "").replace("£", "").replace("$", ""))
            except ValueError:
                messagebox.showwarning("Validation Error",
                                       "Replacement Cost must be a valid number.",
                                       parent=self.dialog)
                return

        try:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO union_equipment
                        (equipment_name, category, description, serial_number,
                         purchase_date, condition_status, location,
                         availability_status, replacement_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'available', ?)
                ''', (name, category, description or None, serial_number or None,
                      purchase_date or None, condition_status, location or None,
                      replacement_cost))
                conn.commit()
                new_id = cursor.lastrowid
            finally:
                conn.close()

            messagebox.showinfo("Equipment Added",
                                f"New equipment added successfully!\n\n"
                                f"Equipment ID: {new_id}\n"
                                f"Name: {name}\n"
                                f"Category: {category}\n"
                                f"Status: Available\n\n"
                                f"Equipment is now available for checkout.",
                                parent=self.dialog)
            self.dialog.destroy()
        except Exception as e:
            logging.error("Failed to add equipment: %s", e)
            messagebox.showerror("Database Error",
                                 f"Failed to add equipment:\n{e}",
                                 parent=self.dialog)



class UpdateEquipmentStatusDialog:
    """Dialog for updating equipment status (admin)"""

    STATUS_MAP = {
        'available': 'Available',
        'in_use': 'In Use',
        'checked_out': 'Checked Out',
        'maintenance': 'Maintenance',
        'maintenance_required': 'Maintenance',
        'damaged': 'Damaged',
        'retired': 'Retired',
    }

    STATUS_DB_VALUES = ('available', 'in_use', 'maintenance', 'damaged', 'retired')
    CONDITION_DB_VALUES = ('good', 'fair', 'poor')

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Update Equipment Status")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.tree = None
        self.status_combo = None
        self.condition_combo = None
        self.location_entry = None
        self.notes_text = None
        self.create_widgets()
        self.load_equipment()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Update Equipment Status",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Equipment list
        list_frame = ttk.LabelFrame(main_frame, text="Equipment Inventory")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Name', 'Category', 'Current Status', 'Condition', 'Location')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.tree.heading(col, text=col)
            if col == 'Name':
                self.tree.column(col, width=200)
            elif col == 'Category':
                self.tree.column(col, width=120)
            else:
                self.tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # Update form
        update_frame = ttk.LabelFrame(main_frame, text="Update Status")
        update_frame.pack(fill='x', pady=(0, 15))

        update_content = ttk.Frame(update_frame)
        update_content.pack(fill='x', padx=15, pady=10)

        ttk.Label(update_content, text="New Status:").grid(row=0, column=0, sticky='w', pady=5)
        self.status_combo = ttk.Combobox(update_content, width=25, state='readonly')
        self.status_combo['values'] = ('available', 'in_use', 'maintenance', 'damaged', 'retired')
        self.status_combo.current(0)
        self.status_combo.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(update_content, text="New Condition:").grid(row=1, column=0, sticky='w', pady=5)
        self.condition_combo = ttk.Combobox(update_content, width=25, state='readonly')
        self.condition_combo['values'] = ('good', 'fair', 'poor')
        self.condition_combo.current(0)
        self.condition_combo.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(update_content, text="New Location:").grid(row=2, column=0, sticky='w', pady=5)
        self.location_entry = ttk.Entry(update_content, width=27)
        self.location_entry.grid(row=2, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(update_content, text="Notes:").grid(row=3, column=0, sticky='nw', pady=5)
        self.notes_text = scrolledtext.ScrolledText(update_content, height=3, width=27)
        self.notes_text.grid(row=3, column=1, sticky='ew', padx=10, pady=5)

        update_content.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Update Status", command=self.update_status).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Refresh", command=self.load_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_equipment(self):
        """Load equipment from the database into the treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT equipment_id, equipment_name, category,
                           availability_status, condition_status, location
                    FROM union_equipment
                    ORDER BY equipment_id
                ''')
                rows = cursor.fetchall()
            finally:
                conn.close()

            for row in rows:
                display_status = self.STATUS_MAP.get(row[3], row[3] or 'Unknown')
                self.tree.insert('', 'end', values=(
                    row[0], row[1] or '', row[2] or '',
                    display_status, row[4] or '', row[5] or ''
                ))
        except Exception as e:
            logging.error("Failed to load equipment: %s", e)
            messagebox.showerror("Database Error",
                                 f"Failed to load equipment:\n{e}",
                                 parent=self.dialog)

    def update_status(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection",
                                   "Please select an equipment item to update.",
                                   parent=self.dialog)
            return

        item_values = self.tree.item(selected[0], 'values')
        equipment_id = item_values[0]
        old_status = item_values[3]
        equipment_name = item_values[1]

        new_status = self.status_combo.get()
        new_condition = self.condition_combo.get()
        new_location = self.location_entry.get().strip()

        try:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                if new_location:
                    cursor.execute('''
                        UPDATE union_equipment
                        SET availability_status = ?, condition_status = ?, location = ?
                        WHERE equipment_id = ?
                    ''', (new_status, new_condition, new_location, equipment_id))
                else:
                    cursor.execute('''
                        UPDATE union_equipment
                        SET availability_status = ?, condition_status = ?
                        WHERE equipment_id = ?
                    ''', (new_status, new_condition, equipment_id))
                conn.commit()
            finally:
                conn.close()

            messagebox.showinfo("Status Updated",
                                f"Equipment status updated!\n\n"
                                f"ID: {equipment_id} - {equipment_name}\n"
                                f"Old Status: {old_status}\n"
                                f"New Status: {self.STATUS_MAP.get(new_status, new_status)}\n"
                                f"Condition: {new_condition}",
                                parent=self.dialog)
            self.load_equipment()
        except Exception as e:
            logging.error("Failed to update equipment status: %s", e)
            messagebox.showerror("Database Error",
                                 f"Failed to update status:\n{e}",
                                 parent=self.dialog)



class EquipmentMaintenanceTrackingDialog:
    """Dialog for tracking equipment maintenance"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Equipment Maintenance Tracking")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.current_tree = None
        self.scheduled_tree = None
        self.create_widgets()
        self.load_maintenance_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Equipment Maintenance",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Current Maintenance tab - equipment with condition issues or maintenance status
        current_frame = ttk.Frame(notebook)
        notebook.add(current_frame, text="Needs Maintenance")

        current_columns = ('ID', 'Equipment', 'Category', 'Condition', 'Status', 'Location', 'Maintenance Due')
        self.current_tree = ttk.Treeview(current_frame, columns=current_columns, show='headings', height=10)

        for col in current_columns:
            self.current_tree.heading(col, text=col)
            if col == 'Equipment':
                self.current_tree.column(col, width=180)
            else:
                self.current_tree.column(col, width=110)

        current_scroll = ttk.Scrollbar(current_frame, orient='vertical', command=self.current_tree.yview)
        self.current_tree.configure(yscrollcommand=current_scroll.set)
        self.current_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        current_scroll.pack(side='right', fill='y', pady=10)

        # Scheduled Maintenance tab - equipment with upcoming maintenance_due dates
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text="Scheduled Maintenance")

        sched_columns = ('ID', 'Equipment', 'Category', 'Condition', 'Maintenance Due', 'Location')
        self.scheduled_tree = ttk.Treeview(schedule_frame, columns=sched_columns, show='headings', height=10)

        for col in sched_columns:
            self.scheduled_tree.heading(col, text=col)
            if col == 'Equipment':
                self.scheduled_tree.column(col, width=200)
            else:
                self.scheduled_tree.column(col, width=120)

        sched_scroll = ttk.Scrollbar(schedule_frame, orient='vertical', command=self.scheduled_tree.yview)
        self.scheduled_tree.configure(yscrollcommand=sched_scroll.set)
        self.scheduled_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        sched_scroll.pack(side='right', fill='y', pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Report Issue", command=self.report_issue).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Complete Maintenance", command=self.complete_maintenance).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Schedule Maintenance", command=self.schedule_maintenance).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Refresh", command=self.load_maintenance_data).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_maintenance_data(self):
        """Load maintenance-related equipment data from the database."""
        for tree in (self.current_tree, self.scheduled_tree):
            for item in tree.get_children():
                tree.delete(item)

        try:
            conn = get_connection()
            try:
                cursor = conn.cursor()

                # Needs maintenance: poor/damaged condition or maintenance/maintenance_required status
                cursor.execute('''
                    SELECT equipment_id, equipment_name, category,
                           condition_status, availability_status, location, maintenance_due
                    FROM union_equipment
                    WHERE availability_status IN ('maintenance', 'maintenance_required')
                       OR condition_status IN ('poor', 'damaged')
                       OR (maintenance_due IS NOT NULL AND maintenance_due <= date('now'))
                    ORDER BY maintenance_due, condition_status
                ''')
                for row in cursor.fetchall():
                    self.current_tree.insert('', 'end', values=(
                        row[0], row[1] or '', row[2] or '',
                        row[3] or '', row[4] or '', row[5] or '',
                        row[6] or 'Not scheduled'
                    ))

                # Scheduled: equipment with future maintenance_due
                cursor.execute('''
                    SELECT equipment_id, equipment_name, category,
                           condition_status, maintenance_due, location
                    FROM union_equipment
                    WHERE maintenance_due IS NOT NULL AND maintenance_due > date('now')
                    ORDER BY maintenance_due
                ''')
                for row in cursor.fetchall():
                    self.scheduled_tree.insert('', 'end', values=(
                        row[0], row[1] or '', row[2] or '',
                        row[3] or '', row[4] or '', row[5] or ''
                    ))
            finally:
                conn.close()
        except Exception as e:
            logging.error("Failed to load maintenance data: %s", e)
            messagebox.showerror("Database Error",
                                 f"Failed to load maintenance data:\n{e}",
                                 parent=self.dialog)

    def report_issue(self):
        """Show a form dialog to report an equipment issue."""
        report_dlg = tk.Toplevel(self.dialog)
        report_dlg.title("Report Equipment Issue")
        report_dlg.geometry("450x400")
        report_dlg.transient(self.dialog)
        report_dlg.grab_set()

        frame = ttk.Frame(report_dlg)
        frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(frame, text="Report Equipment Issue", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        form = ttk.Frame(frame)
        form.pack(fill='x')

        # Equipment ID
        ttk.Label(form, text="Equipment ID:").grid(row=0, column=0, sticky='w', pady=5)
        eq_id_entry = ttk.Entry(form, width=30)
        eq_id_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        # Pre-fill if selected in current tree
        selected = self.current_tree.selection()
        if selected:
            vals = self.current_tree.item(selected[0], 'values')
            eq_id_entry.insert(0, str(vals[0]))

        # Problem description
        ttk.Label(form, text="Problem:").grid(row=1, column=0, sticky='nw', pady=5)
        problem_text = scrolledtext.ScrolledText(form, height=4, width=30)
        problem_text.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        # Severity
        ttk.Label(form, text="Severity:").grid(row=2, column=0, sticky='w', pady=5)
        severity_combo = ttk.Combobox(form, width=28, state='readonly')
        severity_combo['values'] = ('Low', 'Medium', 'High', 'Critical')
        severity_combo.current(1)
        severity_combo.grid(row=2, column=1, sticky='ew', padx=10, pady=5)

        form.columnconfigure(1, weight=1)

        def submit_issue():
            eid = eq_id_entry.get().strip()
            problem = problem_text.get("1.0", tk.END).strip()
            severity = severity_combo.get()

            if not eid or not eid.isdigit():
                messagebox.showwarning("Validation Error", "Please enter a valid Equipment ID.",
                                       parent=report_dlg)
                return
            if not problem:
                messagebox.showwarning("Validation Error", "Please describe the problem.",
                                       parent=report_dlg)
                return

            try:
                conn = get_connection()
                try:
                    cursor = conn.cursor()
                    # Verify equipment exists
                    cursor.execute('SELECT equipment_name FROM union_equipment WHERE equipment_id = ?', (int(eid),))
                    eq_row = cursor.fetchone()
                    if not eq_row:
                        messagebox.showwarning("Not Found",
                                               f"Equipment ID {eid} not found.",
                                               parent=report_dlg)
                        return

                    # Update equipment condition to reflect issue
                    new_condition = 'poor' if severity in ('Low', 'Medium') else 'damaged'
                    cursor.execute('''
                        UPDATE union_equipment
                        SET condition_status = ?,
                            availability_status = 'maintenance_required'
                        WHERE equipment_id = ?
                    ''', (new_condition, int(eid)))
                    conn.commit()
                finally:
                    conn.close()

                messagebox.showinfo("Issue Reported",
                                    f"Issue reported for: {eq_row[0]}\n"
                                    f"Severity: {severity}\n"
                                    f"Equipment marked for maintenance.",
                                    parent=report_dlg)
                report_dlg.destroy()
                self.load_maintenance_data()
            except Exception as e:
                logging.error("Failed to report issue: %s", e)
                messagebox.showerror("Database Error",
                                     f"Failed to report issue:\n{e}",
                                     parent=report_dlg)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(15, 0))
        ttk.Button(btn_frame, text="Submit", command=submit_issue).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=report_dlg.destroy).pack(side='right')

    def complete_maintenance(self):
        """Mark the selected maintenance item as complete, update equipment condition."""
        selected = self.current_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection",
                                   "Please select an equipment item from the 'Needs Maintenance' tab.",
                                   parent=self.dialog)
            return

        item_values = self.current_tree.item(selected[0], 'values')
        equipment_id = item_values[0]
        equipment_name = item_values[1]

        # Ask for post-maintenance condition
        complete_dlg = tk.Toplevel(self.dialog)
        complete_dlg.title("Complete Maintenance")
        complete_dlg.geometry("400x250")
        complete_dlg.transient(self.dialog)
        complete_dlg.grab_set()

        frame = ttk.Frame(complete_dlg)
        frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(frame, text=f"Complete Maintenance for:\n{equipment_name} (ID: {equipment_id})",
                  font=('Arial', 10, 'bold')).pack(pady=(0, 10))

        form = ttk.Frame(frame)
        form.pack(fill='x')

        ttk.Label(form, text="Condition After:").grid(row=0, column=0, sticky='w', pady=5)
        cond_combo = ttk.Combobox(form, width=20, state='readonly')
        cond_combo['values'] = ('good', 'fair', 'poor')
        cond_combo.current(0)
        cond_combo.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(form, text="Next Maintenance\n(YYYY-MM-DD):").grid(row=1, column=0, sticky='w', pady=5)
        next_maint_entry = ttk.Entry(form, width=22)
        next_maint_entry.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        form.columnconfigure(1, weight=1)

        def do_complete():
            new_condition = cond_combo.get()
            next_date = next_maint_entry.get().strip() or None

            if next_date:
                try:
                    datetime.strptime(next_date, '%Y-%m-%d')
                except ValueError:
                    messagebox.showwarning("Validation Error",
                                           "Next maintenance date must be YYYY-MM-DD format.",
                                           parent=complete_dlg)
                    return

            new_availability = 'available' if new_condition in ('good', 'fair') else 'maintenance_required'

            try:
                conn = get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE union_equipment
                        SET condition_status = ?, availability_status = ?, maintenance_due = ?
                        WHERE equipment_id = ?
                    ''', (new_condition, new_availability, next_date, equipment_id))
                    conn.commit()
                finally:
                    conn.close()

                messagebox.showinfo("Maintenance Complete",
                                    f"Maintenance completed for {equipment_name}.\n"
                                    f"Condition: {new_condition}\n"
                                    f"Status: {new_availability}",
                                    parent=complete_dlg)
                complete_dlg.destroy()
                self.load_maintenance_data()
            except Exception as e:
                logging.error("Failed to complete maintenance: %s", e)
                messagebox.showerror("Database Error",
                                     f"Failed to complete maintenance:\n{e}",
                                     parent=complete_dlg)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(15, 0))
        ttk.Button(btn_frame, text="Complete", command=do_complete).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=complete_dlg.destroy).pack(side='right')

    def schedule_maintenance(self):
        """Show a form to schedule future maintenance for an equipment item."""
        sched_dlg = tk.Toplevel(self.dialog)
        sched_dlg.title("Schedule Maintenance")
        sched_dlg.geometry("420x280")
        sched_dlg.transient(self.dialog)
        sched_dlg.grab_set()

        frame = ttk.Frame(sched_dlg)
        frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(frame, text="Schedule Maintenance", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        form = ttk.Frame(frame)
        form.pack(fill='x')

        # Equipment selector
        ttk.Label(form, text="Equipment ID:").grid(row=0, column=0, sticky='w', pady=5)
        eq_id_entry = ttk.Entry(form, width=25)
        eq_id_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        # Pre-fill from selection in either tree
        for tree in (self.current_tree, self.scheduled_tree):
            sel = tree.selection()
            if sel:
                vals = tree.item(sel[0], 'values')
                eq_id_entry.insert(0, str(vals[0]))
                break

        ttk.Label(form, text="Maintenance Date\n(YYYY-MM-DD):").grid(row=1, column=0, sticky='w', pady=5)
        date_entry = ttk.Entry(form, width=25)
        date_entry.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(form, text="Notes:").grid(row=2, column=0, sticky='nw', pady=5)
        notes_entry = scrolledtext.ScrolledText(form, height=3, width=25)
        notes_entry.grid(row=2, column=1, sticky='ew', padx=10, pady=5)

        form.columnconfigure(1, weight=1)

        def do_schedule():
            eid = eq_id_entry.get().strip()
            maint_date = date_entry.get().strip()

            if not eid or not eid.isdigit():
                messagebox.showwarning("Validation Error",
                                       "Please enter a valid Equipment ID.",
                                       parent=sched_dlg)
                return
            if not maint_date:
                messagebox.showwarning("Validation Error",
                                       "Please enter a maintenance date.",
                                       parent=sched_dlg)
                return
            try:
                datetime.strptime(maint_date, '%Y-%m-%d')
            except ValueError:
                messagebox.showwarning("Validation Error",
                                       "Date must be in YYYY-MM-DD format.",
                                       parent=sched_dlg)
                return

            try:
                conn = get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute('SELECT equipment_name FROM union_equipment WHERE equipment_id = ?', (int(eid),))
                    eq_row = cursor.fetchone()
                    if not eq_row:
                        messagebox.showwarning("Not Found",
                                               f"Equipment ID {eid} not found.",
                                               parent=sched_dlg)
                        return

                    cursor.execute('''
                        UPDATE union_equipment
                        SET maintenance_due = ?
                        WHERE equipment_id = ?
                    ''', (maint_date, int(eid)))
                    conn.commit()
                finally:
                    conn.close()

                messagebox.showinfo("Maintenance Scheduled",
                                    f"Maintenance scheduled for {eq_row[0]}.\n"
                                    f"Date: {maint_date}",
                                    parent=sched_dlg)
                sched_dlg.destroy()
                self.load_maintenance_data()
            except Exception as e:
                logging.error("Failed to schedule maintenance: %s", e)
                messagebox.showerror("Database Error",
                                     f"Failed to schedule maintenance:\n{e}",
                                     parent=sched_dlg)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(15, 0))
        ttk.Button(btn_frame, text="Schedule", command=do_schedule).pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=sched_dlg.destroy).pack(side='right')



class GenerateEquipmentReportsDialog:
    """Dialog for generating equipment reports with real DB data"""

    REPORT_TYPES = [
        ("Inventory Report", "_generate_inventory"),
        ("Status Report", "_generate_status"),
        ("Maintenance Report", "_generate_maintenance"),
        ("Asset Valuation Report", "_generate_valuation"),
    ]

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.current_report_text = ""

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Equipment Reports")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.report_display = None
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Equipment Reports",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Report type buttons
        btn_frame = ttk.LabelFrame(main_frame, text="Generate Report")
        btn_frame.pack(fill='x', pady=(0, 10))
        btn_inner = ttk.Frame(btn_frame)
        btn_inner.pack(padx=10, pady=10)

        for label, method_name in self.REPORT_TYPES:
            ttk.Button(btn_inner, text=label,
                       command=lambda m=method_name: self._run_report(m)).pack(side='left', padx=(0, 10))

        # Report display area
        display_frame = ttk.LabelFrame(main_frame, text="Report Output")
        display_frame.pack(fill='both', expand=True, pady=(0, 10))

        self.report_display = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD, font=('Courier', 9))
        self.report_display.pack(fill='both', expand=True, padx=5, pady=5)
        self.report_display.insert('1.0', "Select a report type above to generate a report from live data.")
        self.report_display.config(state='disabled')

        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill='x')

        ttk.Button(action_frame, text="Save as TXT", command=self._save_as_txt).pack(side='left', padx=(0, 10))
        ttk.Button(action_frame, text="Email to Admin", command=self._email_to_admin).pack(side='left', padx=(0, 10))
        ttk.Button(action_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    # ------------------------------------------------------------------
    # Report generation helpers
    # ------------------------------------------------------------------

    def _run_report(self, method_name):
        """Dispatch to a report generator method."""
        method = getattr(self, method_name, None)
        if method is None:
            return
        try:
            report_text = method()
        except Exception as e:
            logging.error("Report generation failed: %s", e)
            report_text = f"Error generating report:\n{e}"

        self.current_report_text = report_text
        self.report_display.config(state='normal')
        self.report_display.delete('1.0', tk.END)
        self.report_display.insert('1.0', report_text)
        self.report_display.config(state='disabled')

    def _generate_inventory(self) -> str:
        """Full inventory report from union_equipment table."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT equipment_id, equipment_name, category, serial_number,
                       condition_status, availability_status, location,
                       purchase_date, replacement_cost
                FROM union_equipment
                ORDER BY category, equipment_name
            ''')
            rows = cursor.fetchall()
        finally:
            conn.close()

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            "EQUIPMENT INVENTORY REPORT",
            f"Generated: {now}",
            "=" * 90,
            f"Total items: {len(rows)}",
            "",
            f"{'ID':<6} {'Name':<30} {'Category':<18} {'Serial':<15} {'Cond.':<8} {'Status':<12} {'Location':<15}",
            "-" * 90,
        ]
        for r in rows:
            lines.append(
                f"{r[0]:<6} {(r[1] or '')[:29]:<30} {(r[2] or '')[:17]:<18} "
                f"{(r[3] or 'N/A')[:14]:<15} {(r[4] or '')[:7]:<8} "
                f"{(r[5] or '')[:11]:<12} {(r[6] or '')[:14]:<15}"
            )
        return "\n".join(lines)

    def _generate_status(self) -> str:
        """Status breakdown report."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM union_equipment')
            total = cursor.fetchone()[0]

            cursor.execute('''
                SELECT availability_status, COUNT(*) as cnt
                FROM union_equipment
                GROUP BY availability_status
                ORDER BY cnt DESC
            ''')
            status_rows = cursor.fetchall()

            cursor.execute('''
                SELECT condition_status, COUNT(*) as cnt
                FROM union_equipment
                GROUP BY condition_status
                ORDER BY cnt DESC
            ''')
            condition_rows = cursor.fetchall()

            cursor.execute('''
                SELECT COUNT(*) FROM equipment_checkouts WHERE status = 'checked_out'
            ''')
            active_checkouts = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM equipment_checkouts
                WHERE status = 'checked_out' AND expected_return < date('now')
            ''')
            overdue = cursor.fetchone()[0]
        finally:
            conn.close()

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            "EQUIPMENT STATUS REPORT",
            f"Generated: {now}",
            "=" * 60,
            f"Total Equipment Items: {total}",
            "",
            "AVAILABILITY BREAKDOWN:",
            "-" * 40,
        ]
        for row in status_rows:
            pct = (row[1] / total * 100) if total else 0
            lines.append(f"  {(row[0] or 'unknown'):<25} {row[1]:>4}  ({pct:.1f}%)")

        lines += [
            "",
            "CONDITION BREAKDOWN:",
            "-" * 40,
        ]
        for row in condition_rows:
            pct = (row[1] / total * 100) if total else 0
            lines.append(f"  {(row[0] or 'unknown'):<25} {row[1]:>4}  ({pct:.1f}%)")

        lines += [
            "",
            "CHECKOUT ACTIVITY:",
            "-" * 40,
            f"  Active checkouts:  {active_checkouts}",
            f"  Overdue returns:   {overdue}",
        ]
        return "\n".join(lines)

    def _generate_maintenance(self) -> str:
        """Maintenance report - items needing or scheduled for maintenance."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT equipment_id, equipment_name, condition_status,
                       availability_status, maintenance_due, location
                FROM union_equipment
                WHERE availability_status IN ('maintenance', 'maintenance_required')
                   OR condition_status IN ('poor', 'damaged')
                ORDER BY maintenance_due
            ''')
            needs_maint = cursor.fetchall()

            cursor.execute('''
                SELECT equipment_id, equipment_name, maintenance_due, condition_status
                FROM union_equipment
                WHERE maintenance_due IS NOT NULL AND maintenance_due > date('now')
                ORDER BY maintenance_due
            ''')
            scheduled = cursor.fetchall()

            cursor.execute('''
                SELECT COUNT(*) FROM union_equipment
                WHERE condition_status IN ('poor', 'damaged')
            ''')
            poor_count = cursor.fetchone()[0]
        finally:
            conn.close()

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            "EQUIPMENT MAINTENANCE REPORT",
            f"Generated: {now}",
            "=" * 80,
            f"Items needing maintenance: {len(needs_maint)}",
            f"Items with poor/damaged condition: {poor_count}",
            f"Scheduled future maintenance: {len(scheduled)}",
            "",
            "ITEMS CURRENTLY NEEDING MAINTENANCE:",
            "-" * 80,
            f"{'ID':<6} {'Name':<25} {'Condition':<12} {'Status':<20} {'Due':<12} {'Location':<15}",
            "-" * 80,
        ]
        if needs_maint:
            for r in needs_maint:
                lines.append(
                    f"{r[0]:<6} {(r[1] or '')[:24]:<25} {(r[2] or ''):<12} "
                    f"{(r[3] or ''):<20} {(r[4] or 'N/A'):<12} {(r[5] or ''):<15}"
                )
        else:
            lines.append("  No items currently need maintenance.")

        lines += [
            "",
            "UPCOMING SCHEDULED MAINTENANCE:",
            "-" * 60,
        ]
        if scheduled:
            for r in scheduled:
                lines.append(f"  ID {r[0]}: {r[1] or ''} - Due: {r[2]} (Condition: {r[3] or 'N/A'})")
        else:
            lines.append("  No upcoming maintenance scheduled.")

        return "\n".join(lines)

    def _generate_valuation(self) -> str:
        """Asset valuation report based on replacement_cost."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT category,
                       COUNT(*) as cnt,
                       SUM(COALESCE(replacement_cost, 0)) as total_value,
                       AVG(COALESCE(replacement_cost, 0)) as avg_value
                FROM union_equipment
                GROUP BY category
                ORDER BY total_value DESC
            ''')
            cat_rows = cursor.fetchall()

            cursor.execute('''
                SELECT COUNT(*), SUM(COALESCE(replacement_cost, 0))
                FROM union_equipment
            ''')
            totals = cursor.fetchone()

            cursor.execute('''
                SELECT equipment_id, equipment_name, category, replacement_cost
                FROM union_equipment
                WHERE replacement_cost IS NOT NULL
                ORDER BY replacement_cost DESC
                LIMIT 10
            ''')
            top_items = cursor.fetchall()
        finally:
            conn.close()

        total_count = totals[0] if totals else 0
        total_value = totals[1] if totals else 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [
            "ASSET VALUATION REPORT",
            f"Generated: {now}",
            "=" * 70,
            f"Total Equipment Items: {total_count}",
            f"Total Replacement Value: {total_value:,.2f}",
            "",
            "VALUE BY CATEGORY:",
            "-" * 70,
            f"{'Category':<25} {'Count':>6} {'Total Value':>15} {'Avg Value':>12}",
            "-" * 70,
        ]
        for r in cat_rows:
            cat = r[0] or 'Uncategorised'
            lines.append(f"  {cat[:24]:<25} {r[1]:>5}  {r[2]:>14,.2f}  {r[3]:>11,.2f}")

        lines += [
            "",
            "TOP 10 MOST VALUABLE ITEMS:",
            "-" * 60,
        ]
        for r in top_items:
            lines.append(f"  ID {r[0]}: {(r[1] or '')[:30]} ({r[2] or 'N/A'}) - Value: {r[3]:,.2f}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Save & email actions
    # ------------------------------------------------------------------

    def _save_as_txt(self):
        """Save the currently displayed report to a TXT file."""
        if not self.current_report_text:
            messagebox.showwarning("No Report",
                                   "Please generate a report first.",
                                   parent=self.dialog)
            return

        filepath = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Save Report As",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"equipment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if not filepath:
            return

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.current_report_text)
            messagebox.showinfo("Saved",
                                f"Report saved to:\n{filepath}",
                                parent=self.dialog)
        except Exception as e:
            logging.error("Failed to save report: %s", e)
            messagebox.showerror("Save Error",
                                 f"Failed to save report:\n{e}",
                                 parent=self.dialog)

    def _email_to_admin(self):
        """Email the current report to admin users."""
        if not self.current_report_text:
            messagebox.showwarning("No Report",
                                   "Please generate a report first.",
                                   parent=self.dialog)
            return

        # Look up admin email(s)
        admin_emails = []
        try:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                # Try multiple common table/column patterns for admin users
                for query in [
                    "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL AND email != '' LIMIT 5",
                    "SELECT email FROM user_accounts ua JOIN users u ON ua.user_id = u.id WHERE u.role = 'admin' AND u.email IS NOT NULL AND u.email != '' LIMIT 5",
                ]:
                    try:
                        cursor.execute(query)
                        rows = cursor.fetchall()
                        if rows:
                            admin_emails = [r[0] for r in rows]
                            break
                    except Exception:
                        continue
            finally:
                conn.close()
        except Exception as e:
            logging.warning("Could not look up admin email from DB: %s", e)

        # Fallback to system default
        if not admin_emails:
            try:
                from education_system.post_18.university_system.core.defaults import get_admin_email
                fallback = get_admin_email()
                if fallback:
                    admin_emails = [fallback]
            except ImportError:
                pass

        if not admin_emails:
            messagebox.showwarning("No Admin Email",
                                   "Could not find an admin email address.\n"
                                   "Please ensure admin accounts have email addresses configured.",
                                   parent=self.dialog)
            return

        subject = f"Equipment Report - {datetime.now().strftime('%Y-%m-%d')}"

        try:
            from education_system.post_18.university_system.infrastructure.email.email_service.core import send_email
            for email_addr in admin_emails:
                send_email(email_addr, subject, self.current_report_text)
            messagebox.showinfo("Email Sent",
                                f"Report emailed to: {', '.join(admin_emails)}",
                                parent=self.dialog)
        except Exception as e:
            logging.error("Failed to email report: %s", e)
            messagebox.showerror("Email Error",
                                 f"Failed to send email:\n{e}",
                                 parent=self.dialog)



def open_manage_equipment_system_dialog(self):
    """Open equipment management system hub"""
    dialog = ManageEquipmentSystemDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_add_new_equipment_dialog(self):
    """Open add new equipment (admin)"""
    dialog = AddNewEquipmentDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_update_equipment_status_dialog(self):
    """Open update equipment status (admin)"""
    dialog = UpdateEquipmentStatusDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_equipment_maintenance_tracking_dialog(self):
    """Open equipment maintenance tracking"""
    dialog = EquipmentMaintenanceTrackingDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_generate_equipment_reports_dialog(self):
    """Open generate equipment reports"""
    dialog = GenerateEquipmentReportsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
# ====================================================================
# END NEW FEATURE INTEGRATION METHODS
# ====================================================================


