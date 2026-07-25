"""
Shifts Management GUI

Manages employee shifts, scheduling, and time tracking for payroll.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
import calendar

# Import database connection
from education_system.systems.university.interfaces.gui.operations.commerce.restaurant_management_gui.core.main_gui import get_db_connection

# Import translation function
from education_system.systems.university.infrastructure.i18n import get_text as get_translation
_t = get_translation


def init_shifts_tables():
    """Initialize shifts and related tables"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Ensure restaurant_staff table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_staff (
                staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                position TEXT,
                hourly_rate REAL,
                email TEXT,
                phone TEXT,
                hire_date DATE,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create shifts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_shifts (
                shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL,
                shift_date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME,
                break_minutes INTEGER DEFAULT 0,
                hours_worked REAL,
                hourly_rate REAL,
                total_pay REAL,
                status TEXT DEFAULT 'Scheduled',
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (staff_id) REFERENCES restaurant_staff(staff_id)
            )
        ''')

        # Create shift swaps table (for schedule management)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_shift_swaps (
                swap_id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_shift_id INTEGER NOT NULL,
                requesting_staff_id INTEGER NOT NULL,
                covering_staff_id INTEGER,
                swap_date DATE NOT NULL,
                status TEXT DEFAULT 'Pending',
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (original_shift_id) REFERENCES restaurant_shifts(shift_id),
                FOREIGN KEY (requesting_staff_id) REFERENCES restaurant_staff(staff_id),
                FOREIGN KEY (covering_staff_id) REFERENCES restaurant_staff(staff_id)
            )
        ''')

        conn.commit()
        conn.close()
        print(_t("shifts.init_success", default="✓ Shifts tables initialized successfully"))
        return True

    except Exception as e:
        print(_t("shifts.init_error", default="✗ Error initializing shifts tables: {error}").format(error=e))
        return False


class ShiftsManagementGUI:
    """GUI for managing employee shifts"""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title(_t("shifts.window_title", default="Shifts Management & Scheduling"))
        self.window.geometry("1400x800")

        # Initialize tables
        init_shifts_tables()

        self.create_widgets()
        self.load_staff()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main notebook
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Shifts Tab
        shifts_tab = ttk.Frame(notebook)
        notebook.add(shifts_tab, text=_t("shifts.tabs.shifts", default="Shifts"))
        self.create_shifts_tab(shifts_tab)

        # Staff Tab
        staff_tab = ttk.Frame(notebook)
        notebook.add(staff_tab, text=_t("shifts.tabs.staff", default="Staff"))
        self.create_staff_tab(staff_tab)

        # Schedule Tab
        schedule_tab = ttk.Frame(notebook)
        notebook.add(schedule_tab, text=_t("shifts.tabs.weekly_schedule", default="Weekly Schedule"))
        self.create_schedule_tab(schedule_tab)

    def create_shifts_tab(self, parent):
        """Create shifts tab"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("shifts.shifts_tab.header", default="Shifts Management"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_t("shifts.shifts_tab.add_shift_button", default="Add Shift"),
                  command=self.add_shift).pack(side=tk.RIGHT, padx=5)

        # Filters
        filter_frame = ttk.LabelFrame(parent, text=_t("shifts.shifts_tab.filters_label", default="Filters"), padding="10")
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("shifts.shifts_tab.date_range_label", default="Date Range:")).grid(row=0, column=0, padx=5)
        self.start_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=self.start_date_var, width=12).grid(row=0, column=1, padx=5)

        ttk.Label(filter_frame, text=_t("shifts.shifts_tab.to_label", default="to")).grid(row=0, column=2, padx=5)
        end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        self.end_date_var = tk.StringVar(value=end_date)
        ttk.Entry(filter_frame, textvariable=self.end_date_var, width=12).grid(row=0, column=3, padx=5)

        ttk.Label(filter_frame, text=_t("shifts.shifts_tab.staff_label", default="Staff:")).grid(row=0, column=4, padx=5)
        self.staff_filter = ttk.Combobox(filter_frame, width=20)
        self.staff_filter.set(_t("shifts.shifts_tab.all", default="All"))
        self.staff_filter.grid(row=0, column=5, padx=5)

        ttk.Label(filter_frame, text=_t("shifts.shifts_tab.status_label", default="Status:")).grid(row=0, column=6, padx=5)
        self.status_filter = ttk.Combobox(filter_frame, width=15,
                                         values=[
                                             _t("shifts.statuses.all", default="All"),
                                             _t("shifts.statuses.scheduled", default="Scheduled"),
                                             _t("shifts.statuses.in_progress", default="In Progress"),
                                             _t("shifts.statuses.completed", default="Completed"),
                                             _t("shifts.statuses.cancelled", default="Cancelled")
                                         ])
        self.status_filter.set(_t("shifts.statuses.all", default="All"))
        self.status_filter.grid(row=0, column=7, padx=5)

        ttk.Button(filter_frame, text=_t("shifts.shifts_tab.search_button", default="Search"),
                  command=self.load_shifts).grid(row=0, column=8, padx=10)

        # Shifts List
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('staff_name', 'date', 'start_time', 'end_time', 'hours',
                  'rate', 'total_pay', 'status')
        self.shifts_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.shifts_tree.heading('staff_name', text=_t("shifts.columns.staff_name", default="Staff Name"))
        self.shifts_tree.heading('date', text=_t("shifts.columns.date", default="Date"))
        self.shifts_tree.heading('start_time', text=_t("shifts.columns.start_time", default="Start Time"))
        self.shifts_tree.heading('end_time', text=_t("shifts.columns.end_time", default="End Time"))
        self.shifts_tree.heading('hours', text=_t("shifts.columns.hours", default="Hours"))
        self.shifts_tree.heading('rate', text=_t("shifts.columns.rate", default="Rate/Hr"))
        self.shifts_tree.heading('total_pay', text=_t("shifts.columns.total_pay", default="Total Pay"))
        self.shifts_tree.heading('status', text=_t("shifts.columns.status", default="Status"))

        self.shifts_tree.column('staff_name', width=150)
        self.shifts_tree.column('date', width=100)
        self.shifts_tree.column('start_time', width=100)
        self.shifts_tree.column('end_time', width=100)
        self.shifts_tree.column('hours', width=80)
        self.shifts_tree.column('rate', width=80)
        self.shifts_tree.column('total_pay', width=100)
        self.shifts_tree.column('status', width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.shifts_tree.yview)
        self.shifts_tree.configure(yscrollcommand=scrollbar.set)

        self.shifts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text=_t("shifts.shifts_tab.clock_in_button", default="Clock In"),
                  command=self.clock_in).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("shifts.shifts_tab.clock_out_button", default="Clock Out"),
                  command=self.clock_out).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("shifts.shifts_tab.edit_shift_button", default="Edit Shift"),
                  command=self.edit_shift).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("shifts.shifts_tab.delete_shift_button", default="Delete Shift"),
                  command=self.delete_shift).pack(side=tk.LEFT, padx=5)

        # Load shifts
        self.load_shifts()

    def create_staff_tab(self, parent):
        """Create staff management tab"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("shifts.staff_tab.header", default="Staff Members"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_t("shifts.staff_tab.add_staff_button", default="Add Staff"),
                  command=self.add_staff).pack(side=tk.RIGHT, padx=5)

        # Staff List
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('name', 'position', 'hourly_rate', 'email', 'phone', 'hire_date', 'is_active')
        self.staff_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)

        self.staff_tree.heading('name', text=_t("shifts.columns.name", default="Name"))
        self.staff_tree.heading('position', text=_t("shifts.columns.position", default="Position"))
        self.staff_tree.heading('hourly_rate', text=_t("shifts.columns.hourly_rate", default="Hourly Rate"))
        self.staff_tree.heading('email', text=_t("shifts.columns.email", default="Email"))
        self.staff_tree.heading('phone', text=_t("shifts.columns.phone", default="Phone"))
        self.staff_tree.heading('hire_date', text=_t("shifts.columns.hire_date", default="Hire Date"))
        self.staff_tree.heading('is_active', text=_t("shifts.columns.is_active", default="Status"))

        self.staff_tree.column('name', width=150)
        self.staff_tree.column('position', width=120)
        self.staff_tree.column('hourly_rate', width=100)
        self.staff_tree.column('email', width=200)
        self.staff_tree.column('phone', width=120)
        self.staff_tree.column('hire_date', width=100)
        self.staff_tree.column('is_active', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.staff_tree.yview)
        self.staff_tree.configure(yscrollcommand=scrollbar.set)

        self.staff_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text=_t("shifts.staff_tab.edit_staff_button", default="Edit Staff"),
                  command=self.edit_staff).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("shifts.staff_tab.toggle_status_button", default="Toggle Active/Inactive"),
                  command=self.toggle_staff_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("shifts.staff_tab.delete_button", default="Delete"),
                  command=self.delete_staff).pack(side=tk.LEFT, padx=5)

    def create_schedule_tab(self, parent):
        """Create weekly schedule tab"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("shifts.schedule_tab.header", default="Weekly Schedule"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        # Week selector
        week_frame = ttk.Frame(header_frame)
        week_frame.pack(side=tk.RIGHT)

        ttk.Button(week_frame, text=_t("shifts.schedule_tab.previous_week_button", default="◄ Previous Week"),
                  command=self.previous_week).pack(side=tk.LEFT, padx=5)

        self.week_label = ttk.Label(week_frame, text=_t("shifts.schedule_tab.week_of_label", default="Week of: "), font=('Arial', 10, 'bold'))
        self.week_label.pack(side=tk.LEFT, padx=10)

        ttk.Button(week_frame, text=_t("shifts.schedule_tab.next_week_button", default="Next Week ►"),
                  command=self.next_week).pack(side=tk.LEFT, padx=5)

        # Schedule grid frame
        self.schedule_frame = ttk.Frame(parent)
        self.schedule_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Current week start
        today = datetime.now()
        self.current_week_start = today - timedelta(days=today.weekday())

        self.display_weekly_schedule()

    def display_weekly_schedule(self):
        """Display weekly schedule grid"""
        # Clear existing widgets
        for widget in self.schedule_frame.winfo_children():
            widget.destroy()

        # Update week label
        week_end = self.current_week_start + timedelta(days=6)
        self.week_label.config(text=_t("shifts.schedule_tab.week_range",
                                      default="Week of: {start} to {end}").format(
                                          start=self.current_week_start.strftime('%Y-%m-%d'),
                                          end=week_end.strftime('%Y-%m-%d')))

        # Create grid
        days = [
            _t("shifts.days_of_week.monday", default="Monday"),
            _t("shifts.days_of_week.tuesday", default="Tuesday"),
            _t("shifts.days_of_week.wednesday", default="Wednesday"),
            _t("shifts.days_of_week.thursday", default="Thursday"),
            _t("shifts.days_of_week.friday", default="Friday"),
            _t("shifts.days_of_week.saturday", default="Saturday"),
            _t("shifts.days_of_week.sunday", default="Sunday")
        ]

        # Headers
        for col, day in enumerate(days):
            date = self.current_week_start + timedelta(days=col)
            header_text = f"{day}\n{date.strftime('%m/%d')}"
            ttk.Label(self.schedule_frame, text=header_text,
                     font=('Arial', 10, 'bold'), relief=tk.RIDGE, padding=5).grid(
                row=0, column=col, sticky='ew', padx=1, pady=1)

        # Load shifts for the week
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            week_end_str = week_end.strftime('%Y-%m-%d')
            week_start_str = self.current_week_start.strftime('%Y-%m-%d')

            cursor.execute('''
                SELECT s.name, sh.shift_date, sh.start_time, sh.end_time, sh.status
                FROM restaurant_shifts sh
                JOIN restaurant_staff s ON sh.staff_id = s.staff_id
                WHERE sh.shift_date BETWEEN ? AND ?
                ORDER BY sh.shift_date, sh.start_time
            ''', (week_start_str, week_end_str))

            shifts_by_day = {i: [] for i in range(7)}
            for row in cursor.fetchall():
                staff_name, shift_date, start_time, end_time, status = row
                shift_datetime = datetime.strptime(shift_date, '%Y-%m-%d')
                day_index = (shift_datetime - self.current_week_start).days

                if 0 <= day_index < 7:
                    shifts_by_day[day_index].append({
                        'name': staff_name,
                        'start': start_time,
                        'end': end_time or _t("shifts.schedule_tab.in_progress", default="In Progress"),
                        'status': status
                    })

            conn.close()

            # Display shifts in grid
            max_shifts = max(len(shifts) for shifts in shifts_by_day.values()) if shifts_by_day else 0

            for col in range(7):
                shifts = shifts_by_day[col]
                if shifts:
                    for row_idx, shift in enumerate(shifts, start=1):
                        shift_text = f"{shift['name']}\n{shift['start']} - {shift['end']}"
                        bg_color = '#90EE90' if shift['status'] == 'Completed' else '#FFE4B5'

                        label = tk.Label(self.schedule_frame, text=shift_text,
                                       relief=tk.RAISED, bg=bg_color, padx=5, pady=5,
                                       font=('Arial', 8))
                        label.grid(row=row_idx, column=col, sticky='nsew', padx=2, pady=2)
                else:
                    label = tk.Label(self.schedule_frame, text=_t("shifts.schedule_tab.no_shifts", default="No shifts"),
                                   relief=tk.SUNKEN, fg='gray', padx=5, pady=5)
                    label.grid(row=1, column=col, sticky='nsew', padx=2, pady=2)

            # Configure grid weights
            for col in range(7):
                self.schedule_frame.columnconfigure(col, weight=1)

        except Exception as e:
            messagebox.showerror(_t("shifts.messages.load_schedule_error_title", default="Error"),
                               _t("shifts.messages.load_schedule_error_message", default="Failed to load schedule: {error}").format(error=e))

    def previous_week(self):
        """Go to previous week"""
        self.current_week_start -= timedelta(days=7)
        self.display_weekly_schedule()

    def next_week(self):
        """Go to next week"""
        self.current_week_start += timedelta(days=7)
        self.display_weekly_schedule()

    def load_staff(self):
        """Load staff list"""
        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, position, hourly_rate, email, phone, hire_date, is_active
                FROM restaurant_staff
                ORDER BY name
            ''')

            staff_names = [_t("shifts.shifts_tab.all", default="All")]
            for row in cursor.fetchall():
                name, position, rate, email, phone, hire_date, is_active = row
                status = _t("shifts.statuses.active", default="Active") if is_active else _t("shifts.statuses.inactive", default="Inactive")
                rate_str = _t("shifts.display.rate_format", default="£{rate}").format(rate=f"{rate:.2f}") if rate else _t("shifts.display.not_available", default="N/A")

                self.staff_tree.insert('', tk.END, values=(
                    name, position or '', rate_str, email or '', phone or '',
                    hire_date or '', status
                ))

                if is_active:
                    staff_names.append(name)

            conn.close()

            # Update staff filter
            self.staff_filter['values'] = staff_names

        except Exception as e:
            messagebox.showerror(_t("shifts.messages.load_staff_error_title", default="Error"),
                               _t("shifts.messages.load_staff_error_message", default="Failed to load staff: {error}").format(error=e))

    def load_shifts(self):
        """Load shifts based on filters"""
        for item in self.shifts_tree.get_children():
            self.shifts_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Build query based on filters
            query = '''
                SELECT s.name, sh.shift_date, sh.start_time, sh.end_time,
                       sh.hours_worked, sh.hourly_rate, sh.total_pay, sh.status
                FROM restaurant_shifts sh
                JOIN restaurant_staff s ON sh.staff_id = s.staff_id
                WHERE sh.shift_date BETWEEN ? AND ?
            '''
            params = [self.start_date_var.get(), self.end_date_var.get()]

            staff_filter = self.staff_filter.get()
            all_text = _t("shifts.shifts_tab.all", default="All")
            if staff_filter and staff_filter != all_text:
                query += ' AND s.name = ?'
                params.append(staff_filter)

            status_filter = self.status_filter.get()
            if status_filter and status_filter != all_text:
                # Map translated status back to English for database query
                status_map = {
                    _t("shifts.statuses.scheduled", default="Scheduled"): "Scheduled",
                    _t("shifts.statuses.in_progress", default="In Progress"): "In Progress",
                    _t("shifts.statuses.completed", default="Completed"): "Completed",
                    _t("shifts.statuses.cancelled", default="Cancelled"): "Cancelled"
                }
                db_status = status_map.get(status_filter, status_filter)
                query += ' AND sh.status = ?'
                params.append(db_status)

            query += ' ORDER BY sh.shift_date DESC, sh.start_time'

            cursor.execute(query, params)

            for row in cursor.fetchall():
                name, date, start, end, hours, rate, pay, status = row
                hours_str = _t("shifts.display.hours_format", default="{hours}").format(hours=f"{hours:.2f}") if hours else _t("shifts.display.not_available", default="N/A")
                rate_str = _t("shifts.display.rate_format", default="£{rate}").format(rate=f"{rate:.2f}") if rate else _t("shifts.display.not_available", default="N/A")
                pay_str = _t("shifts.display.pay_format", default="£{pay}").format(pay=f"{pay:.2f}") if pay else _t("shifts.display.not_available", default="N/A")
                end_str = end if end else _t("shifts.schedule_tab.in_progress", default="In Progress")

                self.shifts_tree.insert('', tk.END, values=(
                    name, date, start, end_str, hours_str, rate_str, pay_str, status
                ))

            conn.close()

        except Exception as e:
            messagebox.showerror(_t("shifts.messages.load_shifts_error_title", default="Error"),
                               _t("shifts.messages.load_shifts_error_message", default="Failed to load shifts: {error}").format(error=e))

    def add_shift(self):
        """Add new shift"""
        dialog = ShiftDialog(self.window, None)
        if dialog.result:
            self.load_shifts()
            self.display_weekly_schedule()

    def edit_shift(self):
        """Edit selected shift"""
        selection = self.shifts_tree.selection()
        if not selection:
            messagebox.showwarning(_t("shifts.messages.no_selection_title", default="No Selection"),
                                 _t("shifts.messages.no_selection_shift_edit", default="Please select a shift to edit"))
            return

        # Get shift details
        values = self.shifts_tree.item(selection[0])['values']
        staff_name = values[0]
        shift_date = values[1]
        start_time = values[2]

        # Find shift_id
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT sh.shift_id
                FROM restaurant_shifts sh
                JOIN restaurant_staff s ON sh.staff_id = s.staff_id
                WHERE s.name = ? AND sh.shift_date = ? AND sh.start_time = ?
            ''', (staff_name, shift_date, start_time))

            result = cursor.fetchone()
            conn.close()

            if result:
                shift_id = result[0]
                dialog = ShiftDialog(self.window, shift_id)
                if dialog.result:
                    self.load_shifts()
                    self.display_weekly_schedule()

        except Exception as e:
            messagebox.showerror(_t("shifts.messages.load_shift_error_title", default="Error"),
                               _t("shifts.messages.load_shift_error_message", default="Failed to load shift: {error}").format(error=e))

    def clock_in(self):
        """Clock in for shift (start shift)"""
        selection = self.shifts_tree.selection()
        if not selection:
            messagebox.showwarning(_t("shifts.messages.no_selection_title", default="No Selection"),
                                 _t("shifts.messages.no_selection_shift_clock", default="Please select a shift"))
            return

        values = self.shifts_tree.item(selection[0])['values']
        scheduled_text = _t("shifts.statuses.scheduled", default="Scheduled")
        if values[7] != scheduled_text:
            messagebox.showwarning(_t("shifts.messages.invalid_status_title", default="Invalid Status"),
                                 _t("shifts.messages.invalid_status_clock_in", default="Can only clock in for scheduled shifts"))
            return

        if messagebox.askyesno(_t("shifts.messages.clock_in_title", default="Clock In"),
                              _t("shifts.messages.clock_in_confirm", default="Clock in for {name} on {date}?").format(name=values[0], date=values[1])):
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()

                # Find shift_id
                cursor.execute('''
                    SELECT sh.shift_id
                    FROM restaurant_shifts sh
                    JOIN restaurant_staff s ON sh.staff_id = s.staff_id
                    WHERE s.name = ? AND sh.shift_date = ? AND sh.start_time = ?
                ''', (values[0], values[1], values[2]))

                result = cursor.fetchone()
                if result:
                    cursor.execute('''
                        UPDATE restaurant_shifts
                        SET status = 'In Progress', start_time = time('now', 'localtime')
                        WHERE shift_id = ?
                    ''', (result[0],))

                    conn.commit()
                    messagebox.showinfo(_t("shifts.messages.clock_in_success_title", default="Success"),
                                      _t("shifts.messages.clock_in_success_message", default="Clocked in successfully"))
                    self.load_shifts()

                conn.close()

            except Exception as e:
                messagebox.showerror(_t("shifts.messages.clock_in_error_title", default="Error"),
                                   _t("shifts.messages.clock_in_error_message", default="Failed to clock in: {error}").format(error=e))

    def clock_out(self):
        """Clock out from shift (end shift)"""
        selection = self.shifts_tree.selection()
        if not selection:
            messagebox.showwarning(_t("shifts.messages.no_selection_title", default="No Selection"),
                                 _t("shifts.messages.no_selection_shift_clock", default="Please select a shift"))
            return

        values = self.shifts_tree.item(selection[0])['values']
        in_progress_text = _t("shifts.statuses.in_progress", default="In Progress")
        if values[7] != in_progress_text:
            messagebox.showwarning(_t("shifts.messages.invalid_status_title", default="Invalid Status"),
                                 _t("shifts.messages.invalid_status_clock_out", default="Can only clock out from shifts in progress"))
            return

        if messagebox.askyesno(_t("shifts.messages.clock_out_title", default="Clock Out"),
                              _t("shifts.messages.clock_out_confirm", default="Clock out for {name}?").format(name=values[0])):
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()

                # Find shift
                cursor.execute('''
                    SELECT sh.shift_id, sh.start_time, sh.break_minutes, sh.hourly_rate
                    FROM restaurant_shifts sh
                    JOIN restaurant_staff s ON sh.staff_id = s.staff_id
                    WHERE s.name = ? AND sh.shift_date = ?
                    AND sh.status = 'In Progress'
                ''', (values[0], values[1]))

                result = cursor.fetchone()
                if result:
                    shift_id, start_time, break_mins, rate = result

                    # Calculate hours worked
                    start_dt = datetime.strptime(start_time, '%H:%M:%S')
                    end_dt = datetime.now()
                    duration = end_dt - start_dt.replace(year=end_dt.year, month=end_dt.month, day=end_dt.day)
                    total_minutes = duration.total_seconds() / 60
                    hours_worked = (total_minutes - (break_mins or 0)) / 60

                    total_pay = hours_worked * (rate or 0)

                    cursor.execute('''
                        UPDATE restaurant_shifts
                        SET status = 'Completed',
                            end_time = time('now', 'localtime'),
                            hours_worked = ?,
                            total_pay = ?
                        WHERE shift_id = ?
                    ''', (hours_worked, total_pay, shift_id))

                    conn.commit()
                    messagebox.showinfo(_t("shifts.messages.clock_out_success_title", default="Success"),
                                      _t("shifts.messages.clock_out_success_message",
                                         default="Clocked out successfully\n\nHours worked: {hours}\nTotal pay: £{pay}").format(
                                             hours=f"{hours_worked:.2f}",
                                             pay=f"{total_pay:.2f}"))
                    self.load_shifts()
                    self.display_weekly_schedule()

                conn.close()

            except Exception as e:
                messagebox.showerror(_t("shifts.messages.clock_out_error_title", default="Error"),
                                   _t("shifts.messages.clock_out_error_message", default="Failed to clock out: {error}").format(error=e))

    def delete_shift(self):
        """Delete selected shift"""
        selection = self.shifts_tree.selection()
        if not selection:
            messagebox.showwarning(_t("shifts.messages.no_selection_title", default="No Selection"),
                                 _t("shifts.messages.no_selection_shift_delete", default="Please select a shift to delete"))
            return

        if messagebox.askyesno(_t("shifts.messages.delete_shift_title", default="Confirm Delete"),
                              _t("shifts.messages.delete_shift_confirm", default="Delete selected shift?\n\nThis cannot be undone.")):
            try:
                values = self.shifts_tree.item(selection[0])['values']

                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM restaurant_shifts
                    WHERE shift_id IN (
                        SELECT sh.shift_id
                        FROM restaurant_shifts sh
                        JOIN restaurant_staff s ON sh.staff_id = s.staff_id
                        WHERE s.name = ? AND sh.shift_date = ? AND sh.start_time = ?
                    )
                ''', (values[0], values[1], values[2]))

                conn.commit()
                conn.close()

                messagebox.showinfo(_t("shifts.messages.delete_shift_success_title", default="Success"),
                                  _t("shifts.messages.delete_shift_success_message", default="Shift deleted"))
                self.load_shifts()
                self.display_weekly_schedule()

            except Exception as e:
                messagebox.showerror(_t("shifts.messages.delete_shift_error_title", default="Error"),
                                   _t("shifts.messages.delete_shift_error_message", default="Failed to delete shift: {error}").format(error=e))

    def add_staff(self):
        """Add new staff member"""
        dialog = StaffDialog(self.window, None)
        if dialog.result:
            self.load_staff()

    def edit_staff(self):
        """Edit staff member"""
        selection = self.staff_tree.selection()
        if not selection:
            messagebox.showwarning(_t("shifts.messages.no_selection_title", default="No Selection"),
                                 _t("shifts.messages.no_selection_staff_edit", default="Please select a staff member to edit"))
            return

        staff_name = self.staff_tree.item(selection[0])['values'][0]
        dialog = StaffDialog(self.window, staff_name)
        if dialog.result:
            self.load_staff()

    def toggle_staff_status(self):
        """Toggle staff active/inactive"""
        selection = self.staff_tree.selection()
        if not selection:
            messagebox.showwarning(_t("shifts.messages.no_selection_title", default="No Selection"),
                                 _t("shifts.messages.no_selection_staff_toggle", default="Please select a staff member"))
            return

        staff_name = self.staff_tree.item(selection[0])['values'][0]

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE restaurant_staff
                SET is_active = NOT is_active
                WHERE name = ?
            ''', (staff_name,))

            conn.commit()
            conn.close()

            self.load_staff()

        except Exception as e:
            messagebox.showerror(_t("shifts.messages.update_status_error_title", default="Error"),
                               _t("shifts.messages.update_status_error_message", default="Failed to update status: {error}").format(error=e))

    def delete_staff(self):
        """Delete staff member"""
        selection = self.staff_tree.selection()
        if not selection:
            messagebox.showwarning(_t("shifts.messages.no_selection_title", default="No Selection"),
                                 _t("shifts.messages.no_selection_staff_delete", default="Please select a staff member to delete"))
            return

        staff_name = self.staff_tree.item(selection[0])['values'][0]

        if messagebox.askyesno(_t("shifts.messages.delete_staff_title", default="Confirm Delete"),
                              _t("shifts.messages.delete_staff_confirm", default="Delete staff member '{name}'?\n\nThis cannot be undone.").format(name=staff_name)):
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('DELETE FROM restaurant_staff WHERE name = ?', (staff_name,))
                conn.commit()
                conn.close()

                messagebox.showinfo(_t("shifts.messages.delete_staff_success_title", default="Success"),
                                  _t("shifts.messages.delete_staff_success_message", default="Staff member deleted"))
                self.load_staff()

            except Exception as e:
                messagebox.showerror(_t("shifts.messages.delete_staff_error_title", default="Error"),
                                   _t("shifts.messages.delete_staff_error_message", default="Failed to delete staff: {error}").format(error=e))


class ShiftDialog:
    """Dialog for creating/editing shifts"""

    def __init__(self, parent, shift_id=None):
        self.result = False
        self.shift_id = shift_id
        self.is_edit = shift_id is not None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("shifts.shift_dialog.title_edit", default="Edit Shift") if self.is_edit else _t("shifts.shift_dialog.title_new", default="New Shift"))
        self.dialog.geometry("500x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

        if self.is_edit:
            self.load_shift_data()

    def create_widgets(self):
        """Create widgets"""
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Staff selection
        ttk.Label(frame, text=_t("shifts.shift_dialog.staff_member_label", default="Staff Member:*")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.staff_var = tk.StringVar()
        self.staff_combo = ttk.Combobox(frame, textvariable=self.staff_var, width=38)
        self.staff_combo.grid(row=0, column=1, pady=5)
        self.load_staff_list()

        # Date
        ttk.Label(frame, text=_t("shifts.shift_dialog.date_label", default="Date:*")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=self.date_var, width=40).grid(row=1, column=1, pady=5)

        # Start time
        ttk.Label(frame, text=_t("shifts.shift_dialog.start_time_label", default="Start Time:*")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_var = tk.StringVar(value='09:00')
        ttk.Entry(frame, textvariable=self.start_var, width=40).grid(row=2, column=1, pady=5)

        # End time
        ttk.Label(frame, text=_t("shifts.shift_dialog.end_time_label", default="End Time:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_var = tk.StringVar(value='17:00')
        ttk.Entry(frame, textvariable=self.end_var, width=40).grid(row=3, column=1, pady=5)

        # Break minutes
        ttk.Label(frame, text=_t("shifts.shift_dialog.break_minutes_label", default="Break (minutes):")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.break_var = tk.IntVar(value=30)
        ttk.Entry(frame, textvariable=self.break_var, width=40).grid(row=4, column=1, pady=5)

        # Status
        ttk.Label(frame, text=_t("shifts.shift_dialog.status_label", default="Status:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.status_var = tk.StringVar(value=_t("shifts.statuses.scheduled", default="Scheduled"))
        ttk.Combobox(frame, textvariable=self.status_var, width=38,
                    values=[
                        _t("shifts.statuses.scheduled", default="Scheduled"),
                        _t("shifts.statuses.in_progress", default="In Progress"),
                        _t("shifts.statuses.completed", default="Completed"),
                        _t("shifts.statuses.cancelled", default="Cancelled")
                    ]).grid(row=5, column=1, pady=5)

        # Notes
        ttk.Label(frame, text=_t("shifts.shift_dialog.notes_label", default="Notes:")).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.notes_text = tk.Text(frame, height=4, width=40)
        self.notes_text.grid(row=6, column=1, pady=5)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text=_t("shifts.shift_dialog.save_button", default="Save"), command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("shifts.shift_dialog.cancel_button", default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT)

    def load_staff_list(self):
        """Load active staff for selection"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('SELECT name FROM restaurant_staff WHERE is_active = 1 ORDER BY name')
            staff = [row[0] for row in cursor.fetchall()]
            self.staff_combo['values'] = staff
            conn.close()

        except Exception as e:
            print(_t("shifts.shift_dialog.error_loading_staff", default="Error loading staff: {error}").format(error=e))

    def load_shift_data(self):
        """Load existing shift data"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.name, sh.shift_date, sh.start_time, sh.end_time,
                       sh.break_minutes, sh.status, sh.notes
                FROM restaurant_shifts sh
                JOIN restaurant_staff s ON sh.staff_id = s.staff_id
                WHERE sh.shift_id = ?
            ''', (self.shift_id,))

            data = cursor.fetchone()
            conn.close()

            if data:
                self.staff_var.set(data[0])
                self.date_var.set(data[1])
                self.start_var.set(data[2])
                self.end_var.set(data[3] or '')
                self.break_var.set(data[4] or 0)
                self.status_var.set(data[5])
                self.notes_text.insert('1.0', data[6] or '')

        except Exception as e:
            messagebox.showerror(_t("shifts.shift_dialog.load_error_title", default="Error"),
                               _t("shifts.shift_dialog.load_error_message", default="Failed to load shift data: {error}").format(error=e))

    def save(self):
        """Save shift"""
        if not self.staff_var.get() or not self.date_var.get() or not self.start_var.get():
            messagebox.showwarning(_t("shifts.shift_dialog.missing_info_title", default="Missing Info"),
                                 _t("shifts.shift_dialog.missing_info_message", default="Please fill in all required fields"))
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Get staff ID
            cursor.execute('SELECT staff_id, hourly_rate FROM restaurant_staff WHERE name = ?',
                         (self.staff_var.get(),))
            staff_row = cursor.fetchone()
            if not staff_row:
                messagebox.showerror(_t("shifts.shift_dialog.staff_not_found_title", default="Error"),
                                   _t("shifts.shift_dialog.staff_not_found_message", default="Staff member not found"))
                conn.close()
                return

            staff_id, hourly_rate = staff_row

            # Calculate hours and pay if end time provided
            hours_worked = None
            total_pay = None

            if self.end_var.get():
                try:
                    start = datetime.strptime(self.start_var.get(), '%H:%M')
                    end = datetime.strptime(self.end_var.get(), '%H:%M')
                    duration = (end - start).total_seconds() / 3600
                    hours_worked = duration - (self.break_var.get() / 60)
                    total_pay = hours_worked * (hourly_rate or 0)
                except (ValueError, TypeError):
                    pass

            notes = self.notes_text.get('1.0', tk.END).strip()

            if self.is_edit:
                cursor.execute('''
                    UPDATE restaurant_shifts
                    SET staff_id = ?, shift_date = ?, start_time = ?, end_time = ?,
                        break_minutes = ?, hours_worked = ?, hourly_rate = ?, total_pay = ?,
                        status = ?, notes = ?
                    WHERE shift_id = ?
                ''', (staff_id, self.date_var.get(), self.start_var.get(),
                     self.end_var.get() or None, self.break_var.get(),
                     hours_worked, hourly_rate, total_pay,
                     self.status_var.get(), notes, self.shift_id))
            else:
                cursor.execute('''
                    INSERT INTO restaurant_shifts
                    (staff_id, shift_date, start_time, end_time, break_minutes,
                     hours_worked, hourly_rate, total_pay, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (staff_id, self.date_var.get(), self.start_var.get(),
                     self.end_var.get() or None, self.break_var.get(),
                     hours_worked, hourly_rate, total_pay,
                     self.status_var.get(), notes))

            conn.commit()
            conn.close()

            self.result = True
            messagebox.showinfo(_t("shifts.shift_dialog.save_success_title", default="Success"),
                              _t("shifts.shift_dialog.save_success_message", default="Shift saved successfully"))
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("shifts.shift_dialog.save_error_title", default="Error"),
                               _t("shifts.shift_dialog.save_error_message", default="Failed to save shift: {error}").format(error=e))


class StaffDialog:
    """Dialog for adding/editing staff"""

    def __init__(self, parent, staff_name=None):
        self.result = False
        self.staff_name = staff_name
        self.is_edit = staff_name is not None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("shifts.staff_dialog.title_edit", default="Edit Staff") if self.is_edit else _t("shifts.staff_dialog.title_new", default="New Staff"))
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

        if self.is_edit:
            self.load_staff_data()

    def create_widgets(self):
        """Create widgets"""
        frame = ttk.Frame(self.dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t("shifts.staff_dialog.name_label", default="Name:*")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=40).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t("shifts.staff_dialog.position_label", default="Position:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.position_var = tk.StringVar()
        ttk.Combobox(frame, textvariable=self.position_var, width=38,
                    values=[
                        _t("shifts.positions.chef", default="Chef"),
                        _t("shifts.positions.line_cook", default="Line Cook"),
                        _t("shifts.positions.server", default="Server"),
                        _t("shifts.positions.bartender", default="Bartender"),
                        _t("shifts.positions.host", default="Host"),
                        _t("shifts.positions.dishwasher", default="Dishwasher"),
                        _t("shifts.positions.manager", default="Manager"),
                        _t("shifts.positions.assistant_manager", default="Assistant Manager")
                    ]).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text=_t("shifts.staff_dialog.hourly_rate_label", default="Hourly Rate (£):*")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.rate_var = tk.DoubleVar(value=10.50)
        ttk.Entry(frame, textvariable=self.rate_var, width=40).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text=_t("shifts.staff_dialog.email_label", default="Email:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.email_var, width=40).grid(row=3, column=1, pady=5)

        ttk.Label(frame, text=_t("shifts.staff_dialog.phone_label", default="Phone:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.phone_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.phone_var, width=40).grid(row=4, column=1, pady=5)

        ttk.Label(frame, text=_t("shifts.staff_dialog.hire_date_label", default="Hire Date:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.hire_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=self.hire_date_var, width=40).grid(row=5, column=1, pady=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text=_t("shifts.staff_dialog.save_button", default="Save"), command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("shifts.staff_dialog.cancel_button", default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT)

    def load_staff_data(self):
        """Load existing staff data"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, position, hourly_rate, email, phone, hire_date
                FROM restaurant_staff
                WHERE name = ?
            ''', (self.staff_name,))

            data = cursor.fetchone()
            conn.close()

            if data:
                self.name_var.set(data[0])
                self.position_var.set(data[1] or '')
                self.rate_var.set(data[2] or 10.50)
                self.email_var.set(data[3] or '')
                self.phone_var.set(data[4] or '')
                self.hire_date_var.set(data[5] or datetime.now().strftime('%Y-%m-%d'))

        except Exception as e:
            messagebox.showerror(_t("shifts.staff_dialog.load_error_title", default="Error"),
                               _t("shifts.staff_dialog.load_error_message", default="Failed to load staff data: {error}").format(error=e))

    def save(self):
        """Save staff"""
        if not self.name_var.get():
            messagebox.showwarning(_t("shifts.staff_dialog.missing_info_title", default="Missing Info"),
                                 _t("shifts.staff_dialog.missing_info_message", default="Please enter staff name"))
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            if self.is_edit:
                cursor.execute('''
                    UPDATE restaurant_staff
                    SET name = ?, position = ?, hourly_rate = ?,
                        email = ?, phone = ?, hire_date = ?
                    WHERE name = ?
                ''', (self.name_var.get(), self.position_var.get(), self.rate_var.get(),
                     self.email_var.get(), self.phone_var.get(),
                     self.hire_date_var.get(), self.staff_name))
            else:
                cursor.execute('''
                    INSERT INTO restaurant_staff
                    (name, position, hourly_rate, email, phone, hire_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (self.name_var.get(), self.position_var.get(), self.rate_var.get(),
                     self.email_var.get(), self.phone_var.get(), self.hire_date_var.get()))

            conn.commit()
            conn.close()

            self.result = True
            messagebox.showinfo(_t("shifts.staff_dialog.save_success_title", default="Success"),
                              _t("shifts.staff_dialog.save_success_message", default="Staff saved successfully"))
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("shifts.staff_dialog.save_error_title", default="Error"),
                               _t("shifts.staff_dialog.save_error_message", default="Failed to save staff: {error}").format(error=e))
