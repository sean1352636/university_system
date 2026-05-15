"""
Lab/Equipment Booking GUI

Provides interface for:
- Equipment browsing and search
- Booking management
- Maintenance scheduling
- Usage reports
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.equipment_manager import EquipmentManager
from education_system.university_system.modules.domain.staff_comms.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_combobox, show_validation_error
)


class EquipmentGUI:
    """GUI for lab equipment booking."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Equipment Booking")
            return

        # Cache categories and equipment lists for combobox use
        self._categories_cache = []
        self._equipment_cache = []

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Equipment")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Lab/Equipment Booking")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)
        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)
        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_browse_tab()
        self._create_my_bookings_tab()
        self._create_book_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_maintenance_tab()
            self._create_reports_tab()

    # ==================== HELPER METHODS ====================

    def _update_status(self, message: str):
        """Update status bar message."""
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.config(text=message)

    def _load_categories(self):
        """Load equipment categories from manager."""
        try:
            self._categories_cache = EquipmentManager.get_categories()
        except Exception:
            self._categories_cache = []
        return self._categories_cache

    def _get_category_names(self, include_all=True):
        """Return list of category names, optionally with 'All' prepended."""
        cats = self._load_categories()
        names = [c.get('name', '') for c in cats if c.get('name')]
        if include_all:
            names.insert(0, "All")
        return names

    def _get_category_id_by_name(self, name):
        """Look up category_id from cached categories by name."""
        for cat in self._categories_cache:
            if cat.get('name') == name:
                return cat.get('category_id')
        return None

    def _get_category_name_by_id(self, category_id):
        """Look up category name from cached categories by id."""
        for cat in self._categories_cache:
            if cat.get('category_id') == category_id:
                return cat.get('name', '')
        return ''

    def _load_all_equipment(self, category_id=None, status=None):
        """Load equipment list via manager."""
        try:
            self._equipment_cache = EquipmentManager.get_all_equipment(
                category_id=category_id, status=status
            )
        except Exception:
            self._equipment_cache = []
        return self._equipment_cache

    def _get_equipment_name_map(self, category_id=None):
        """Return dict of {display_name: equipment_id} for a given category."""
        items = self._load_all_equipment(category_id=category_id)
        name_map = {}
        for item in items:
            display = f"{item.get('name', '')} (ID: {item.get('equipment_id', '')})"
            name_map[display] = item.get('equipment_id')
        return name_map

    # ==================== TAB 1: BROWSE EQUIPMENT ====================

    def _create_browse_tab(self):
        """Create the Browse Equipment tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Browse Equipment")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Browse Equipment", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_browse_equipment).pack(side=tk.RIGHT, padx=5)

        # Filter frame
        filter_frame = ttk.LabelFrame(tab, text="Filters", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Category:").pack(side=tk.LEFT, padx=5)
        self.browse_category_filter = ttk.Combobox(
            filter_frame, values=self._get_category_names(include_all=True),
            width=20, state='readonly'
        )
        self.browse_category_filter.set("All")
        self.browse_category_filter.pack(side=tk.LEFT, padx=5)
        self.browse_category_filter.bind('<<ComboboxSelected>>', lambda e: self._load_browse_equipment())

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=15)
        self.browse_status_filter = ttk.Combobox(
            filter_frame,
            values=["All", "available", "maintenance", "retired"],
            width=15, state='readonly'
        )
        self.browse_status_filter.set("All")
        self.browse_status_filter.pack(side=tk.LEFT, padx=5)
        self.browse_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_browse_equipment())

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Name', 'Category', 'Location', 'Status', 'Approval Required')
        self.browse_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings',
            yscrollcommand=y_scroll.set
        )
        y_scroll.config(command=self.browse_tree.yview)

        col_widths = {'ID': 50, 'Name': 200, 'Category': 140, 'Location': 160,
                      'Status': 100, 'Approval Required': 120}
        for col in columns:
            self.browse_tree.heading(col, text=col)
            self.browse_tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)

        self.browse_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.browse_tree.tag_configure('available', background='#d4edda')
        self.browse_tree.tag_configure('maintenance', background='#fff3cd')
        self.browse_tree.tag_configure('retired', background='#e2e3e5')

        # Double-click to view details
        self.browse_tree.bind('<Double-1>', self._view_equipment_details)

        self._load_browse_equipment()

    def _load_browse_equipment(self):
        """Load equipment into the browse treeview."""
        try:
            self.browse_tree.delete(*self.browse_tree.get_children())

            # Determine filters
            cat_name = self.browse_category_filter.get()
            category_id = None
            if cat_name != "All":
                category_id = self._get_category_id_by_name(cat_name)

            status_val = self.browse_status_filter.get()
            status = None if status_val == "All" else status_val

            items = EquipmentManager.get_all_equipment(category_id=category_id, status=status)
            # Refresh categories cache
            self._load_categories()

            for item in items:
                cat_display = self._get_category_name_by_id(item.get('category_id')) or '-'
                location = item.get('location') or item.get('building', '') or '-'
                equip_status = item.get('status', 'available')
                approval = "Yes" if item.get('requires_approval') else "No"

                values = (
                    item.get('equipment_id', ''),
                    item.get('name', ''),
                    cat_display,
                    location,
                    equip_status.capitalize(),
                    approval,
                )
                tag = equip_status.lower()
                self.browse_tree.insert('', 'end', values=values, tags=(tag,))

            self._update_status(f"Loaded {len(items)} equipment items")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load equipment: {e}")

    def _view_equipment_details(self, event=None):
        """Open a detail Toplevel for the selected equipment item."""
        selection = self.browse_tree.selection()
        if not selection:
            return

        item = self.browse_tree.item(selection[0])
        equipment_id = item['values'][0]

        try:
            equip = EquipmentManager.get_equipment(equipment_id)
            if not equip:
                messagebox.showerror("Error", "Equipment not found")
                return

            # Fetch maintenance history
            maintenance_history = EquipmentManager.get_maintenance_history(equipment_id)
            self._load_categories()

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Equipment Details - {equip.get('name', '')}")
            dialog.geometry("600x550")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=equip.get('name', ''),
                      font=('Arial', 16, 'bold')).pack(anchor=tk.W, pady=(0, 15))

            # Details grid
            details_frame = ttk.LabelFrame(main_frame, text="Equipment Information", padding=10)
            details_frame.pack(fill=tk.X, pady=5)

            cat_display = self._get_category_name_by_id(equip.get('category_id')) or 'N/A'
            fields = [
                ("Equipment ID:", str(equip.get('equipment_id', ''))),
                ("Category:", cat_display),
                ("Location:", equip.get('location') or 'N/A'),
                ("Building:", equip.get('building') or 'N/A'),
                ("Room:", equip.get('room_number') or 'N/A'),
                ("Serial Number:", equip.get('serial_number') or 'N/A'),
                ("Model:", equip.get('model') or 'N/A'),
                ("Manufacturer:", equip.get('manufacturer') or 'N/A'),
                ("Status:", (equip.get('status') or 'available').capitalize()),
                ("Requires Approval:", "Yes" if equip.get('requires_approval') else "No"),
                ("Requires Training:", "Yes" if equip.get('requires_training') else "No"),
                ("Max Booking (hrs):", str(equip.get('max_booking_hours', 8))),
                ("Min Booking (hrs):", str(equip.get('min_booking_hours', 1))),
            ]

            for i, (label, value) in enumerate(fields):
                row_idx = i // 2
                col_offset = (i % 2) * 2
                ttk.Label(details_frame, text=label, font=('Arial', 9, 'bold')).grid(
                    row=row_idx, column=col_offset, sticky='e', padx=5, pady=2)
                ttk.Label(details_frame, text=value).grid(
                    row=row_idx, column=col_offset + 1, sticky='w', padx=5, pady=2)

            # Description
            desc = equip.get('description') or 'No description provided'
            desc_frame = ttk.LabelFrame(main_frame, text="Description", padding=10)
            desc_frame.pack(fill=tk.X, pady=5)
            ttk.Label(desc_frame, text=desc, wraplength=540, anchor=tk.W, justify=tk.LEFT).pack(
                fill=tk.X)

            # Maintenance history
            maint_frame = ttk.LabelFrame(main_frame, text="Maintenance History", padding=10)
            maint_frame.pack(fill=tk.BOTH, expand=True, pady=5)

            maint_columns = ('ID', 'Type', 'Scheduled', 'Completed', 'Status')
            maint_tree = ttk.Treeview(maint_frame, columns=maint_columns,
                                      show='headings', height=5)
            for col in maint_columns:
                maint_tree.heading(col, text=col)
                maint_tree.column(col, width=100, anchor=tk.CENTER)

            maint_tree.pack(fill=tk.BOTH, expand=True)

            for m in maintenance_history:
                scheduled = (m.get('scheduled_date') or '-')[:10]
                completed = (m.get('completed_date') or '-')[:10]
                maint_tree.insert('', 'end', values=(
                    m.get('maintenance_id', ''),
                    (m.get('maintenance_type') or '-').capitalize(),
                    scheduled,
                    completed,
                    (m.get('status') or '-').capitalize(),
                ))

            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load equipment details: {e}")

    # ==================== TAB 2: MY BOOKINGS ====================

    def _create_my_bookings_tab(self):
        """Create the My Bookings tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Bookings")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Bookings", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_my_bookings).pack(side=tk.RIGHT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Equipment', 'Date', 'Time', 'Status', 'Checked In', 'Checked Out')
        self.bookings_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings',
            yscrollcommand=y_scroll.set
        )
        y_scroll.config(command=self.bookings_tree.yview)

        col_widths = {'ID': 50, 'Equipment': 200, 'Date': 100, 'Time': 130,
                      'Status': 90, 'Checked In': 140, 'Checked Out': 140}
        for col in columns:
            self.bookings_tree.heading(col, text=col)
            self.bookings_tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)

        self.bookings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.bookings_tree.tag_configure('pending', background='#fff3cd')
        self.bookings_tree.tag_configure('approved', background='#d4edda')
        self.bookings_tree.tag_configure('rejected', background='#f8d7da')
        self.bookings_tree.tag_configure('cancelled', background='#e2e3e5')

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Cancel Booking", command=self._cancel_selected_booking).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Check In", command=self._check_in_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Check Out", command=self._check_out_selected).pack(side=tk.LEFT, padx=5)

        self._load_my_bookings()

    def _load_my_bookings(self):
        """Load current user's bookings into the treeview."""
        try:
            self.bookings_tree.delete(*self.bookings_tree.get_children())

            user_id = self._get_user_id()
            bookings = EquipmentManager.get_user_bookings(user_id)

            # Build an equipment name cache for display
            equip_names = {}
            for b in bookings:
                eid = b.get('equipment_id')
                if eid and eid not in equip_names:
                    try:
                        eq = EquipmentManager.get_equipment(eid)
                        equip_names[eid] = eq.get('name', str(eid)) if eq else str(eid)
                    except Exception:
                        equip_names[eid] = str(eid)

            for b in bookings:
                booking_id = b.get('booking_id', '')
                equip_name = equip_names.get(b.get('equipment_id'), '-')
                booking_date = (b.get('booking_date') or '-')[:10]
                start_time = b.get('start_time') or ''
                end_time = b.get('end_time') or ''
                time_display = f"{start_time} - {end_time}" if start_time and end_time else '-'
                status = b.get('status', 'pending')
                checked_in = (b.get('checked_in_at') or '-')[:19]
                checked_out = (b.get('checked_out_at') or '-')[:19]

                values = (booking_id, equip_name, booking_date, time_display,
                          status.capitalize(), checked_in, checked_out)
                self.bookings_tree.insert('', 'end', values=values, tags=(status,))

            self._update_status(f"Loaded {len(bookings)} bookings")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load bookings: {e}")

    def _get_selected_booking(self):
        """Get the selected booking ID and status from the bookings treeview."""
        selection = self.bookings_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a booking first")
            return None, None
        item = self.bookings_tree.item(selection[0])
        booking_id = item['values'][0]
        status = item['values'][4].lower()
        return booking_id, status

    def _cancel_selected_booking(self):
        """Cancel the selected booking."""
        booking_id, status = self._get_selected_booking()
        if booking_id is None:
            return

        if status not in ('pending', 'approved'):
            messagebox.showwarning("Warning", "Only pending or approved bookings can be cancelled")
            return

        if not messagebox.askyesno("Confirm", "Are you sure you want to cancel this booking?"):
            return

        try:
            EquipmentManager.cancel_booking(booking_id)
            messagebox.showinfo("Success", "Booking cancelled successfully")
            self._load_my_bookings()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to cancel booking: {e}")

    def _check_in_selected(self):
        """Check in for the selected booking."""
        booking_id, status = self._get_selected_booking()
        if booking_id is None:
            return

        if status != 'approved':
            messagebox.showwarning("Warning", "Only approved bookings can be checked in")
            return

        try:
            EquipmentManager.check_in(booking_id)
            messagebox.showinfo("Success", "Checked in successfully")
            self._load_my_bookings()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check in: {e}")

    def _check_out_selected(self):
        """Check out from the selected booking."""
        booking_id, status = self._get_selected_booking()
        if booking_id is None:
            return

        # Check that the booking has been checked in
        item = self.bookings_tree.item(self.bookings_tree.selection()[0])
        checked_in_val = item['values'][5]
        if checked_in_val == '-':
            messagebox.showwarning("Warning", "You must check in before checking out")
            return

        checked_out_val = item['values'][6]
        if checked_out_val != '-':
            messagebox.showwarning("Warning", "Already checked out")
            return

        try:
            EquipmentManager.check_out(booking_id)
            messagebox.showinfo("Success", "Checked out successfully")
            self._load_my_bookings()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check out: {e}")

    # ==================== TAB 3: BOOK EQUIPMENT ====================

    def _create_book_tab(self):
        """Create the Book Equipment tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Book Equipment")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Book Equipment", style='Header.TLabel').pack(side=tk.LEFT)

        # Form frame
        form_frame = ttk.LabelFrame(tab, text="Booking Details", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=5)

        # Equipment selector: Category filters Equipment
        row1 = ttk.Frame(form_frame)
        row1.pack(fill=tk.X, pady=5)
        ttk.Label(row1, text="Category:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.book_category_combo = ttk.Combobox(
            row1, values=self._get_category_names(include_all=False),
            width=25, state='readonly'
        )
        self.book_category_combo.pack(side=tk.LEFT, padx=5)
        self.book_category_combo.bind('<<ComboboxSelected>>', self._on_book_category_changed)

        row2 = ttk.Frame(form_frame)
        row2.pack(fill=tk.X, pady=5)
        ttk.Label(row2, text="Equipment:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.book_equipment_combo = ttk.Combobox(row2, width=35, state='readonly')
        self.book_equipment_combo.pack(side=tk.LEFT, padx=5)
        # Store the mapping of display name -> equipment_id
        self._book_equipment_map = {}

        # Date entry
        row3 = ttk.Frame(form_frame)
        row3.pack(fill=tk.X, pady=5)
        ttk.Label(row3, text="Date:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.book_date_entry = ttk.Entry(row3, width=15)
        self.book_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.book_date_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row3, text="(YYYY-MM-DD)", font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Start Time entry
        row4 = ttk.Frame(form_frame)
        row4.pack(fill=tk.X, pady=5)
        ttk.Label(row4, text="Start Time:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.book_start_time_entry = ttk.Entry(row4, width=10)
        self.book_start_time_entry.insert(0, "09:00")
        self.book_start_time_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row4, text="(HH:MM)", font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # End Time entry
        row5 = ttk.Frame(form_frame)
        row5.pack(fill=tk.X, pady=5)
        ttk.Label(row5, text="End Time:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.book_end_time_entry = ttk.Entry(row5, width=10)
        self.book_end_time_entry.insert(0, "10:00")
        self.book_end_time_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row5, text="(HH:MM)", font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Purpose
        row6 = ttk.Frame(form_frame)
        row6.pack(fill=tk.X, pady=5)
        ttk.Label(row6, text="Purpose:", width=15, anchor=tk.W).pack(side=tk.LEFT, anchor=tk.N)
        self.book_purpose_text = tk.Text(row6, height=3, width=40)
        self.book_purpose_text.pack(side=tk.LEFT, padx=5)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Check Availability",
                   command=self._check_availability).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Submit Booking",
                   command=self._submit_booking).pack(side=tk.LEFT, padx=5)

        # Availability display
        avail_frame = ttk.LabelFrame(tab, text="Existing Bookings for Selected Date", padding=10)
        avail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        avail_columns = ('ID', 'User', 'Start', 'End', 'Status')
        self.avail_tree = ttk.Treeview(avail_frame, columns=avail_columns,
                                       show='headings', height=6)
        for col in avail_columns:
            self.avail_tree.heading(col, text=col)
            self.avail_tree.column(col, width=120, anchor=tk.CENTER)

        self.avail_tree.pack(fill=tk.BOTH, expand=True)

    def _on_book_category_changed(self, event=None):
        """When a category is selected in the Book tab, update the equipment combobox."""
        cat_name = self.book_category_combo.get()
        category_id = self._get_category_id_by_name(cat_name)
        self._book_equipment_map = self._get_equipment_name_map(category_id=category_id)
        self.book_equipment_combo['values'] = list(self._book_equipment_map.keys())
        self.book_equipment_combo.set('')

    def _get_selected_book_equipment_id(self):
        """Get the equipment_id for the currently selected equipment in the Book tab."""
        selection = self.book_equipment_combo.get()
        if not selection:
            return None
        return self._book_equipment_map.get(selection)

    def _validate_time_format(self, time_str):
        """Validate HH:MM time format and return the string or raise ValidationError."""
        time_str = time_str.strip()
        if not time_str:
            raise ValidationError("Time is required.")
        try:
            datetime.strptime(time_str, "%H:%M")
        except ValueError:
            raise ValidationError(f"'{time_str}' is not a valid time. Use HH:MM format.")
        return time_str

    def _check_availability(self):
        """Check and display existing bookings for the selected equipment and date."""
        equipment_id = self._get_selected_book_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Warning", "Please select an equipment item first")
            return

        try:
            date_val = validate_date_entry(self.book_date_entry, "Date")
        except ValidationError as e:
            show_validation_error(e)
            return

        try:
            bookings = EquipmentManager.get_equipment_bookings(equipment_id, date=date_val)

            self.avail_tree.delete(*self.avail_tree.get_children())

            if not bookings:
                self.avail_tree.insert('', 'end', values=('-', '-', '-', '-', 'No bookings'))
            else:
                for b in bookings:
                    self.avail_tree.insert('', 'end', values=(
                        b.get('booking_id', ''),
                        b.get('user_id', ''),
                        b.get('start_time', ''),
                        b.get('end_time', ''),
                        (b.get('status') or '').capitalize(),
                    ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check availability: {e}")

    def _submit_booking(self):
        """Submit a new equipment booking."""
        equipment_id = self._get_selected_book_equipment_id()
        if not equipment_id:
            messagebox.showwarning("Warning", "Please select a category and equipment item")
            return

        # Validate inputs
        try:
            date_val = validate_date_entry(self.book_date_entry, "Date")
        except ValidationError as e:
            show_validation_error(e)
            return

        try:
            start_time = self._validate_time_format(self.book_start_time_entry.get())
        except ValidationError as e:
            show_validation_error(e)
            return

        try:
            end_time = self._validate_time_format(self.book_end_time_entry.get())
        except ValidationError as e:
            show_validation_error(e)
            return

        if end_time <= start_time:
            messagebox.showerror("Validation Error", "End time must be after start time")
            return

        purpose = self.book_purpose_text.get("1.0", "end-1c").strip() or None

        user_id = self._get_user_id()

        try:
            booking_id = EquipmentManager.create_booking(
                equipment_id=equipment_id,
                user_id=user_id,
                booking_date=date_val,
                start_time=start_time,
                end_time=end_time,
                purpose=purpose,
            )
            messagebox.showinfo("Success",
                                f"Booking created successfully (ID: {booking_id})")
            # Clear purpose
            self.book_purpose_text.delete("1.0", "end")
            # Refresh availability display
            self._check_availability()
            # Refresh my bookings if the tab exists
            if hasattr(self, 'bookings_tree'):
                self._load_my_bookings()

        except ValueError as e:
            messagebox.showerror("Booking Conflict", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create booking: {e}")

    # ==================== TAB 4: MAINTENANCE (ADMIN) ====================

    def _create_maintenance_tab(self):
        """Create the Maintenance tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Maintenance")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Equipment Maintenance", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_maintenance).pack(side=tk.RIGHT, padx=5)

        # Equipment selector for filtering
        filter_frame = ttk.LabelFrame(tab, text="Filter", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Equipment:").pack(side=tk.LEFT, padx=5)
        self._maint_equipment_map = {}
        self.maint_equipment_combo = ttk.Combobox(filter_frame, width=35, state='readonly')
        self.maint_equipment_combo.pack(side=tk.LEFT, padx=5)
        self.maint_equipment_combo.bind('<<ComboboxSelected>>', lambda e: self._load_maintenance())
        self._refresh_maint_equipment_list()

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Equipment', 'Type', 'Scheduled', 'Completed', 'Status')
        self.maint_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings',
            yscrollcommand=y_scroll.set
        )
        y_scroll.config(command=self.maint_tree.yview)

        col_widths = {'ID': 50, 'Equipment': 200, 'Type': 100,
                      'Scheduled': 120, 'Completed': 120, 'Status': 100}
        for col in columns:
            self.maint_tree.heading(col, text=col)
            self.maint_tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)

        self.maint_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.maint_tree.tag_configure('scheduled', background='#fff3cd')
        self.maint_tree.tag_configure('completed', background='#d4edda')

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Schedule Maintenance",
                   command=self._show_schedule_maintenance_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Complete",
                   command=self._complete_selected_maintenance).pack(side=tk.LEFT, padx=5)

        self._load_maintenance()

    def _refresh_maint_equipment_list(self):
        """Refresh the equipment list for the maintenance filter combobox."""
        all_name_map = self._get_equipment_name_map(category_id=None)
        all_name_map_with_all = {"All": None}
        all_name_map_with_all.update(all_name_map)
        self._maint_equipment_map = all_name_map_with_all
        self.maint_equipment_combo['values'] = list(self._maint_equipment_map.keys())
        self.maint_equipment_combo.set("All")

    def _load_maintenance(self):
        """Load maintenance records into the treeview."""
        try:
            self.maint_tree.delete(*self.maint_tree.get_children())

            selected = self.maint_equipment_combo.get()
            equipment_id = self._maint_equipment_map.get(selected)

            # Build equipment name lookup
            self._load_categories()
            all_equipment = EquipmentManager.get_all_equipment()
            equip_name_lookup = {e.get('equipment_id'): e.get('name', '') for e in all_equipment}

            if equipment_id:
                # Show maintenance for a specific piece of equipment
                records = EquipmentManager.get_maintenance_history(equipment_id)
            else:
                # Show all maintenance records - iterate all equipment
                records = []
                for eq in all_equipment:
                    try:
                        hist = EquipmentManager.get_maintenance_history(eq['equipment_id'])
                        records.extend(hist)
                    except Exception:
                        pass
                # Sort by scheduled_date descending
                records.sort(key=lambda r: r.get('scheduled_date') or '', reverse=True)

            for m in records:
                eid = m.get('equipment_id', '')
                equip_name = equip_name_lookup.get(eid, str(eid))
                scheduled = (m.get('scheduled_date') or '-')[:10]
                completed = (m.get('completed_date') or '-')[:10]
                maint_status = m.get('status', 'scheduled')

                values = (
                    m.get('maintenance_id', ''),
                    equip_name,
                    (m.get('maintenance_type') or '-').capitalize(),
                    scheduled,
                    completed,
                    maint_status.capitalize(),
                )
                self.maint_tree.insert('', 'end', values=values, tags=(maint_status,))

            self._update_status(f"Loaded {len(records)} maintenance records")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load maintenance records: {e}")

    def _show_schedule_maintenance_dialog(self):
        """Show a dialog to schedule new maintenance."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Schedule Maintenance")
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Schedule Equipment Maintenance",
                  font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Equipment selector
        row1 = ttk.Frame(main_frame)
        row1.pack(fill=tk.X, pady=5)
        ttk.Label(row1, text="Equipment:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        sched_equip_map = self._get_equipment_name_map(category_id=None)
        sched_equip_combo = ttk.Combobox(row1, values=list(sched_equip_map.keys()),
                                         width=30, state='readonly')
        sched_equip_combo.pack(side=tk.LEFT, padx=5)

        # Maintenance type
        row2 = ttk.Frame(main_frame)
        row2.pack(fill=tk.X, pady=5)
        ttk.Label(row2, text="Type:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        type_combo = ttk.Combobox(row2, values=['routine', 'repair', 'calibration'],
                                  width=20, state='readonly')
        type_combo.set('routine')
        type_combo.pack(side=tk.LEFT, padx=5)

        # Description
        row3 = ttk.Frame(main_frame)
        row3.pack(fill=tk.X, pady=5)
        ttk.Label(row3, text="Description:", width=15, anchor=tk.W).pack(side=tk.LEFT, anchor=tk.N)
        desc_text = tk.Text(row3, height=3, width=35)
        desc_text.pack(side=tk.LEFT, padx=5)

        # Scheduled date
        row4 = ttk.Frame(main_frame)
        row4.pack(fill=tk.X, pady=5)
        ttk.Label(row4, text="Scheduled Date:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        date_entry = ttk.Entry(row4, width=15)
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        date_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row4, text="(YYYY-MM-DD)", font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Cost
        row5 = ttk.Frame(main_frame)
        row5.pack(fill=tk.X, pady=5)
        ttk.Label(row5, text="Est. Cost:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        cost_entry = ttk.Entry(row5, width=12)
        cost_entry.insert(0, "0.00")
        cost_entry.pack(side=tk.LEFT, padx=5)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save():
            equip_sel = sched_equip_combo.get()
            if not equip_sel:
                error_label.config(text="Please select an equipment item")
                return

            eid = sched_equip_map.get(equip_sel)
            if not eid:
                error_label.config(text="Invalid equipment selection")
                return

            maint_type = type_combo.get()
            if not maint_type:
                error_label.config(text="Please select a maintenance type")
                return

            try:
                sched_date = validate_date_entry(date_entry, "Scheduled Date")
            except ValidationError as e:
                error_label.config(text=str(e))
                return

            description = desc_text.get("1.0", "end-1c").strip() or None

            try:
                cost = float(cost_entry.get().strip() or '0')
            except ValueError:
                error_label.config(text="Cost must be a valid number")
                return

            try:
                maintenance_id = EquipmentManager.schedule_maintenance(
                    equipment_id=eid,
                    maintenance_type=maint_type,
                    description=description,
                    scheduled_date=sched_date,
                    cost=cost,
                )
                messagebox.showinfo("Success",
                                    f"Maintenance scheduled (ID: {maintenance_id})")
                dialog.destroy()
                self._load_maintenance()
                # Also refresh browse since equipment status changes
                if hasattr(self, 'browse_tree'):
                    self._load_browse_equipment()
            except Exception as e:
                error_label.config(text=f"Error: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Schedule", command=save).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _complete_selected_maintenance(self):
        """Mark the selected maintenance record as complete."""
        selection = self.maint_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a maintenance record")
            return

        item = self.maint_tree.item(selection[0])
        maintenance_id = item['values'][0]
        maint_status = item['values'][5].lower()

        if maint_status == 'completed':
            messagebox.showwarning("Warning", "This maintenance is already completed")
            return

        if not messagebox.askyesno("Confirm", "Mark this maintenance as completed?"):
            return

        performed_by = self.current_user.get('username') or self._get_user_id()

        try:
            EquipmentManager.complete_maintenance(
                maintenance_id=maintenance_id,
                performed_by=performed_by,
            )
            messagebox.showinfo("Success", "Maintenance marked as completed")
            self._load_maintenance()
            # Also refresh browse since equipment status changes
            if hasattr(self, 'browse_tree'):
                self._load_browse_equipment()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to complete maintenance: {e}")

    # ==================== TAB 5: REPORTS (ADMIN) ====================

    def _create_reports_tab(self):
        """Create the Reports tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reports")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Equipment Usage Reports", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_reports).pack(side=tk.RIGHT, padx=5)

        # Summary frame
        summary_frame = ttk.LabelFrame(tab, text="Usage Statistics", padding=15)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        self.report_total_label = ttk.Label(summary_frame, text="Total Bookings: 0",
                                            font=('Arial', 11))
        self.report_total_label.pack(side=tk.LEFT, padx=20)

        self.report_approved_label = ttk.Label(summary_frame, text="Approved: 0",
                                               font=('Arial', 11), foreground='green')
        self.report_approved_label.pack(side=tk.LEFT, padx=20)

        self.report_rejected_label = ttk.Label(summary_frame, text="Rejected: 0",
                                               font=('Arial', 11), foreground='red')
        self.report_rejected_label.pack(side=tk.LEFT, padx=20)

        self.report_pending_label = ttk.Label(summary_frame, text="Pending: 0",
                                              font=('Arial', 11), foreground='orange')
        self.report_pending_label.pack(side=tk.LEFT, padx=20)

        self.report_cancelled_label = ttk.Label(summary_frame, text="Cancelled: 0",
                                                font=('Arial', 11), foreground='gray')
        self.report_cancelled_label.pack(side=tk.LEFT, padx=20)

        # Utilization treeview
        util_frame = ttk.LabelFrame(tab, text="Equipment Utilization", padding=10)
        util_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        util_columns = ('Equipment Name', 'Total Bookings', 'Utilization')
        self.util_tree = ttk.Treeview(util_frame, columns=util_columns,
                                      show='headings')

        col_widths = {'Equipment Name': 300, 'Total Bookings': 150, 'Utilization': 150}
        for col in util_columns:
            self.util_tree.heading(col, text=col)
            self.util_tree.column(col, width=col_widths.get(col, 150), anchor=tk.CENTER)

        y_scroll = ttk.Scrollbar(util_frame, orient=tk.VERTICAL, command=self.util_tree.yview)
        self.util_tree.configure(yscrollcommand=y_scroll.set)
        self.util_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_reports()

    def _load_reports(self):
        """Load usage statistics and populate the reports tab."""
        try:
            stats = EquipmentManager.get_usage_statistics()

            total = stats.get('total_bookings', 0)
            by_status = stats.get('by_status', {})
            approved = by_status.get('approved', 0)
            rejected = by_status.get('rejected', 0)
            pending = by_status.get('pending', 0)
            cancelled = by_status.get('cancelled', 0)

            self.report_total_label.config(text=f"Total Bookings: {total}")
            self.report_approved_label.config(text=f"Approved: {approved}")
            self.report_rejected_label.config(text=f"Rejected: {rejected}")
            self.report_pending_label.config(text=f"Pending: {pending}")
            self.report_cancelled_label.config(text=f"Cancelled: {cancelled}")

            # Utilization treeview
            self.util_tree.delete(*self.util_tree.get_children())

            utilization = stats.get('utilization', [])
            max_bookings = max((u.get('booking_count', 0) for u in utilization), default=1)
            if max_bookings == 0:
                max_bookings = 1

            for u in utilization:
                name = u.get('name', 'Unknown')
                count = u.get('booking_count', 0)
                pct = (count / max_bookings) * 100
                utilization_display = f"{pct:.1f}%"

                self.util_tree.insert('', 'end', values=(name, count, utilization_display))

            self._update_status(f"Reports loaded - {total} total bookings")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load reports: {e}")


def launch_equipment_gui(root, auth):
    """Launch Lab/Equipment Booking GUI."""
    try:
        return EquipmentGUI(root, auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Equipment GUI: {e}")
        return None
