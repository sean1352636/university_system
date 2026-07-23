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
    # comprehensive schema when running stand-alone.
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
    from education_system.post_18.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


logger = logging.getLogger(__name__)


def _ensure_green_tables():
    """Create green-initiative tables if they do not yet exist."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS green_initiatives (
                initiative_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                status TEXT DEFAULT 'active',
                created_by TEXT,
                created_date TEXT,
                target_date TEXT,
                carbon_target REAL,
                notes TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS carbon_tracking (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                transport_carbon REAL DEFAULT 0,
                energy_carbon REAL DEFAULT 0,
                catering_carbon REAL DEFAULT 0,
                total_carbon REAL DEFAULT 0,
                attendees INTEGER DEFAULT 0,
                carbon_per_person REAL DEFAULT 0,
                sustainability_score REAL DEFAULT 0,
                notes TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS waste_reduction_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                waste_generated REAL DEFAULT 0,
                waste_recycled REAL DEFAULT 0,
                waste_composted REAL DEFAULT 0,
                waste_landfill REAL DEFAULT 0,
                recycling_rate REAL DEFAULT 0,
                notes TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS green_transport_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                transport_method TEXT,
                distance_km REAL DEFAULT 0,
                carbon_saved REAL DEFAULT 0,
                trip_date TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS eco_suppliers (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                certifications TEXT,
                description TEXT,
                contact_email TEXT,
                rating REAL DEFAULT 0,
                added_by TEXT,
                added_date TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS green_certifications (
                cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_name TEXT,
                entity_type TEXT,
                certification_level TEXT,
                score REAL DEFAULT 0,
                awarded_date TEXT,
                expires_date TEXT,
                notes TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS carbon_offsets (
                offset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_name TEXT NOT NULL,
                description TEXT,
                offset_kg REAL DEFAULT 0,
                cost REAL DEFAULT 0,
                status TEXT DEFAULT 'pending',
                purchased_by TEXT,
                purchase_date TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error creating green tables: {e}")


def _get_current_user_id(auth):
    """Extract the current user identifier from the auth manager."""
    try:
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            return auth.current_user.get('id') or auth.current_user.get('user_id') or 'unknown'
    except Exception:
        pass
    return 'unknown'


class GreenInitiativesDialog:
    """Main dialog for green initiatives and sustainability"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Green Initiatives")
        self.dialog.geometry("1000x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_initiatives()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Green Initiatives & Sustainability",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Top button bar for sub-dialogs
        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack(fill='x', pady=(0, 10))

        buttons = [
            ("Carbon Tracking", self.carbon_tracking),
            ("Waste Reduction", self.waste_reduction),
            ("Green Transport", self.green_transport),
            ("Env. Reports", self.environmental_reports),
            ("Eco Suppliers", self.eco_suppliers),
            ("Certifications", self.green_certifications),
            ("Offset Programs", self.offset_programs),
        ]
        for text, cmd in buttons:
            ttk.Button(nav_frame, text=text, command=cmd).pack(side='left', padx=3)

        # -- New initiative form --
        form_frame = ttk.LabelFrame(main_frame, text="Create New Initiative")
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(row1, text="Title:").pack(side='left')
        self.title_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.title_var, width=40).pack(side='left', padx=5)

        ttk.Label(row1, text="Category:").pack(side='left', padx=(10, 0))
        self.category_var = tk.StringVar()
        cat_combo = ttk.Combobox(row1, textvariable=self.category_var, width=20,
                                  values=["Carbon Reduction", "Waste Management",
                                          "Transport", "Energy", "Biodiversity", "Other"])
        cat_combo.pack(side='left', padx=5)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(row2, text="Description:").pack(side='left')
        self.desc_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.desc_var, width=70).pack(side='left', padx=5, fill='x', expand=True)

        row3 = ttk.Frame(form_frame)
        row3.pack(fill='x', padx=10, pady=5)
        ttk.Label(row3, text="Target Date (YYYY-MM-DD):").pack(side='left')
        self.target_date_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self.target_date_var, width=15).pack(side='left', padx=5)

        ttk.Label(row3, text="Carbon Target (kg CO2):").pack(side='left', padx=(10, 0))
        self.carbon_target_var = tk.StringVar(value="0")
        ttk.Entry(row3, textvariable=self.carbon_target_var, width=10).pack(side='left', padx=5)

        ttk.Button(row3, text="Save Initiative", command=self.save_initiative).pack(side='right', padx=5)

        # -- Initiatives list --
        list_frame = ttk.LabelFrame(main_frame, text="Current Initiatives")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Title', 'Category', 'Status', 'Target Date', 'Carbon Target', 'Created')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.tree.heading(col, text=col)
        self.tree.column('ID', width=40)
        self.tree.column('Title', width=200)
        self.tree.column('Category', width=130)
        self.tree.column('Status', width=80)
        self.tree.column('Target Date', width=100)
        self.tree.column('Carbon Target', width=100)
        self.tree.column('Created', width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y', pady=5)

        # Bottom buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text="Refresh", command=self.load_initiatives).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete Selected", command=self.delete_initiative).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side='right', padx=5)

    def load_initiatives(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT initiative_id, title, category, status, target_date,
                       carbon_target, created_date
                FROM green_initiatives ORDER BY created_date DESC
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['initiative_id'], r['title'], r['category'] or '',
                    r['status'], r['target_date'] or '', r['carbon_target'] or 0,
                    r['created_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading initiatives: {e}")

    def save_initiative(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Validation", "Please enter a title.")
            return
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO green_initiatives
                    (title, description, category, status, created_by, created_date,
                     target_date, carbon_target)
                VALUES (?, ?, ?, 'active', ?, ?, ?, ?)
            ''', (
                title,
                self.desc_var.get().strip(),
                self.category_var.get().strip() or 'Other',
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                self.target_date_var.get().strip() or None,
                float(self.carbon_target_var.get() or 0),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", f"Initiative '{title}' created.")
            self.title_var.set('')
            self.desc_var.set('')
            self.category_var.set('')
            self.target_date_var.set('')
            self.carbon_target_var.set('0')
            self.load_initiatives()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save initiative: {e}")

    def delete_initiative(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection", "Please select an initiative to delete.")
            return
        vals = self.tree.item(selected[0], 'values')
        if not messagebox.askyesno("Confirm", f"Delete initiative '{vals[1]}'?"):
            return
        try:
            conn = get_connection()
            conn.execute('DELETE FROM green_initiatives WHERE initiative_id = ?', (vals[0],))
            conn.commit()
            conn.close()
            self.load_initiatives()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {e}")

    # --- Sub-dialog launchers ---

    def carbon_tracking(self):
        dialog = CarbonTrackingDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def sustainable_events(self):
        dialog = SustainableEventsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def waste_reduction(self):
        dialog = WasteReductionDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def green_transport(self):
        dialog = GreenTransportDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def environmental_reports(self):
        dialog = EnvironmentalReportsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def eco_suppliers(self):
        dialog = EcoSuppliersDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def green_certifications(self):
        dialog = GreenCertificationsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def offset_programs(self):
        dialog = OffsetProgramsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)


class CarbonTrackingDialog:
    """Dialog for tracking carbon footprint"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Carbon Footprint Tracking")
        self.dialog.geometry("950x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_history()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Carbon Footprint Calculator",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Event name
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(name_frame, text="Event / Activity Name:").pack(side='left')
        self.event_name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=self.event_name_var, width=50).pack(side='left', padx=5)

        # Calculator notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='x', pady=(0, 10))

        # Transportation tab
        transport_frame = ttk.Frame(notebook)
        notebook.add(transport_frame, text="Transportation")
        self.create_transport_tab(transport_frame)

        # Energy tab
        energy_frame = ttk.Frame(notebook)
        notebook.add(energy_frame, text="Energy")
        self.create_energy_tab(energy_frame)

        # Catering tab
        catering_frame = ttk.Frame(notebook)
        notebook.add(catering_frame, text="Catering")
        self.create_catering_tab(catering_frame)

        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Carbon Footprint Results")
        results_frame.pack(fill='x', pady=(0, 10))

        self.results_label = ttk.Label(results_frame, text="Total Carbon Footprint: 0.00 kg CO2",
                                      font=('Arial', 12, 'bold'))
        self.results_label.pack(padx=10, pady=5)

        self.detail_label = ttk.Label(results_frame,
                                       text="Transport: 0.00 | Energy: 0.00 | Catering: 0.00")
        self.detail_label.pack(padx=10, pady=(0, 5))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(button_frame, text="Calculate", command=self.calculate_footprint).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Save to Database", command=self.save_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

        # History
        hist_frame = ttk.LabelFrame(main_frame, text="Saved Carbon Records")
        hist_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Event', 'Transport', 'Energy', 'Catering', 'Total', 'Per Person', 'Score', 'Date')
        self.history_tree = ttk.Treeview(hist_frame, columns=columns, show='headings', height=6)
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=90)
        self.history_tree.column('Event', width=150)
        self.history_tree.pack(fill='both', expand=True, padx=5, pady=5)

    def create_transport_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Attendee Transportation").pack(anchor='w', pady=(0, 10))

        self.transport_vars = {}
        methods = [("Walking/Cycling", 0), ("Public Transport", 0.05), ("Car", 0.21), ("Taxi/Uber", 0.25)]

        for method, rate in methods:
            row = ttk.Frame(frame)
            row.pack(fill='x', pady=5)

            ttk.Label(row, text=f"{method}:", width=20).pack(side='left')

            count_var = tk.StringVar(value="0")
            ttk.Entry(row, textvariable=count_var, width=10).pack(side='left', padx=5)
            ttk.Label(row, text="attendees").pack(side='left')

            self.transport_vars[method] = (count_var, rate)

    def create_energy_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Energy Consumption").pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text="Event Duration (hours):").pack(anchor='w')
        self.duration_var = tk.StringVar(value="2")
        ttk.Entry(frame, textvariable=self.duration_var, width=10).pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text="Number of Attendees:").pack(anchor='w')
        self.attendees_var = tk.StringVar(value="50")
        ttk.Entry(frame, textvariable=self.attendees_var, width=10).pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text="Estimated: 0.5 kWh per person per hour\nCarbon: 0.233 kg CO2 per kWh (UK average)",
                 foreground='gray').pack(anchor='w')

    def create_catering_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text="Catering Impact").pack(anchor='w', pady=(0, 10))

        self.catering_vars = {}
        options = [("Vegan", 1.5), ("Vegetarian", 2.5), ("Meat-based", 5.0)]

        for option, rate in options:
            row = ttk.Frame(frame)
            row.pack(fill='x', pady=5)

            ttk.Label(row, text=f"{option} meals:", width=20).pack(side='left')

            count_var = tk.StringVar(value="0")
            ttk.Entry(row, textvariable=count_var, width=10).pack(side='left', padx=5)
            ttk.Label(row, text=f"({rate} kg CO2 each)").pack(side='left')

            self.catering_vars[option] = (count_var, rate)

    def calculate_footprint(self):
        """Calculate and display the carbon footprint breakdown."""
        self._transport_total = 0.0
        self._energy_total = 0.0
        self._catering_total = 0.0

        try:
            for method, (count_var, rate) in self.transport_vars.items():
                count = float(count_var.get() or 0)
                self._transport_total += count * rate * 10  # 10 km average

            duration = float(self.duration_var.get() or 0)
            attendees = float(self.attendees_var.get() or 0)
            self._energy_total = duration * attendees * 0.5 * 0.233

            for option, (count_var, rate) in self.catering_vars.items():
                count = float(count_var.get() or 0)
                self._catering_total += count * rate

            total = self._transport_total + self._energy_total + self._catering_total
            self._last_total = total
            self._last_attendees = int(attendees) if attendees else 0

            self.results_label.config(text=f"Total Carbon Footprint: {total:.2f} kg CO2")
            self.detail_label.config(
                text=f"Transport: {self._transport_total:.2f} | "
                     f"Energy: {self._energy_total:.2f} | "
                     f"Catering: {self._catering_total:.2f}")

            if total > 100:
                messagebox.showinfo("Recommendations",
                                   "High carbon footprint! Consider:\n\n"
                                   "- Encourage public transport\n"
                                   "- Serve more plant-based food\n"
                                   "- Use renewable energy\n"
                                   "- Reduce event duration")
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers.")

    def save_report(self):
        """Save the carbon tracking record to the database."""
        event_name = self.event_name_var.get().strip()
        if not event_name:
            messagebox.showwarning("Validation", "Please enter an event name.")
            return

        if not hasattr(self, '_last_total'):
            messagebox.showwarning("Calculate First", "Please click Calculate before saving.")
            return

        total = self._last_total
        attendees = self._last_attendees
        per_person = total / attendees if attendees > 0 else 0
        score = max(0, 100 - (per_person * 10))

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO carbon_tracking
                    (event_name, transport_carbon, energy_carbon, catering_carbon,
                     total_carbon, attendees, carbon_per_person, sustainability_score,
                     recorded_by, recorded_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event_name,
                self._transport_total,
                self._energy_total,
                self._catering_total,
                total,
                attendees,
                per_person,
                score,
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", f"Carbon record saved for '{event_name}'.\n"
                                f"Sustainability score: {score:.1f}/100")
            self.load_history()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def load_history(self):
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT record_id, event_name, transport_carbon, energy_carbon,
                       catering_carbon, total_carbon, carbon_per_person,
                       sustainability_score, recorded_date
                FROM carbon_tracking ORDER BY recorded_date DESC LIMIT 50
            ''')
            for r in cursor.fetchall():
                self.history_tree.insert('', 'end', values=(
                    r['record_id'], r['event_name'],
                    f"{r['transport_carbon']:.1f}", f"{r['energy_carbon']:.1f}",
                    f"{r['catering_carbon']:.1f}", f"{r['total_carbon']:.1f}",
                    f"{r['carbon_per_person']:.2f}", f"{r['sustainability_score']:.0f}",
                    r['recorded_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading carbon history: {e}")


class WasteReductionDialog:
    """Dialog for waste reduction tracking"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Waste Reduction Tracking")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.refresh_stats()
        self.load_log()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Waste Reduction & Recycling",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Stats
        self.stats_frame = ttk.LabelFrame(main_frame, text="Waste Statistics (from database)")
        self.stats_frame.pack(fill='x', pady=(0, 10))
        self.stats_label = ttk.Label(self.stats_frame, text="Loading...",
                                      justify='left', font=('Courier', 10))
        self.stats_label.pack(padx=15, pady=10)

        # Log new entry form
        form_frame = ttk.LabelFrame(main_frame, text="Log Waste Data")
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(row1, text="Event Name:").pack(side='left')
        self.event_name_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.event_name_var, width=40).pack(side='left', padx=5)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill='x', padx=10, pady=5)

        ttk.Label(row2, text="Waste Generated (kg):").pack(side='left')
        self.waste_gen_var = tk.StringVar(value="0")
        ttk.Entry(row2, textvariable=self.waste_gen_var, width=10).pack(side='left', padx=5)

        ttk.Label(row2, text="Recycled (kg):").pack(side='left', padx=(10, 0))
        self.waste_rec_var = tk.StringVar(value="0")
        ttk.Entry(row2, textvariable=self.waste_rec_var, width=10).pack(side='left', padx=5)

        ttk.Label(row2, text="Composted (kg):").pack(side='left', padx=(10, 0))
        self.waste_comp_var = tk.StringVar(value="0")
        ttk.Entry(row2, textvariable=self.waste_comp_var, width=10).pack(side='left', padx=5)

        row3 = ttk.Frame(form_frame)
        row3.pack(fill='x', padx=10, pady=5)
        ttk.Label(row3, text="Notes:").pack(side='left')
        self.notes_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self.notes_var, width=60).pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(row3, text="Save Entry", command=self.save_entry).pack(side='right', padx=5)

        # History treeview
        hist_frame = ttk.LabelFrame(main_frame, text="Waste Log History")
        hist_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Event', 'Generated', 'Recycled', 'Composted', 'Landfill', 'Rate %', 'Date')
        self.tree = ttk.Treeview(hist_frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=90)
        self.tree.column('Event', width=160)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Bottom buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_all).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side='right', padx=5)

    def _refresh_all(self):
        self.refresh_stats()
        self.load_log()

    def refresh_stats(self):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    COUNT(*) as entries,
                    COALESCE(SUM(waste_generated), 0) as total_gen,
                    COALESCE(SUM(waste_recycled), 0) as total_rec,
                    COALESCE(SUM(waste_composted), 0) as total_comp,
                    COALESCE(SUM(waste_landfill), 0) as total_land
                FROM waste_reduction_log
            ''')
            row = cursor.fetchone()
            conn.close()

            entries = row['entries']
            total_gen = row['total_gen']
            total_rec = row['total_rec']
            total_comp = row['total_comp']
            total_land = row['total_land']
            rate = (total_rec / total_gen * 100) if total_gen > 0 else 0
            diversion = ((total_rec + total_comp) / total_gen * 100) if total_gen > 0 else 0

            stats_text = (
                f"Events Logged: {entries}\n"
                f"Total Waste Generated: {total_gen:.1f} kg\n"
                f"Recycled: {total_rec:.1f} kg ({rate:.1f}%)\n"
                f"Composted: {total_comp:.1f} kg\n"
                f"Landfill: {total_land:.1f} kg\n"
                f"Landfill Diversion Rate: {diversion:.1f}%\n"
                f"Target: 80% diversion from landfill"
            )
            self.stats_label.config(text=stats_text)
        except Exception as e:
            self.stats_label.config(text=f"Error loading stats: {e}")

    def load_log(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT log_id, event_name, waste_generated, waste_recycled,
                       waste_composted, waste_landfill, recycling_rate, recorded_date
                FROM waste_reduction_log ORDER BY recorded_date DESC LIMIT 50
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['log_id'], r['event_name'] or '',
                    f"{r['waste_generated']:.1f}", f"{r['waste_recycled']:.1f}",
                    f"{r['waste_composted']:.1f}", f"{r['waste_landfill']:.1f}",
                    f"{r['recycling_rate']:.1f}", r['recorded_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading waste log: {e}")

    def save_entry(self):
        event_name = self.event_name_var.get().strip()
        if not event_name:
            messagebox.showwarning("Validation", "Please enter an event name.")
            return
        try:
            generated = float(self.waste_gen_var.get() or 0)
            recycled = float(self.waste_rec_var.get() or 0)
            composted = float(self.waste_comp_var.get() or 0)
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for waste amounts.")
            return

        if recycled + composted > generated:
            messagebox.showerror("Error", "Recycled + composted cannot exceed total waste generated.")
            return

        landfill = generated - recycled - composted
        rate = (recycled / generated * 100) if generated > 0 else 0

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO waste_reduction_log
                    (event_name, waste_generated, waste_recycled, waste_composted,
                     waste_landfill, recycling_rate, notes, recorded_by, recorded_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event_name, generated, recycled, composted, landfill, rate,
                self.notes_var.get().strip(),
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success",
                                f"Waste data saved for '{event_name}'.\n"
                                f"Recycling rate: {rate:.1f}%")
            self.event_name_var.set('')
            self.waste_gen_var.set('0')
            self.waste_rec_var.set('0')
            self.waste_comp_var.set('0')
            self.notes_var.set('')
            self._refresh_all()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")


class GreenTransportDialog:
    """Dialog for green transport tracking"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Green Transport")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.refresh_stats()
        self.load_log()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Green Transport Tracker",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Log trip form
        form_frame = ttk.LabelFrame(main_frame, text="Log a Green Trip")
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)

        ttk.Label(row1, text="Transport Method:").pack(side='left')
        self.method_var = tk.StringVar()
        method_combo = ttk.Combobox(row1, textvariable=self.method_var, width=20,
                                     values=["Walking", "Cycling", "Public Transport",
                                             "Carpooling", "Electric Vehicle"],
                                     state='readonly')
        method_combo.pack(side='left', padx=5)
        method_combo.current(0)

        ttk.Label(row1, text="Distance (km):").pack(side='left', padx=(15, 0))
        self.distance_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.distance_var, width=10).pack(side='left', padx=5)

        ttk.Label(row1, text="Date (YYYY-MM-DD):").pack(side='left', padx=(15, 0))
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(row1, textvariable=self.date_var, width=12).pack(side='left', padx=5)

        ttk.Button(row1, text="Save Trip", command=self.save_trip).pack(side='right', padx=5)

        # Personal stats
        self.stats_frame = ttk.LabelFrame(main_frame, text="Your Green Transport Stats")
        self.stats_frame.pack(fill='x', pady=(0, 10))
        self.stats_label = ttk.Label(self.stats_frame, text="Loading...", justify='left')
        self.stats_label.pack(padx=15, pady=10)

        # Trip history
        hist_frame = ttk.LabelFrame(main_frame, text="Trip History")
        hist_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Method', 'Distance (km)', 'CO2 Saved (kg)', 'Trip Date', 'Recorded')
        self.tree = ttk.Treeview(hist_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        self.tree.column('ID', width=40)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Bottom buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_all).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete Selected", command=self.delete_trip).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side='right', padx=5)

    def _refresh_all(self):
        self.refresh_stats()
        self.load_log()

    def _calc_carbon_saved(self, method, distance):
        """Calculate CO2 saved compared to driving a car."""
        car_rate = 0.21  # kg CO2 per km
        method_rates = {
            "Walking": 0,
            "Cycling": 0,
            "Public Transport": 0.05,
            "Carpooling": 0.105,
            "Electric Vehicle": 0.05,
        }
        rate = method_rates.get(method, 0)
        return distance * (car_rate - rate)

    def save_trip(self):
        method = self.method_var.get().strip()
        if not method:
            messagebox.showwarning("Validation", "Please select a transport method.")
            return
        try:
            distance = float(self.distance_var.get() or 0)
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid distance.")
            return
        if distance <= 0:
            messagebox.showwarning("Validation", "Distance must be greater than zero.")
            return

        trip_date = self.date_var.get().strip() or datetime.now().strftime('%Y-%m-%d')
        carbon_saved = self._calc_carbon_saved(method, distance)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO green_transport_log
                    (transport_method, distance_km, carbon_saved, trip_date,
                     recorded_by, recorded_date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                method, distance, carbon_saved, trip_date,
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success",
                                f"Trip logged: {method} {distance} km\n"
                                f"CO2 saved vs car: {carbon_saved:.2f} kg")
            self.distance_var.set('0')
            self._refresh_all()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save trip: {e}")

    def refresh_stats(self):
        user_id = _get_current_user_id(self.auth)
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # This month stats
            month_start = datetime.now().strftime('%Y-%m-01')
            cursor.execute('''
                SELECT transport_method,
                       COUNT(*) as trips,
                       COALESCE(SUM(distance_km), 0) as total_km,
                       COALESCE(SUM(carbon_saved), 0) as total_saved
                FROM green_transport_log
                WHERE recorded_by = ? AND trip_date >= ?
                GROUP BY transport_method
            ''', (user_id, month_start))
            rows = cursor.fetchall()

            # All-time stats
            cursor.execute('''
                SELECT COUNT(*) as total_trips,
                       COALESCE(SUM(distance_km), 0) as total_km,
                       COALESCE(SUM(carbon_saved), 0) as total_saved
                FROM green_transport_log
                WHERE recorded_by = ?
            ''', (user_id,))
            totals = cursor.fetchone()
            conn.close()

            lines = ["This Month:"]
            month_saved = 0.0
            for r in rows:
                lines.append(f"  {r['transport_method']}: {r['trips']} trips, "
                             f"{r['total_km']:.1f} km, saved {r['total_saved']:.2f} kg CO2")
                month_saved += r['total_saved']

            if not rows:
                lines.append("  No trips logged this month yet.")

            lines.append(f"\nMonth CO2 Saved: {month_saved:.2f} kg")
            lines.append(f"\nAll-Time: {totals['total_trips']} trips, "
                         f"{totals['total_km']:.1f} km, "
                         f"{totals['total_saved']:.2f} kg CO2 saved")

            self.stats_label.config(text='\n'.join(lines))
        except Exception as e:
            self.stats_label.config(text=f"Error loading stats: {e}")

    def load_log(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT log_id, transport_method, distance_km, carbon_saved,
                       trip_date, recorded_date
                FROM green_transport_log
                ORDER BY recorded_date DESC LIMIT 50
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['log_id'], r['transport_method'],
                    f"{r['distance_km']:.1f}", f"{r['carbon_saved']:.2f}",
                    r['trip_date'] or '', r['recorded_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading transport log: {e}")

    def delete_trip(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection", "Please select a trip to delete.")
            return
        vals = self.tree.item(selected[0], 'values')
        if not messagebox.askyesno("Confirm", f"Delete trip #{vals[0]}?"):
            return
        try:
            conn = get_connection()
            conn.execute('DELETE FROM green_transport_log WHERE log_id = ?', (vals[0],))
            conn.commit()
            conn.close()
            self._refresh_all()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {e}")


class EnvironmentalReportsDialog:
    """Dialog for viewing environmental reports generated from DB data"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Environmental Reports")
        self.dialog.geometry("950x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.generate_report()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Environmental Impact Reports",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Report display
        self.report_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Courier', 10))
        self.report_text.pack(fill='both', expand=True, pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Regenerate Report", command=self.generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Save as TXT", command=self.save_as_txt).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Email to Admin", command=self.email_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def generate_report(self):
        """Build the sustainability report from actual database data."""
        self.report_text.config(state='normal')
        self.report_text.delete(1.0, tk.END)

        now = datetime.now()
        report_date = now.strftime('%B %Y')
        separator = '=' * 80

        lines = []
        lines.append(f"SUSTAINABILITY REPORT - {report_date.upper()}")
        lines.append(separator)
        lines.append('')

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # --- Carbon Emissions ---
            month_start = now.strftime('%Y-%m-01')
            prev_month_start = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-01')

            cursor.execute('''
                SELECT COALESCE(SUM(total_carbon), 0) as total,
                       COALESCE(SUM(transport_carbon), 0) as transport,
                       COALESCE(SUM(energy_carbon), 0) as energy,
                       COALESCE(SUM(catering_carbon), 0) as catering,
                       COUNT(*) as records
                FROM carbon_tracking
                WHERE recorded_date >= ?
            ''', (month_start,))
            current = cursor.fetchone()

            cursor.execute('''
                SELECT COALESCE(SUM(total_carbon), 0) as total
                FROM carbon_tracking
                WHERE recorded_date >= ? AND recorded_date < ?
            ''', (prev_month_start, month_start))
            prev = cursor.fetchone()

            cur_total = current['total']
            prev_total = prev['total']
            change = ((cur_total - prev_total) / prev_total * 100) if prev_total > 0 else 0

            lines.append('CARBON EMISSIONS:')
            lines.append(f'  Records this month: {current["records"]}')
            lines.append(f'  Total emissions this month: {cur_total:,.1f} kg CO2')
            lines.append(f'  Previous month: {prev_total:,.1f} kg CO2')
            if prev_total > 0:
                direction = "Improvement" if change < 0 else "Increase"
                lines.append(f'  Change: {change:+.1f}% ({direction})')
            lines.append('')
            lines.append('  Breakdown:')
            lines.append(f'  - Transport: {current["transport"]:,.1f} kg CO2')
            lines.append(f'  - Energy: {current["energy"]:,.1f} kg CO2')
            lines.append(f'  - Catering: {current["catering"]:,.1f} kg CO2')
            lines.append('')

            # --- Waste Management ---
            cursor.execute('''
                SELECT COALESCE(SUM(waste_generated), 0) as gen,
                       COALESCE(SUM(waste_recycled), 0) as rec,
                       COALESCE(SUM(waste_composted), 0) as comp,
                       COALESCE(SUM(waste_landfill), 0) as land,
                       COUNT(*) as entries
                FROM waste_reduction_log
                WHERE recorded_date >= ?
            ''', (month_start,))
            waste = cursor.fetchone()

            w_gen = waste['gen']
            w_rec = waste['rec']
            w_comp = waste['comp']
            w_land = waste['land']
            rec_rate = (w_rec / w_gen * 100) if w_gen > 0 else 0
            div_rate = ((w_rec + w_comp) / w_gen * 100) if w_gen > 0 else 0

            lines.append('WASTE MANAGEMENT:')
            lines.append(f'  Events logged: {waste["entries"]}')
            lines.append(f'  Total waste: {w_gen:,.1f} kg')
            lines.append(f'  Recycled: {w_rec:,.1f} kg ({rec_rate:.1f}%)')
            lines.append(f'  Composted: {w_comp:,.1f} kg')
            lines.append(f'  Landfill: {w_land:,.1f} kg')
            lines.append(f'  Landfill diversion rate: {div_rate:.1f}% (Target: 80%)')
            lines.append('')

            # --- Green Transport ---
            cursor.execute('''
                SELECT transport_method,
                       COUNT(*) as trips,
                       COALESCE(SUM(distance_km), 0) as km,
                       COALESCE(SUM(carbon_saved), 0) as saved
                FROM green_transport_log
                WHERE trip_date >= ?
                GROUP BY transport_method
                ORDER BY saved DESC
            ''', (month_start,))
            transport_rows = cursor.fetchall()

            cursor.execute('''
                SELECT COUNT(DISTINCT recorded_by) as users,
                       COALESCE(SUM(carbon_saved), 0) as total_saved
                FROM green_transport_log
                WHERE trip_date >= ?
            ''', (month_start,))
            transport_totals = cursor.fetchone()

            lines.append('GREEN TRANSPORT:')
            lines.append(f'  Active users: {transport_totals["users"]}')
            lines.append(f'  Total CO2 saved: {transport_totals["total_saved"]:,.1f} kg')
            for tr in transport_rows:
                lines.append(f'  - {tr["transport_method"]}: {tr["trips"]} trips, '
                             f'{tr["km"]:.1f} km, {tr["saved"]:.1f} kg CO2 saved')
            lines.append('')

            # --- Green Initiatives ---
            cursor.execute('''
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                FROM green_initiatives
            ''')
            init_row = cursor.fetchone()
            lines.append('GREEN INITIATIVES:')
            lines.append(f'  Total initiatives: {init_row["total"]}')
            lines.append(f'  Active: {init_row["active"] or 0}')
            lines.append(f'  Completed: {init_row["completed"] or 0}')
            lines.append('')

            # --- Eco Suppliers ---
            cursor.execute('SELECT COUNT(*) as cnt FROM eco_suppliers')
            sup_cnt = cursor.fetchone()['cnt']
            lines.append(f'ECO SUPPLIERS: {sup_cnt} registered')
            lines.append('')

            # --- Certifications ---
            cursor.execute('''
                SELECT certification_level, COUNT(*) as cnt
                FROM green_certifications
                GROUP BY certification_level
                ORDER BY cnt DESC
            ''')
            cert_rows = cursor.fetchall()
            lines.append('GREEN CERTIFICATIONS:')
            if cert_rows:
                for cr in cert_rows:
                    lines.append(f'  {cr["certification_level"]}: {cr["cnt"]}')
            else:
                lines.append('  No certifications awarded yet.')
            lines.append('')

            # --- Recommendations ---
            lines.append('RECOMMENDATIONS:')
            rec_num = 1
            if rec_rate < 80 and w_gen > 0:
                lines.append(f'  {rec_num}. Increase recycling rate (currently {rec_rate:.0f}%, target 80%)')
                rec_num += 1
            if cur_total > 0 and current['transport'] > cur_total * 0.4:
                lines.append(f'  {rec_num}. Reduce transport emissions (currently {current["transport"]/cur_total*100:.0f}% of total)')
                rec_num += 1
            if transport_totals['users'] < 5:
                lines.append(f'  {rec_num}. Encourage more users to log green transport trips')
                rec_num += 1
            lines.append(f'  {rec_num}. Continue expanding green initiatives')
            lines.append('')

            conn.close()

        except Exception as e:
            lines.append(f'Error generating report: {e}')
            lines.append('')

        lines.append(separator)
        lines.append(f'Generated: {now.strftime("%Y-%m-%d %H:%M:%S")}')

        self.report_text.insert(1.0, '\n'.join(lines))
        self.report_text.config(state='disabled')

    def save_as_txt(self):
        """Save the report content to a TXT file."""
        self.report_text.config(state='normal')
        content = self.report_text.get(1.0, tk.END).strip()
        self.report_text.config(state='disabled')

        if not content:
            messagebox.showwarning("No Report", "No report content to save.")
            return

        file_path = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Save Environmental Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"sustainability_report_{datetime.now().strftime('%Y%m%d')}.txt"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("Success", f"Report saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {e}")

    def email_report(self):
        """Email report to admin from database"""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection as _gc
            from education_system.post_18.university_system.infrastructure.email.email_service.core import send_email

            # Get admin email from database
            admin_email = None
            try:
                conn = _gc()
                cursor = conn.execute("""
                    SELECT email FROM users
                    WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                    LIMIT 1
                """)
                admin_row = cursor.fetchone()
                if admin_row:
                    admin_email = admin_row['email'] if isinstance(admin_row, sqlite3.Row) else admin_row[0]
                conn.close()
            except Exception as e:
                print(f"Warning: Could not fetch admin email: {e}")

            if not admin_email:
                # Prompt user for email address
                admin_email = simpledialog.askstring(
                    "Email Address",
                    "No admin email found in database.\nEnter recipient email:",
                    parent=self.dialog
                )
                if not admin_email:
                    return

            # Get report content
            self.report_text.config(state='normal')
            report_content = self.report_text.get(1.0, tk.END).strip()
            self.report_text.config(state='disabled')

            if not report_content:
                messagebox.showwarning("No Report", "No report content to send.")
                return

            subject = f"Sustainability Report - {datetime.now().strftime('%B %Y')}"
            body = report_content

            # Try to use render_template if available, fall back to plain text
            try:
                subject, body = render_template('student_union/environmental_report', {
                    'report_date': datetime.now().strftime('%Y-%m-%d'),
                    'generation_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'separator': '=' * 60,
                    'report_content': report_content
                })
            except Exception:
                pass  # Use plain text subject/body

            result = send_email(
                recipient_email=admin_email,
                subject=subject,
                body=body
            )

            if result:
                messagebox.showinfo("Success", f"Report sent successfully to {admin_email}")
            else:
                messagebox.showinfo("Queued", f"Report queued for delivery to {admin_email}")

        except ImportError:
            messagebox.showerror("Error", "Email service is not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send report: {str(e)}")


class SustainableEventsDialog:
    """Dialog for tracking sustainability of events."""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Sustainable Events")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Sustainable Events Tracker",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        info_label = ttk.Label(main_frame,
                                text="Track the environmental impact of events. "
                                     "Use Carbon Tracking and Waste Reduction dialogs "
                                     "to log detailed data per event.",
                                wraplength=800, foreground='gray')
        info_label.pack(pady=(0, 10))

        # Events from sustainability_tracking (the existing core table)
        list_frame = ttk.LabelFrame(main_frame, text="Events with Sustainability Data")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Event', 'Carbon (kg)', 'Waste (kg)', 'Recycled (kg)', 'Score', 'Date')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        self.tree.column('Event', width=200)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text="Refresh", command=self.load_events).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side='right', padx=5)

    def load_events(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            # Try reading from the core sustainability_tracking table
            cursor.execute('''
                SELECT st.tracking_id,
                       COALESCE(e.event_name, 'Event #' || st.event_id) as event_name,
                       st.carbon_footprint, st.waste_generated, st.waste_recycled,
                       st.sustainability_score, st.recorded_date
                FROM sustainability_tracking st
                LEFT JOIN union_events e ON st.event_id = e.event_id
                ORDER BY st.recorded_date DESC
                LIMIT 50
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['event_name'] or '',
                    f"{r['carbon_footprint']:.1f}" if r['carbon_footprint'] else '0.0',
                    f"{r['waste_generated']:.1f}" if r['waste_generated'] else '0.0',
                    f"{r['waste_recycled']:.1f}" if r['waste_recycled'] else '0.0',
                    f"{r['sustainability_score']:.0f}" if r['sustainability_score'] else '-',
                    r['recorded_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading sustainable events: {e}")


class EcoSuppliersDialog:
    """Dialog for managing eco-friendly suppliers."""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Eco Suppliers Directory")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_suppliers()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Eco-Friendly Supplier Directory",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Add supplier form
        form_frame = ttk.LabelFrame(main_frame, text="Add New Supplier")
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(row1, text="Name:").pack(side='left')
        self.name_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.name_var, width=30).pack(side='left', padx=5)

        ttk.Label(row1, text="Category:").pack(side='left', padx=(10, 0))
        self.cat_var = tk.StringVar()
        ttk.Combobox(row1, textvariable=self.cat_var, width=20,
                      values=["Catering", "Venues", "Equipment", "Transport",
                              "Printing", "Energy", "Other"]).pack(side='left', padx=5)

        ttk.Label(row1, text="Rating (1-5):").pack(side='left', padx=(10, 0))
        self.rating_var = tk.StringVar(value="4")
        ttk.Entry(row1, textvariable=self.rating_var, width=5).pack(side='left', padx=5)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(row2, text="Contact Email:").pack(side='left')
        self.email_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.email_var, width=30).pack(side='left', padx=5)

        ttk.Label(row2, text="Certifications:").pack(side='left', padx=(10, 0))
        self.certs_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.certs_var, width=30).pack(side='left', padx=5)

        row3 = ttk.Frame(form_frame)
        row3.pack(fill='x', padx=10, pady=5)
        ttk.Label(row3, text="Description:").pack(side='left')
        self.desc_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self.desc_var, width=60).pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(row3, text="Add Supplier", command=self.add_supplier).pack(side='right', padx=5)

        # Supplier list
        list_frame = ttk.LabelFrame(main_frame, text="Registered Suppliers")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Category', 'Certifications', 'Email', 'Rating', 'Added')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110)
        self.tree.column('ID', width=40)
        self.tree.column('Name', width=160)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text="Refresh", command=self.load_suppliers).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete Selected", command=self.delete_supplier).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side='right', padx=5)

    def load_suppliers(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT supplier_id, name, category, certifications,
                       contact_email, rating, added_date
                FROM eco_suppliers ORDER BY name
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['supplier_id'], r['name'], r['category'] or '',
                    r['certifications'] or '', r['contact_email'] or '',
                    f"{r['rating']:.1f}" if r['rating'] else '',
                    r['added_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading suppliers: {e}")

    def add_supplier(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Please enter a supplier name.")
            return
        try:
            rating = float(self.rating_var.get() or 0)
            rating = max(0, min(5, rating))
        except ValueError:
            rating = 0

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO eco_suppliers
                    (name, category, certifications, description,
                     contact_email, rating, added_by, added_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                self.cat_var.get().strip() or 'Other',
                self.certs_var.get().strip(),
                self.desc_var.get().strip(),
                self.email_var.get().strip(),
                rating,
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", f"Supplier '{name}' added.")
            self.name_var.set('')
            self.cat_var.set('')
            self.certs_var.set('')
            self.desc_var.set('')
            self.email_var.set('')
            self.rating_var.set('4')
            self.load_suppliers()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add supplier: {e}")

    def delete_supplier(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection", "Please select a supplier to delete.")
            return
        vals = self.tree.item(selected[0], 'values')
        if not messagebox.askyesno("Confirm", f"Delete supplier '{vals[1]}'?"):
            return
        try:
            conn = get_connection()
            conn.execute('DELETE FROM eco_suppliers WHERE supplier_id = ?', (vals[0],))
            conn.commit()
            conn.close()
            self.load_suppliers()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {e}")


class GreenCertificationsDialog:
    """Dialog for managing green certifications."""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Green Certifications")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_certifications()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Green Certification Management",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Standards info
        info_frame = ttk.LabelFrame(main_frame, text="Certification Levels")
        info_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(info_frame,
                  text="Bronze (70-79 pts): Basic sustainability practices  |  "
                       "Silver (80-89 pts): Comprehensive management  |  "
                       "Gold (90-95 pts): 90%+ waste diverted  |  "
                       "Platinum (95+ pts): Net carbon negative",
                  wraplength=800).pack(padx=10, pady=8)

        # Award certification form
        form_frame = ttk.LabelFrame(main_frame, text="Award Certification")
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)

        ttk.Label(row1, text="Entity Name:").pack(side='left')
        self.entity_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.entity_var, width=25).pack(side='left', padx=5)

        ttk.Label(row1, text="Type:").pack(side='left', padx=(10, 0))
        self.type_var = tk.StringVar()
        ttk.Combobox(row1, textvariable=self.type_var, width=15,
                      values=["Club", "Event", "Individual", "Department"],
                      state='readonly').pack(side='left', padx=5)

        ttk.Label(row1, text="Level:").pack(side='left', padx=(10, 0))
        self.level_var = tk.StringVar()
        ttk.Combobox(row1, textvariable=self.level_var, width=12,
                      values=["Bronze", "Silver", "Gold", "Platinum"],
                      state='readonly').pack(side='left', padx=5)

        ttk.Label(row1, text="Score:").pack(side='left', padx=(10, 0))
        self.score_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.score_var, width=6).pack(side='left', padx=5)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(row2, text="Notes:").pack(side='left')
        self.notes_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.notes_var, width=60).pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(row2, text="Award", command=self.award_cert).pack(side='right', padx=5)

        # Certifications list
        list_frame = ttk.LabelFrame(main_frame, text="Awarded Certifications")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Entity', 'Type', 'Level', 'Score', 'Awarded', 'Expires', 'Notes')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        self.tree.column('ID', width=40)
        self.tree.column('Entity', width=160)
        self.tree.column('Notes', width=150)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text="Refresh", command=self.load_certifications).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Revoke Selected", command=self.revoke_cert).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side='right', padx=5)

    def load_certifications(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT cert_id, entity_name, entity_type, certification_level,
                       score, awarded_date, expires_date, notes
                FROM green_certifications
                ORDER BY awarded_date DESC
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['cert_id'], r['entity_name'], r['entity_type'] or '',
                    r['certification_level'], f"{r['score']:.0f}" if r['score'] else '',
                    r['awarded_date'] or '', r['expires_date'] or '',
                    r['notes'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading certifications: {e}")

    def award_cert(self):
        entity = self.entity_var.get().strip()
        etype = self.type_var.get().strip()
        level = self.level_var.get().strip()
        if not entity or not level:
            messagebox.showwarning("Validation", "Please fill in entity name and level.")
            return
        try:
            score = float(self.score_var.get() or 0)
        except ValueError:
            score = 0

        awarded = datetime.now().strftime('%Y-%m-%d')
        expires = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO green_certifications
                    (entity_name, entity_type, certification_level, score,
                     awarded_date, expires_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (entity, etype or 'Other', level, score, awarded, expires,
                  self.notes_var.get().strip()))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success",
                                f"{level} certification awarded to '{entity}'.\n"
                                f"Valid until: {expires}")
            self.entity_var.set('')
            self.type_var.set('')
            self.level_var.set('')
            self.score_var.set('0')
            self.notes_var.set('')
            self.load_certifications()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to award certification: {e}")

    def revoke_cert(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection", "Please select a certification to revoke.")
            return
        vals = self.tree.item(selected[0], 'values')
        if not messagebox.askyesno("Confirm", f"Revoke {vals[3]} certification for '{vals[1]}'?"):
            return
        try:
            conn = get_connection()
            conn.execute('DELETE FROM green_certifications WHERE cert_id = ?', (vals[0],))
            conn.commit()
            conn.close()
            self.load_certifications()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to revoke: {e}")


class OffsetProgramsDialog:
    """Dialog for managing carbon offset programs."""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Carbon Offset Programs")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_offsets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Carbon Offset Programs",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Summary
        self.summary_label = ttk.Label(main_frame, text="Loading summary...",
                                        font=('Arial', 11))
        self.summary_label.pack(pady=(0, 10))

        # Add offset form
        form_frame = ttk.LabelFrame(main_frame, text="Register Offset Purchase")
        form_frame.pack(fill='x', pady=(0, 10))

        row1 = ttk.Frame(form_frame)
        row1.pack(fill='x', padx=10, pady=5)
        ttk.Label(row1, text="Program Name:").pack(side='left')
        self.prog_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.prog_var, width=30).pack(side='left', padx=5)

        ttk.Label(row1, text="Offset (kg CO2):").pack(side='left', padx=(10, 0))
        self.offset_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.offset_var, width=10).pack(side='left', padx=5)

        ttk.Label(row1, text="Cost:").pack(side='left', padx=(10, 0))
        self.cost_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.cost_var, width=10).pack(side='left', padx=5)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill='x', padx=10, pady=5)
        ttk.Label(row2, text="Description:").pack(side='left')
        self.desc_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.desc_var, width=55).pack(side='left', padx=5, fill='x', expand=True)

        ttk.Label(row2, text="Status:").pack(side='left', padx=(10, 0))
        self.status_var = tk.StringVar(value="purchased")
        ttk.Combobox(row2, textvariable=self.status_var, width=12,
                      values=["pending", "purchased", "verified", "retired"],
                      state='readonly').pack(side='left', padx=5)

        ttk.Button(row2, text="Save", command=self.save_offset).pack(side='right', padx=5)

        # Offsets list
        list_frame = ttk.LabelFrame(main_frame, text="Offset Records")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Program', 'Description', 'Offset (kg)', 'Cost', 'Status', 'Date')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110)
        self.tree.column('ID', width=40)
        self.tree.column('Program', width=160)
        self.tree.column('Description', width=180)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text="Refresh", command=self.load_offsets).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Delete Selected", command=self.delete_offset).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side='right', padx=5)

    def load_offsets(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT offset_id, program_name, description, offset_kg,
                       cost, status, purchase_date
                FROM carbon_offsets ORDER BY purchase_date DESC
            ''')
            for r in cursor.fetchall():
                self.tree.insert('', 'end', values=(
                    r['offset_id'], r['program_name'], r['description'] or '',
                    f"{r['offset_kg']:.1f}", f"{r['cost']:.2f}",
                    r['status'], r['purchase_date'] or ''
                ))

            # Update summary
            cursor.execute('''
                SELECT COALESCE(SUM(offset_kg), 0) as total_offset,
                       COALESCE(SUM(cost), 0) as total_cost,
                       COUNT(*) as cnt
                FROM carbon_offsets
            ''')
            s = cursor.fetchone()
            self.summary_label.config(
                text=f"Total offset programs: {s['cnt']}  |  "
                     f"Total CO2 offset: {s['total_offset']:,.1f} kg  |  "
                     f"Total invested: {s['total_cost']:,.2f}")
            conn.close()
        except Exception as e:
            logger.error(f"Error loading offsets: {e}")
            self.summary_label.config(text=f"Error loading data: {e}")

    def save_offset(self):
        prog = self.prog_var.get().strip()
        if not prog:
            messagebox.showwarning("Validation", "Please enter a program name.")
            return
        try:
            offset_kg = float(self.offset_var.get() or 0)
            cost = float(self.cost_var.get() or 0)
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers.")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO carbon_offsets
                    (program_name, description, offset_kg, cost, status,
                     purchased_by, purchase_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                prog,
                self.desc_var.get().strip(),
                offset_kg,
                cost,
                self.status_var.get(),
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success",
                                f"Offset record saved: {offset_kg:.1f} kg CO2 via '{prog}'.")
            self.prog_var.set('')
            self.desc_var.set('')
            self.offset_var.set('0')
            self.cost_var.set('0')
            self.load_offsets()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def delete_offset(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection", "Please select an offset record to delete.")
            return
        vals = self.tree.item(selected[0], 'values')
        if not messagebox.askyesno("Confirm", f"Delete offset record '{vals[1]}'?"):
            return
        try:
            conn = get_connection()
            conn.execute('DELETE FROM carbon_offsets WHERE offset_id = ?', (vals[0],))
            conn.commit()
            conn.close()
            self.load_offsets()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {e}")


# ============================================================================
# VOLUNTEERING SYSTEM DIALOGS
# ============================================================================


def open_green_initiatives_dialog(self):
    """Open green initiatives and sustainability dialog"""
    dialog = GreenInitiativesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
