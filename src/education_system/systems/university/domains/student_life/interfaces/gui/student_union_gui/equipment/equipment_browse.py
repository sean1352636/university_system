
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
logger = logging.getLogger(__name__)
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
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
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class EquipmentBrowseDialog:
    """Dialog for browsing available equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.windows.browse_equipment', default="Browse Equipment"))
        self.dialog.geometry("1000x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.equipment_catalog', default="Equipment Catalog"), font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Filter
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.category', default="Category:")).pack(side='left', padx=(0, 10))
        self.category_var = tk.StringVar(value=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.values.all', default="All"))
        category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, width=20)
        try:
            _conn = get_connection(row_factory=False)
            try:
                category_combo['values'] = ('All', *_catalogue().categories(_conn))
            finally:
                _conn.close()
        except sqlite3.Error:
            category_combo['values'] = ('All',)
        category_combo.pack(side='left')
        category_combo.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        # Equipment list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.available_equipment', default="Available Equipment"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Category', 'Condition', 'Location', 'Status')
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.equipment_tree.heading(col, text=col)
            self.equipment_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=scrollbar.set)

        self.equipment_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.check_out', default="Check Out"), command=self.checkout).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.my_equipment', default="My Equipment"), command=self.view_my_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        for item in self.equipment_tree.get_children():
            self.equipment_tree.delete(item)

        try:
            conn = get_connection(row_factory=False)
            cursor = conn.cursor()

            category_filter = self.category_var.get()
            if category_filter == "All":
                cursor.execute('''
                SELECT equipment_id, equipment_name, category, condition_status,
                       location, availability_status
                FROM union_equipment
                WHERE availability_status = 'available'
                ORDER BY equipment_name
                ''')
            else:
                cursor.execute('''
                SELECT equipment_id, equipment_name, category, condition_status,
                       location, availability_status
                FROM union_equipment
                WHERE availability_status = 'available' AND category = ?
                ORDER BY equipment_name
                ''', (category_filter,))

            equipment = cursor.fetchall()
            for item in equipment:
                self.equipment_tree.insert('', 'end', values=item)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.error', default="Error"), f"Failed to load equipment: {str(e)}")

    def checkout(self):
        selection = self.equipment_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.please_select_equipment_to_check_out', default="Please select equipment to check out."))
            return

        item = self.equipment_tree.item(selection[0])
        equipment_id = item['values'][0]
        equipment_name = item['values'][1]

        from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.equipment.equipment_checkout import EquipmentCheckoutDialog
        dialog = EquipmentCheckoutDialog(self.dialog, self.auth, equipment_id, equipment_name)
        self.dialog.wait_window(dialog.dialog)
        self.load_data()

    def view_my_equipment(self):
        from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.equipment.equipment_checkout import MyEquipmentDialog
        dialog = MyEquipmentDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



def _catalogue():
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.facilities import (
        equipment_catalogue,
    )
    return equipment_catalogue


def _owner_id(conn, auth):
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
        current_student_id,
    )
    return current_student_id(conn.cursor(), auth)


def _open_conn():
    conn = get_connection(row_factory=False)
    _catalogue().ensure_schema(conn)
    conn.commit()
    return conn


def _fmt_money(value):
    try:
        return f"£{float(value):,.2f}" if value is not None else "Not recorded"
    except (TypeError, ValueError):
        return str(value)


def _open_checkout(parent, auth, equipment_id, equipment_name, status):
    """Hand a real item to the real checkout dialog, if it can be borrowed."""
    if (status or '').lower() != 'available':
        messagebox.showwarning(
            _t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.check_out', default="Check Out"),
            f"{equipment_name} is {_catalogue().status_label(status).lower()} and cannot be checked out now.\n\n"
            "Use Reserve to request it for later dates.",
            parent=parent)
        return False
    from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.equipment.equipment_checkout import EquipmentCheckoutDialog
    dialog = EquipmentCheckoutDialog(parent, auth, equipment_id, equipment_name)
    parent.wait_window(dialog.dialog)
    return True


class ReserveEquipmentDialog:
    """Request an item for future dates (su_equipment_reservations)."""

    def __init__(self, parent, auth_manager, equipment_id, equipment_name):
        self.parent = parent
        self.auth = auth_manager
        self.equipment_id = equipment_id
        self.equipment_name = equipment_name
        self.saved = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.reserve', default="Reserve"))
        self.dialog.geometry("520x420")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        frame = ttk.Frame(self.dialog)
        frame.pack(fill='both', expand=True, padx=15, pady=15)
        ttk.Label(frame, text=f"Reserve: {equipment_name}", font=('Arial', 12, 'bold')).pack(anchor='w', pady=(0, 10))

        self.existing_label = ttk.Label(frame, text="", justify='left', foreground='gray')
        self.existing_label.pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.pickup_date', default="Pickup date (YYYY-MM-DD):")).pack(anchor='w')
        self.pickup_var = tk.StringVar(value=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=self.pickup_var).pack(fill='x', pady=(0, 8))
        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.return_date', default="Return date (YYYY-MM-DD):")).pack(anchor='w')
        self.return_var = tk.StringVar(value=(datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=self.return_var).pack(fill='x', pady=(0, 8))
        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.reason_for_use', default="Reason for use:")).pack(anchor='w')
        self.purpose_text = scrolledtext.ScrolledText(frame, height=5, wrap=tk.WORD)
        self.purpose_text.pack(fill='both', expand=True, pady=(0, 10))

        buttons = ttk.Frame(frame)
        buttons.pack(fill='x')
        ttk.Button(buttons, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.reserve', default="Reserve"), command=self.submit).pack(side='left')
        ttk.Button(buttons, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

        self._show_existing()

    def _show_existing(self):
        try:
            conn = _open_conn()
            try:
                taken = _catalogue().open_reservations(conn, self.equipment_id)
            finally:
                conn.close()
        except sqlite3.Error:
            taken = []
        if taken:
            lines = [f"  {r['pickup_date']} to {r['return_date']} ({r['status']})" for r in taken]
            self.existing_label.config(text="Already requested:\n" + "\n".join(lines))
        else:
            self.existing_label.config(text="No other requests for this item.")

    def submit(self):
        purpose = self.purpose_text.get('1.0', tk.END).strip()
        if not purpose:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.warning', default="Warning"),
                                   "Please give a reason for use.", parent=self.dialog)
            return
        try:
            conn = _open_conn()
            try:
                owner = _owner_id(conn, self.auth)
                cat = _catalogue()
                rid = cat.reserve(conn, equipment_id=self.equipment_id, requester_id=owner,
                                  pickup_date=self.pickup_var.get(), return_date=self.return_var.get(),
                                  purpose=purpose)
                from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import contact_email
                email = contact_email(conn.cursor(), owner)
            finally:
                conn.close()
        except ValueError as e:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.reserve', default="Reserve"), str(e), parent=self.dialog)
            return
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.error', default="Error"), f"Failed to reserve equipment: {e}", parent=self.dialog)
            return

        sent = False
        if email:
            try:
                from education_system.systems.university.infrastructure.email import send_email
                send_email(email, f"Equipment reservation requested: {self.equipment_name}",
                           f"Your request to reserve {self.equipment_name} has been recorded.\n\n"
                           f"Reservation ID: {rid}\nPickup: {self.pickup_var.get()}\n"
                           f"Return: {self.return_var.get()}\nStatus: pending approval\n")
                sent = True
            except Exception:
                logger.debug("reservation email failed", exc_info=True)
        self.saved = True
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.reserve', default="Reserve"),
                            f"Reservation #{rid} requested for {self.equipment_name}.\n"
                            f"Status: pending approval."
                            + ("\nA confirmation email has been sent." if sent else ""),
                            parent=self.dialog)
        self.dialog.destroy()


class BrowseAvailableEquipmentDialog:
    """Dialog for browsing available equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self._rows = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.windows.browse_equipment', default="Browse Equipment"))
        self.dialog.geometry("1100x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.browse_available_equipment', default="📋 Browse Available Equipment"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Category filter
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.category', default="Category:")).pack(side='left', padx=(0, 10))
        self.category_combo = ttk.Combobox(filter_frame, width=25, state='readonly')
        self.category_combo['values'] = ('All Categories',)
        self.category_combo.current(0)
        self.category_combo.pack(side='left', padx=(0, 20))
        self.category_combo.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        ttk.Label(filter_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.status', default="Status:")).pack(side='left', padx=(0, 10))
        self.status_combo = ttk.Combobox(filter_frame, width=20, state='readonly')
        self.status_combo['values'] = ('All Status', 'Available', 'Checked Out', 'Maintenance', 'Reserved')
        self.status_combo.current(1)  # Available
        self.status_combo.pack(side='left')
        self.status_combo.bind('<<ComboboxSelected>>', lambda e: self.load_data())

        # Equipment list
        self.list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.available_equipment', default="Available Equipment"))
        self.list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Name', 'Category', 'Condition', 'Location', 'Status', 'Last Checkout')
        self.tree = ttk.Treeview(self.list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.tree.heading(col, text=col)
            if col == 'Name':
                self.tree.column(col, width=200)
            elif col == 'Category':
                self.tree.column(col, width=120)
            else:
                self.tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(self.list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        self.tree.bind('<Double-1>', lambda e: self.view_details())

        self.empty_label = ttk.Label(main_frame, text="", foreground='gray')
        self.empty_label.pack(anchor='w')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.view_details', default="View Details"), command=self.view_details).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.check_out_selected', default="Check Out Selected"), command=self.checkout_selected).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.reserve', default="Reserve"), command=self.reserve_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = {}
        cat = _catalogue()
        try:
            conn = _open_conn()
            try:
                current = self.category_combo.get()
                values = cat.with_any(cat.categories(conn), 'All Categories')
                self.category_combo['values'] = values
                if current not in values:
                    self.category_combo.current(0)
                rows = cat.search(conn, category=self.category_combo.get(),
                                  status=cat.status_from_label(self.status_combo.get()))
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.error', default="Error"), f"Failed to load equipment: {e}", parent=self.dialog)
            return

        for r in rows:
            iid = self.tree.insert('', 'end', values=(
                r['equipment_id'], r['name'], r['category'] or '', r['condition'] or '',
                r['location'] or '', cat.status_label(r['status']),
                (r['last_checkout'] or 'Never')[:10]))
            self._rows[iid] = r
        self.list_frame.config(text=f"{self.status_combo.get()} Equipment ({len(rows)})")
        self.empty_label.config(text="" if rows else "No equipment matches these filters.")

    def _selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.warning', default="Warning"),
                                   "Please select an item of equipment first.", parent=self.dialog)
            return None
        return self._rows.get(selection[0])

    def view_details(self):
        row = self._selected()
        if row:
            dialog = ViewEquipmentDetailsDialog(self.dialog, self.auth, row['equipment_id'])
            self.dialog.wait_window(dialog.dialog)
            self.load_data()

    def checkout_selected(self):
        row = self._selected()
        if row and _open_checkout(self.dialog, self.auth, row['equipment_id'], row['name'], row['status']):
            self.load_data()

    def reserve_equipment(self):
        row = self._selected()
        if row:
            dialog = ReserveEquipmentDialog(self.dialog, self.auth, row['equipment_id'], row['name'])
            self.dialog.wait_window(dialog.dialog)



class ViewEquipmentDetailsDialog:
    """Dialog for viewing equipment details"""

    def __init__(self, parent, auth_manager, equipment_id=None):
        self.parent = parent
        self.auth = auth_manager
        self.equipment_id = equipment_id
        self.info = None
        self._choices = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.windows.equipment_details', default="Equipment Details"))
        self.dialog.geometry("700x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_details()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        # Picker — the menu entry opens this window without an item chosen.
        picker = ttk.Frame(main_frame)
        picker.pack(fill='x', pady=(0, 10))
        ttk.Label(picker, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.equipment', default="Equipment:")).pack(side='left', padx=(0, 10))
        self.picker_combo = ttk.Combobox(picker, width=50, state='readonly')
        self.picker_combo.pack(side='left', fill='x', expand=True)
        self.picker_combo.bind('<<ComboboxSelected>>', self._on_pick)

        self.title_label = ttk.Label(main_frame, text="", font=('Arial', 13, 'bold'))
        self.title_label.pack(pady=(0, 15))

        # Equipment info
        info_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.equipment_information', default="Equipment Information"))
        info_frame.pack(fill='both', expand=True, pady=(0, 15))

        self.info_grid = ttk.Frame(info_frame)
        self.info_grid.pack(fill='both', padx=15, pady=10)

        # Description
        desc_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.description_included_items', default="Description & Included Items"))
        desc_frame.pack(fill='x', pady=(0, 15))
        self.desc_label = ttk.Label(desc_frame, text="", justify='left', font=('Arial', 9), wraplength=620)
        self.desc_label.pack(padx=15, pady=10, anchor='w')

        # Usage notes
        notes_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.usage_notes_restrictions', default="Usage Notes & Restrictions"))
        notes_frame.pack(fill='x', pady=(0, 15))
        self.notes_label = ttk.Label(notes_frame, text="", justify='left', font=('Arial', 9), wraplength=620)
        self.notes_label.pack(padx=15, pady=10, anchor='w')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.check_out', default="Check Out"), command=self.checkout).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.reserve', default="Reserve"), command=self.reserve).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.view_history', default="View History"), command=self.view_history).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def _on_pick(self, _event=None):
        self.equipment_id = self._choices.get(self.picker_combo.get())
        self.load_details()

    def load_details(self):
        cat = _catalogue()
        try:
            conn = _open_conn()
            try:
                items = cat.search(conn)
                self._choices = {f"{r['equipment_id']} - {r['name']}": r['equipment_id'] for r in items}
                self.info = cat.details(conn, self.equipment_id) if self.equipment_id else None
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.error', default="Error"), f"Failed to load equipment: {e}", parent=self.dialog)
            return

        self.picker_combo['values'] = list(self._choices)
        for label, eid in self._choices.items():
            if eid == self.equipment_id:
                self.picker_combo.set(label)

        for w in self.info_grid.winfo_children():
            w.destroy()

        info = self.info
        if not info:
            self.title_label.config(text="No equipment selected" if self._choices else "No equipment recorded yet")
            self.desc_label.config(text="Choose an item above." if self._choices else
                                   "The Student Union has not added any equipment.")
            self.notes_label.config(text="")
            return

        self.title_label.config(text=info['name'] or f"Equipment {info['equipment_id']}")
        last = info['last_checkout']
        last_text = f"{(last['checkout_date'] or '')[:10]} by {last['borrower']}" if last else "Never"
        info_data = [
            ("Equipment ID:", info['equipment_id']),
            ("Category:", info['category'] or "Not set"),
            ("Serial Number:", info['serial_number'] or "Not recorded"),
            ("Condition:", (info['condition'] or "Not recorded").title()),
            ("Purchase Date:", info['purchase_date'] or "Not recorded"),
            ("Value:", _fmt_money(info['replacement_cost'])),
            ("Location:", info['location'] or "Not recorded"),
            ("Status:", cat.status_label(info['status'])),
            ("Last Checkout:", last_text),
            ("Times Borrowed:", info['times_borrowed']),
            ("Next Maintenance:", info['maintenance_due'] or "Not scheduled"),
        ]
        for i, (label, value) in enumerate(info_data):
            ttk.Label(self.info_grid, text=label, font=('Arial', 9, 'bold')).grid(row=i, column=0, sticky='w', pady=2)
            ttk.Label(self.info_grid, text=str(value)).grid(row=i, column=1, sticky='w', padx=10, pady=2)

        self.desc_label.config(text=info['description'] or "No description recorded.")

        notes = []
        if info['reservations']:
            notes.append("Requested dates:")
            notes += [f"  {r['pickup_date']} to {r['return_date']} ({r['status']})" for r in info['reservations']]
        else:
            notes.append("No upcoming reservations.")
        if info['replacement_cost']:
            notes.append(f"Borrowers are responsible for loss or damage (replacement value {_fmt_money(info['replacement_cost'])}).")
        self.notes_label.config(text="\n".join(notes))

    def _need_item(self):
        if not self.info:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.warning', default="Warning"),
                                   "Please choose an item of equipment first.", parent=self.dialog)
            return False
        return True

    def checkout(self):
        if self._need_item() and _open_checkout(self.dialog, self.auth, self.info['equipment_id'],
                                                self.info['name'], self.info['status']):
            self.load_details()

    def reserve(self):
        if self._need_item():
            dialog = ReserveEquipmentDialog(self.dialog, self.auth, self.info['equipment_id'], self.info['name'])
            self.dialog.wait_window(dialog.dialog)
            self.load_details()

    def view_history(self):
        if not self._need_item():
            return
        history = self.info['history']
        if not history:
            text = "This item has never been checked out."
        else:
            lines = []
            for i, h in enumerate(history, 1):
                span = f"{h['days']} days" if h['days'] is not None else "still out"
                lines.append(f"{i}. {(h['checkout_date'] or '')[:10]} - {h['borrower']} ({span})")
            returned = [h for h in history if h['late'] is not None]
            late = sum(1 for h in returned if h['late'])
            damaged = sum(1 for h in history if (h['condition_in'] or '').lower() in ('poor', 'damaged'))
            text = (f"Recent Checkouts (Last {len(history)}):\n\n" + "\n".join(lines) +
                    f"\n\nLate returns: {late} of {len(returned)} returned"
                    f"\nReturned in poor/damaged condition: {damaged}")
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.checkout_history', default="Checkout History"),
                            text, parent=self.dialog)



class SearchEquipmentDialog:
    """Dialog for searching equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self._rows = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.windows.search_equipment', default="Search Equipment"))
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.search(announce=False)

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.search_equipment', default="🔍 Search Equipment"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Search criteria
        search_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.search_criteria', default="Search Criteria"))
        search_frame.pack(fill='x', pady=(0, 15))

        search_content = ttk.Frame(search_frame)
        search_content.pack(fill='x', padx=15, pady=10)

        # Search text
        ttk.Label(search_content, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.keyword', default="Keyword:")).grid(row=0, column=0, sticky='w', pady=5)
        self.search_entry = ttk.Entry(search_content, width=40)
        self.search_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)
        self.search_entry.bind('<Return>', lambda e: self.search())

        cat = _catalogue()
        try:
            conn = _open_conn()
            try:
                category_values = cat.with_any(cat.categories(conn), 'Any')
                condition_values = cat.with_any([c.title() for c in cat.conditions(conn)], 'Any')
            finally:
                conn.close()
        except sqlite3.Error:
            category_values, condition_values = ('Any',), ('Any',)

        # Category
        ttk.Label(search_content, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.category', default="Category:")).grid(row=1, column=0, sticky='w', pady=5)
        self.category_combo = ttk.Combobox(search_content, width=38, state='readonly')
        self.category_combo['values'] = category_values
        self.category_combo.current(0)
        self.category_combo.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        # Status
        ttk.Label(search_content, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.status', default="Status:")).grid(row=2, column=0, sticky='w', pady=5)
        self.status_combo = ttk.Combobox(search_content, width=38, state='readonly')
        self.status_combo['values'] = ('Any', 'Available', 'Checked Out', 'Maintenance', 'Reserved')
        self.status_combo.current(0)
        self.status_combo.grid(row=2, column=1, sticky='ew', padx=10, pady=5)

        # Condition
        ttk.Label(search_content, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.condition', default="Condition:")).grid(row=3, column=0, sticky='w', pady=5)
        self.condition_combo = ttk.Combobox(search_content, width=38, state='readonly')
        self.condition_combo['values'] = condition_values
        self.condition_combo.current(0)
        self.condition_combo.grid(row=3, column=1, sticky='ew', padx=10, pady=5)

        ttk.Button(search_content, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.search', default="Search"), command=self.search, width=15).grid(row=4, column=1, sticky='e', padx=10, pady=10)

        search_content.columnconfigure(1, weight=1)

        # Results
        self.results_frame = ttk.LabelFrame(main_frame, text="Search Results")
        self.results_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Name', 'Category', 'Condition', 'Location', 'Status')
        self.tree = ttk.Treeview(self.results_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.tree.heading(col, text=col)
            if col == 'Name':
                self.tree.column(col, width=250)
            elif col == 'Category':
                self.tree.column(col, width=130)
            else:
                self.tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(self.results_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        self.tree.bind('<Double-1>', lambda e: self.view_details())

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.view_details', default="View Details"), command=self.view_details).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.check_out', default="Check Out"), command=self.checkout).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.save_search', default="Save Search"), command=self.save_search).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def search(self, announce=True):
        cat = _catalogue()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rows = {}
        try:
            conn = _open_conn()
            try:
                rows = cat.search(conn, keyword=self.search_entry.get(),
                                  category=self.category_combo.get(),
                                  status=cat.status_from_label(self.status_combo.get()),
                                  condition=self.condition_combo.get())
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.error', default="Error"), f"Search failed: {e}", parent=self.dialog)
            return
        for r in rows:
            iid = self.tree.insert('', 'end', values=(
                r['equipment_id'], r['name'], r['category'] or '', (r['condition'] or '').title(),
                r['location'] or '', cat.status_label(r['status'])))
            self._rows[iid] = r
        noun = "item" if len(rows) == 1 else "items"
        self.results_frame.config(text=f"Search Results ({len(rows)} {noun} found)")
        if announce and not rows:
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.search', default="Search"),
                                "No equipment matches these criteria.", parent=self.dialog)

    def _selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.warning', default="Warning"),
                                   "Please select an item of equipment first.", parent=self.dialog)
            return None
        return self._rows.get(selection[0])

    def view_details(self):
        row = self._selected()
        if row:
            dialog = ViewEquipmentDetailsDialog(self.dialog, self.auth, row['equipment_id'])
            self.dialog.wait_window(dialog.dialog)
            self.search(announce=False)

    def checkout(self):
        row = self._selected()
        if row and _open_checkout(self.dialog, self.auth, row['equipment_id'], row['name'], row['status']):
            self.search(announce=False)

    def save_search(self):
        try:
            conn = _open_conn()
            try:
                owner = _owner_id(conn, self.auth)
                _catalogue().save_search(conn, owner_id=owner, keyword=self.search_entry.get(),
                                         category=self.category_combo.get(),
                                         status=self.status_combo.get(),
                                         condition=self.condition_combo.get())
            finally:
                conn.close()
        except ValueError as e:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.save_search', default="Save Search"), str(e), parent=self.dialog)
            return
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.error', default="Error"), f"Failed to save search: {e}", parent=self.dialog)
            return
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.save_search', default="Save Search"),
                            "Search criteria saved to your account.", parent=self.dialog)


def open_browse_available_equipment_dialog(self):
    """Open browse available equipment"""
    dialog = BrowseAvailableEquipmentDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_view_equipment_details_dialog(self):
    """Open view equipment details"""
    dialog = ViewEquipmentDetailsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_search_equipment_dialog(self):
    """Open search equipment"""
    dialog = SearchEquipmentDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def create_equipment_tab(self):
    """Create equipment management tab"""
    equipment_frame = ttk.Frame(self.notebook)
    self.notebook.add(equipment_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.tabs.equipment', default="Equipment"))

    # Left panel
    left_panel = ttk.LabelFrame(equipment_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.equipment_actions', default="Equipment Actions"))
    left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)

    ttk.Button(left_panel, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.browse_equipment', default="Browse Equipment"),
              command=self.browse_available_equipment).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.check_out_equipment', default="Check Out Equipment"),
              command=self.check_out_equipment_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.return_equipment', default="Return Equipment"),
              command=self.return_equipment_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.my_checkouts', default="My Checkouts"),
              command=self.view_my_equipment_checkouts).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.buttons.search_equipment', default="Search Equipment"),
              command=self.search_equipment_gui).pack(fill='x', pady=2)

    # Right panel
    right_panel = ttk.LabelFrame(equipment_frame, text=_t('gui.pastoral.student_union_gui.equipment.equipment_browse.labels.equipment_information', default="Equipment Information"))
    right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)

    self.equipment_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD,
                                                   height=30, width=80)
    self.equipment_text.pack(fill='both', expand=True, padx=5, pady=5)


def browse_available_equipment(self):
    """Browse available equipment"""
    try:
        dialog = EquipmentBrowseDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.error', default="Error"), f"Failed to open dialog: {str(e)}")


def search_equipment_gui(self):
    """Search equipment"""
    try:
        dialog = EquipmentBrowseDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror(_t('gui.pastoral.student_union_gui.equipment.equipment_browse.dialogs.error', default="Error"), f"Failed to open dialog: {str(e)}")


