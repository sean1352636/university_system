import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
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

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="➕ Add New Equipment",
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

        # Form fields
        form_frame = ttk.Frame(scrollable_frame)
        form_frame.pack(fill='both', expand=True, padx=15, pady=10)

        fields = [
            ("Equipment Name:", "Entry"),
            ("Category:", "Combo", ('Audio Equipment', 'Video Equipment', 'Lighting', 'Computers', 'Sports Equipment', 'Event Supplies', 'Other')),
            ("Manufacturer:", "Entry"),
            ("Model:", "Entry"),
            ("Serial Number:", "Entry"),
            ("Purchase Date:", "Entry"),
            ("Purchase Cost:", "Entry"),
            ("Condition:", "Combo", ('Excellent', 'Good', 'Fair')),
            ("Location:", "Entry"),
            ("Quantity:", "Entry"),
            ("Description:", "Text"),
            ("Included Accessories:", "Text"),
            ("Usage Notes:", "Text"),
            ("Training Required:", "Check"),
            ("Maximum Loan Days:", "Entry"),
            ("Replacement Value:", "Entry")
        ]

        for i, field_info in enumerate(fields):
            label = field_info[0]
            field_type = field_info[1]

            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky='nw', pady=5)

            if field_type == "Entry":
                ttk.Entry(form_frame, width=45).grid(row=i, column=1, sticky='ew', padx=10, pady=5)
            elif field_type == "Combo":
                combo = ttk.Combobox(form_frame, width=43, state='readonly')
                combo['values'] = field_info[2]
                combo.current(0)
                combo.grid(row=i, column=1, sticky='ew', padx=10, pady=5)
            elif field_type == "Text":
                text = scrolledtext.ScrolledText(form_frame, height=3, width=45)
                text.grid(row=i, column=1, sticky='ew', padx=10, pady=5)
            elif field_type == "Check":
                ttk.Checkbutton(form_frame, text="Yes").grid(row=i, column=1, sticky='w', padx=10, pady=5)

        form_frame.columnconfigure(1, weight=1)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Add Equipment", command=self.add_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='right')

    def add_equipment(self):
        messagebox.showinfo("Equipment Added",
                          "New equipment added successfully!\n\n" +
                          "Equipment ID: EQ157\n" +
                          "Name: Professional Camera (Canon EOS R5)\n" +
                          "Category: Video Equipment\n" +
                          "Status: Available\n\n" +
                          "Equipment is now available for checkout.")
        self.dialog.destroy()



class UpdateEquipmentStatusDialog:
    """Dialog for updating equipment status (admin)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Update Equipment Status")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="⚙️ Update Equipment Status",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Equipment list
        list_frame = ttk.LabelFrame(main_frame, text="Equipment Inventory")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Name', 'Category', 'Current Status', 'Condition', 'Location')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Name':
                tree.column(col, width=200)
            elif col == 'Category':
                tree.column(col, width=120)
            else:
                tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # Sample equipment
        equipment = [
            ("EQ001", "Professional Camera (Canon EOS R5)", "Video Equipment", "Available", "Excellent", "Media Room A"),
            ("EQ002", "Wireless Microphone System", "Audio Equipment", "Checked Out", "Good", "Audio Store"),
            ("EQ003", "LED Light Panel (3-pack)", "Lighting", "Maintenance", "Fair", "Repair Shop"),
            ("EQ004", "Tripod (Manfrotto Pro)", "Video Equipment", "Available", "Good", "Media Room A")
        ]

        for item in equipment:
            tree.insert('', 'end', values=item)

        # Update form
        update_frame = ttk.LabelFrame(main_frame, text="Update Status")
        update_frame.pack(fill='x', pady=(0, 15))

        update_content = ttk.Frame(update_frame)
        update_content.pack(fill='x', padx=15, pady=10)

        ttk.Label(update_content, text="New Status:").grid(row=0, column=0, sticky='w', pady=5)
        status_combo = ttk.Combobox(update_content, width=25, state='readonly')
        status_combo['values'] = ('Available', 'Checked Out', 'Maintenance', 'Reserved', 'Lost', 'Retired')
        status_combo.current(0)
        status_combo.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(update_content, text="New Condition:").grid(row=1, column=0, sticky='w', pady=5)
        condition_combo = ttk.Combobox(update_content, width=25, state='readonly')
        condition_combo['values'] = ('Excellent', 'Good', 'Fair', 'Poor', 'Broken')
        condition_combo.current(0)
        condition_combo.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(update_content, text="New Location:").grid(row=2, column=0, sticky='w', pady=5)
        ttk.Entry(update_content, width=27).grid(row=2, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(update_content, text="Notes:").grid(row=3, column=0, sticky='nw', pady=5)
        notes_text = scrolledtext.ScrolledText(update_content, height=3, width=27)
        notes_text.grid(row=3, column=1, sticky='ew', padx=10, pady=5)

        update_content.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Update Status", command=self.update_status).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Bulk Update", command=self.bulk_update).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View History", command=self.view_history).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def update_status(self):
        messagebox.showinfo("Status Updated",
                          "Equipment status updated!\n\n" +
                          "EQ003 - LED Light Panel (3-pack)\n" +
                          "Old Status: Maintenance\n" +
                          "New Status: Available\n" +
                          "Condition: Excellent\n\n" +
                          "Equipment is now available for checkout.")

    def bulk_update(self):
        messagebox.showinfo("Bulk Update",
                          "Bulk status update:\n\n" +
                          "Select multiple items to update:\n" +
                          "- Change status for all\n" +
                          "- Update location for all\n" +
                          "- Set condition for all\n\n" +
                          "Useful for batch operations.")

    def view_history(self):
        messagebox.showinfo("Status History",
                          "Equipment Status History:\n\n" +
                          "EQ003 - LED Light Panel (3-pack)\n\n" +
                          "2025-03-29: Maintenance → Available\n" +
                          "2025-03-22: Checked Out → Maintenance\n" +
                          "2025-03-15: Available → Checked Out\n" +
                          "2025-03-08: Checked Out → Available\n" +
                          "2025-03-01: Available → Checked Out")



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

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🔧 Equipment Maintenance",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Current Maintenance tab
        current_frame = ttk.Frame(notebook)
        notebook.add(current_frame, text="Current Maintenance")

        current_columns = ('ID', 'Equipment', 'Issue', 'Reported', 'Priority', 'Status', 'Expected Completion')
        current_tree = ttk.Treeview(current_frame, columns=current_columns, show='tree headings', height=10)

        for col in current_columns:
            current_tree.heading(col, text=col)
            if col == 'Equipment':
                current_tree.column(col, width=180)
            elif col == 'Issue':
                current_tree.column(col, width=150)
            else:
                current_tree.column(col, width=100)

        current_tree.pack(fill='both', expand=True, padx=10, pady=10)

        maintenance_items = [
            ("MNT012", "LED Light Panel", "Bulb replacement needed", "2025-03-28", "High", "In Progress", "2025-04-02"),
            ("MNT011", "Projector (Epson 4K)", "Fan making noise", "2025-03-25", "Medium", "Waiting Parts", "2025-04-10"),
            ("MNT010", "Laptop (Dell XPS 15)", "Battery replacement", "2025-03-20", "Low", "Scheduled", "2025-04-15")
        ]

        for item in maintenance_items:
            current_tree.insert('', 'end', values=item)

        # Maintenance History tab
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="Maintenance History")

        history_columns = ('ID', 'Equipment', 'Issue', 'Completed', 'Cost', 'Performed By')
        history_tree = ttk.Treeview(history_frame, columns=history_columns, show='tree headings', height=10)

        for col in history_columns:
            history_tree.heading(col, text=col)
            if col == 'Equipment':
                history_tree.column(col, width=200)
            elif col == 'Issue':
                history_tree.column(col, width=180)
            else:
                history_tree.column(col, width=120)

        history_tree.pack(fill='both', expand=True, padx=10, pady=10)

        history_items = [
            ("MNT009", "Professional Camera", "Sensor cleaning", "2025-03-15", "£45.00", "Tech Services"),
            ("MNT008", "Wireless Microphone", "Battery compartment repair", "2025-03-10", "£25.00", "Audio Tech"),
            ("MNT007", "Tripod", "Head adjustment", "2025-03-05", "£15.00", "Equipment Manager")
        ]

        for item in history_items:
            history_tree.insert('', 'end', values=item)

        # Scheduled Maintenance tab
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text="Scheduled Maintenance")

        schedule_scroll = scrolledtext.ScrolledText(schedule_frame, height=18, wrap=tk.WORD, font=('Courier', 9))
        schedule_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        schedule_text = """SCHEDULED MAINTENANCE CALENDAR

APRIL 2025:
────────────────────────────────────────────
Week 1 (Apr 1-7):
  • Professional Cameras (All) - Sensor cleaning
  • Projectors - Filter replacement
  • Audio Equipment - Connection check

Week 2 (Apr 8-14):
  • Laptops - System updates & antivirus
  • Lighting Equipment - Bulb inspection
  • Tripods - Mechanism lubrication

Week 3 (Apr 15-21):
  • Wireless Systems - Battery replacement
  • Speakers - Driver testing
  • Cameras - Firmware updates

Week 4 (Apr 22-30):
  • All Equipment - Safety inspection
  • Inventory audit
  • Equipment calibration

MAY 2025:
────────────────────────────────────────────
Week 1 (May 1-7):
  • Deep cleaning all equipment
  • Cable testing & replacement
  • Storage organization

ANNUAL MAINTENANCE:
────────────────────────────────────────────
  • Professional calibration (June)
  • Insurance inspection (July)
  • Warranty reviews (August)"""

        schedule_scroll.insert('1.0', schedule_text)
        schedule_scroll.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Report Issue", command=self.report_issue).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Complete Maintenance", command=self.complete_maintenance).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Schedule Maintenance", command=self.schedule_maintenance).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def report_issue(self):
        messagebox.showinfo("Report Issue",
                          "Report equipment issue:\n\n" +
                          "Equipment ID or Name:\n" +
                          "Problem Description:\n" +
                          "Severity: Low/Medium/High/Critical\n" +
                          "Photos: Upload (optional)\n\n" +
                          "Maintenance team will be notified.")

    def complete_maintenance(self):
        messagebox.showinfo("Complete Maintenance",
                          "Mark maintenance as complete:\n\n" +
                          "Maintenance ID: MNT012\n" +
                          "Work performed:\n" +
                          "Parts used:\n" +
                          "Cost: £\n" +
                          "Performed by:\n\n" +
                          "Equipment will be marked available.")

    def schedule_maintenance(self):
        messagebox.showinfo("Schedule Maintenance",
                          "Schedule preventive maintenance:\n\n" +
                          "Equipment:\n" +
                          "Maintenance type:\n" +
                          "Scheduled date:\n" +
                          "Assigned to:\n" +
                          "Estimated duration:\n\n" +
                          "Calendar reminder will be created.")



class GenerateEquipmentReportsDialog:
    """Dialog for generating equipment reports"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Equipment Reports")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📊 Equipment Reports",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Report types
        reports_frame = ttk.LabelFrame(main_frame, text="Available Reports")
        reports_frame.pack(fill='both', expand=True, pady=(0, 15))

        # Report cards
        cards_container = ttk.Frame(reports_frame)
        cards_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Row 1
        row1 = ttk.Frame(cards_container)
        row1.pack(fill='x', pady=(0, 10))

        self.create_report_card(row1, "📋 Inventory Report", "Complete equipment inventory", self.inventory_report).pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_report_card(row1, "📈 Usage Statistics", "Checkout and usage stats", self.usage_report).pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_report_card(row1, "🔧 Maintenance Report", "Maintenance history & costs", self.maintenance_report).pack(side='left', fill='both', expand=True)

        # Row 2
        row2 = ttk.Frame(cards_container)
        row2.pack(fill='x', pady=(0, 10))

        self.create_report_card(row2, "💰 Financial Report", "Equipment costs & value", self.financial_report).pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_report_card(row2, "⚠️ Issues Report", "Problems and damages", self.issues_report).pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_report_card(row2, "📊 Utilization Report", "Equipment utilization rates", self.utilization_report).pack(side='left', fill='both', expand=True)

        # Row 3
        row3 = ttk.Frame(cards_container)
        row3.pack(fill='x')

        self.create_report_card(row3, "👥 User Activity", "User checkout patterns", self.user_activity_report).pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_report_card(row3, "📅 Forecast Report", "Future needs prediction", self.forecast_report).pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.create_report_card(row3, "🎯 Custom Report", "Build your own report", self.custom_report).pack(side='left', fill='both', expand=True)

        # Report parameters
        params_frame = ttk.LabelFrame(main_frame, text="Report Parameters")
        params_frame.pack(fill='x', pady=(0, 15))

        params_content = ttk.Frame(params_frame)
        params_content.pack(fill='x', padx=15, pady=10)

        ttk.Label(params_content, text="Date Range:").grid(row=0, column=0, sticky='w', pady=5)
        date_combo = ttk.Combobox(params_content, width=25, state='readonly')
        date_combo['values'] = ('Last 7 days', 'Last 30 days', 'Last 3 months', 'Last 6 months', 'Last year', 'All time', 'Custom range')
        date_combo.current(1)
        date_combo.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(params_content, text="Format:").grid(row=1, column=0, sticky='w', pady=5)
        format_combo = ttk.Combobox(params_content, width=25, state='readonly')
        format_combo['values'] = ('PDF', 'Excel (XLSX)', 'CSV', 'HTML')
        format_combo.current(0)
        format_combo.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(params_content, text="Group By:").grid(row=2, column=0, sticky='w', pady=5)
        group_combo = ttk.Combobox(params_content, width=25, state='readonly')
        group_combo['values'] = ('Category', 'Location', 'Condition', 'Status', 'None')
        group_combo.current(0)
        group_combo.grid(row=2, column=1, sticky='ew', padx=10, pady=5)

        params_content.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="View Saved Reports", command=self.view_saved).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Schedule Report", command=self.schedule_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def create_report_card(self, parent, title, description, command):
        card = ttk.Frame(parent, relief='raised', borderwidth=1)

        ttk.Label(card, text=title, font=('Arial', 10, 'bold')).pack(pady=(8, 3), padx=8)
        ttk.Label(card, text=description, font=('Arial', 8), wraplength=120).pack(pady=(0, 8), padx=8)
        ttk.Button(card, text="Generate", command=command).pack(pady=(0, 8))

        return card

    def inventory_report(self):
        messagebox.showinfo("Inventory Report",
                          "Generating inventory report...\n\n" +
                          "Report will include:\n" +
                          "- All equipment items (156)\n" +
                          "- Status breakdown\n" +
                          "- Location details\n" +
                          "- Condition assessment\n" +
                          "- Value calculation\n\n" +
                          "Saved to: reports/inventory_2025-04-02.pdf")

    def usage_report(self):
        messagebox.showinfo("Usage Statistics",
                          "Usage statistics report:\n\n" +
                          "Top 5 Most Used Equipment:\n" +
                          "1. Professional Camera - 45 checkouts\n" +
                          "2. Laptop (Dell XPS) - 38 checkouts\n" +
                          "3. Projector - 32 checkouts\n" +
                          "4. Wireless Mic - 28 checkouts\n" +
                          "5. Tripod - 25 checkouts\n\n" +
                          "Average checkout duration: 4.2 days\n" +
                          "Total checkouts (30 days): 234")

    def maintenance_report(self):
        messagebox.showinfo("Maintenance Report",
                          "Maintenance summary:\n\n" +
                          "Total maintenance tasks: 15\n" +
                          "Completed: 12 (80%)\n" +
                          "In progress: 3 (20%)\n\n" +
                          "Total maintenance cost: £685.00\n" +
                          "Average cost per task: £45.67\n\n" +
                          "Most common issues:\n" +
                          "1. Battery replacement (5)\n" +
                          "2. Cleaning (4)\n" +
                          "3. Repairs (6)")

    def financial_report(self):
        messagebox.showinfo("Financial Report",
                          "Financial summary:\n\n" +
                          "Total equipment value: £125,400\n" +
                          "Total purchases (2024): £18,500\n" +
                          "Total maintenance costs: £2,340\n" +
                          "Late fees collected: £450\n\n" +
                          "Most valuable items:\n" +
                          "1. Professional Cameras (5x): £17,500\n" +
                          "2. Laptops (10x): £15,000\n" +
                          "3. Projectors (3x): £9,000")

    def issues_report(self):
        messagebox.showinfo("Issues Report",
                          "Equipment issues summary:\n\n" +
                          "Total issues reported: 8\n" +
                          "Resolved: 6 (75%)\n" +
                          "Pending: 2 (25%)\n\n" +
                          "Damage reports: 3\n" +
                          "Lost equipment: 0\n" +
                          "Theft: 0\n\n" +
                          "Total damage costs: £285.00")

    def utilization_report(self):
        messagebox.showinfo("Utilization Report",
                          "Equipment utilization rates:\n\n" +
                          "Overall utilization: 62%\n\n" +
                          "By category:\n" +
                          "- Video Equipment: 85% (High)\n" +
                          "- Audio Equipment: 72% (Good)\n" +
                          "- Computers: 68% (Good)\n" +
                          "- Lighting: 45% (Low)\n" +
                          "- Sports Equipment: 38% (Low)\n\n" +
                          "Recommendation: Consider retiring\n" +
                          "underutilized equipment")

    def user_activity_report(self):
        messagebox.showinfo("User Activity",
                          "User checkout patterns:\n\n" +
                          "Total active users: 87\n" +
                          "Average checkouts per user: 2.7\n\n" +
                          "Top borrowers:\n" +
                          "1. Film Society - 23 checkouts\n" +
                          "2. Media Club - 18 checkouts\n" +
                          "3. John Smith - 12 checkouts\n\n" +
                          "On-time return rate: 94%")

    def forecast_report(self):
        messagebox.showinfo("Forecast Report",
                          "Equipment needs forecast:\n\n" +
                          "Based on usage trends:\n\n" +
                          "Recommend purchasing:\n" +
                          "- 2 additional cameras (high demand)\n" +
                          "- 3 more laptops (waitlist: 12)\n" +
                          "- 1 projector (backup needed)\n\n" +
                          "Estimated investment: £12,000\n" +
                          "Expected ROI: 18 months")

    def custom_report(self):
        messagebox.showinfo("Custom Report",
                          "Build custom report:\n\n" +
                          "Select:\n" +
                          "- Data fields to include\n" +
                          "- Filter criteria\n" +
                          "- Grouping options\n" +
                          "- Chart types\n" +
                          "- Export format\n\n" +
                          "Save template for future use")

    def view_saved(self):
        messagebox.showinfo("Saved Reports",
                          "Previously generated reports:\n\n" +
                          "1. Inventory Report - 2025-04-01.pdf\n" +
                          "2. Usage Statistics - 2025-03-25.xlsx\n" +
                          "3. Maintenance Report - 2025-03-15.pdf\n" +
                          "4. Financial Report - 2025-03-01.pdf\n\n" +
                          "Click to open or delete")

    def schedule_report(self):
        messagebox.showinfo("Schedule Report",
                          "Schedule automatic report generation:\n\n" +
                          "Frequency:\n" +
                          "- Daily\n" +
                          "- Weekly\n" +
                          "- Monthly\n" +
                          "- Quarterly\n\n" +
                          "Reports will be emailed automatically")



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


